"""Pasa por el OpenSCAD real el código que genera la interfaz (matrices, aristas redondeadas).

Si OpenSCAD no está instalado, las pruebas se omiten. Para usar uno concreto:
    OPENSCAD="C:/ruta/openscad.com" python tests/test_openscad.py

Ejecutar:  python tests/test_openscad.py
"""

import math
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from scadgui.edges import finish_edges  # noqa: E402
from scadgui.geometry import load_stl, signed_volume  # noqa: E402
from scadgui.library import CUBE_EDGE_KEYS  # noqa: E402
from scadgui.model import Document, Node, generate, make_node  # noqa: E402
from scadgui.parser import parse  # noqa: E402


def find_openscad() -> str:
    candidates = [os.environ.get("OPENSCAD", ""), shutil.which("openscad") or ""]
    for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
        if base:
            candidates += [os.path.join(base, "OpenSCAD", "openscad.com"),
                           os.path.join(base, "OpenSCAD", "openscad.exe")]
    return next((c for c in candidates if c and os.path.isfile(c)), "")


EXE = find_openscad()


def render(code: str):
    """Exporta a STL y devuelve los triángulos; falla si OpenSCAD da errores o avisos."""
    folder = tempfile.mkdtemp()
    src, out = os.path.join(folder, "m.scad"), os.path.join(folder, "m.stl")
    with open(src, "w", encoding="utf-8") as fh:
        fh.write(code)
    run = subprocess.run([EXE, "-o", out, src], capture_output=True, text=True, timeout=600)
    log = run.stdout + run.stderr
    problems = [line for line in log.splitlines() if "WARNING" in line or "ERROR" in line]
    assert run.returncode == 0 and not problems, log[-1500:]
    assert os.path.getsize(out) > 0, log[-500:]
    return load_stl(out)


def volume_of(code: str) -> float:
    """Volumen del modelo. Si OpenSCAD no deja nada (una intersección vacía), 0."""
    folder = tempfile.mkdtemp()
    src, out = os.path.join(folder, "m.scad"), os.path.join(folder, "m.stl")
    with open(src, "w", encoding="utf-8") as fh:
        fh.write(code)
    run = subprocess.run([EXE, "-o", out, src], capture_output=True, text=True, timeout=600)
    log = run.stdout + run.stderr
    problems = [line for line in log.splitlines() if "WARNING" in line or "ERROR" in line]
    assert not problems, log[-1500:]
    if not os.path.isfile(out) or os.path.getsize(out) == 0:
        return 0.0
    return abs(signed_volume(load_stl(out)))


def _rounded(src: str, edges_of, mode: str, value: float) -> str:
    doc = parse(src)
    node = doc.children[0]
    finish_edges(doc, [(node.id, k) for k in edges_of], mode, value)
    return generate(doc).text


def test_cubo_todas_las_aristas_redondeadas():
    render("$fn = 24;\n" + _rounded("cube([40, 30, 10], center = true);", CUBE_EDGE_KEYS, "round", 3))


def test_esquinas_con_tres_aristas_redondeadas_son_esfericas():
    """Caja 40 x 30 x 10 con todas las aristas redondeadas (r = 3): volumen de la caja interior
    más caras, cuartos de cilindro y ocho octantes de esfera. Con las esquinas como cruce de
    cilindros (la versión anterior) salían unos 10 mm³ de más."""
    tris = render("$fn = 96;\n" + _rounded("cube([40, 30, 10]);", CUBE_EDGE_KEYS, "round", 3))
    p, q, s, r = 34, 24, 4, 3
    exact = p * q * s + 2 * (p * q + q * s + p * s) * r + math.pi * (p + q + s) * r * r + 4 / 3 * math.pi * r ** 3
    assert abs(signed_volume(tris) - exact) < 3, signed_volume(tris)


def test_cubo_algunas_aristas_y_chaflan():
    render(_rounded("cube([40, 30, 10]);", ["x1y1", "y0z1", "x0z0"], "round", 2))
    render(_rounded("cube(20);", ["x1y1", "y0z1", "x0z0", "y1z0"], "chamfer", 2))


def test_cilindro_con_bordes():
    render(_rounded("cylinder(h = 20, d = 16, $fn = 48);", ["top", "bottom"], "round", 3))
    render(_rounded("cylinder(h = 20, r = 8, center = true);", ["top"], "chamfer", 2))


def test_radios_activados_en_el_panel_no_dan_avisos():
    """Activar d2 en un cylinder con r, o d en una sphere, no debe dejar parámetros que choquen."""
    doc = Document()
    cyl = doc.add("cylinder")
    doc.set_param(cyl.id, "d2", 4)
    sph = doc.add("sphere")
    doc.set_param(sph.id, "d", 4)
    bad = parse("cylinder(h = 10, r = 1, d2 = 4, center = true);")
    bad.fix_radii(bad.children[0].id)
    render(generate(doc).text + generate(bad).text)   # render() falla si OpenSCAD da algún aviso


def test_matrices():
    doc = Document()
    for kind in ("linear_array", "polar_array", "grid_array"):
        doc.add(kind).children.append(make_node("cube"))
    render(generate(doc).text)


def test_aristas_dentro_de_un_modulo_de_usuario():
    doc = Document()
    c = doc.add("cube")
    finish_edges(doc, [(c.id, "x1y1")], "round", 1)
    doc.make_module([c.id], "pata", [])
    render(generate(doc).text)



def test_engranajes():
    """La pareja de engranajes (con agujero) se calcula sin avisos y con el volumen esperado."""
    from scadgui import gears
    doc = Document()
    g = doc.add("spur_gear")
    for key, value in (("mod", 2), ("teeth", 20), ("thickness", 6), ("bore", 8)):
        doc.set_param(g.id, key, value)
    doc.add_meshing_gear(g.id, 31)
    tris = render("$fn = 48;\n" + generate(doc).text)
    def area(p):
        return 0.5 * abs(sum(p[i - 1][0] * p[i][1] - p[i][0] * p[i - 1][1] for i in range(len(p))))
    hole = 48 * 0.5 * 16 * math.sin(2 * math.pi / 48)
    expected = sum((area(gears.polygon(2, z, 20, 0.1)) - hole) * 6 for z in (20, 31))
    assert abs(signed_volume(tris) - expected) < 1, (signed_volume(tris), expected)

def test_helicoidal_como_en_la_vista_aproximada():
    """El helicoidal de OpenSCAD tiene el mismo volumen que la malla de la vista aproximada (las
    dos parten el retorcido en las mismas rebanadas), y la pareja de mano contraria no se toca."""
    from scadgui import geometry, gears
    doc = Document()
    g = doc.add("helical_gear")
    for key, value in (("mod", 1), ("teeth", 20), ("thickness", 10), ("helix_angle", 20)):
        doc.set_param(g.id, key, value)
    code = generate(doc).text
    mine = abs(signed_volume(geometry.helical_gear(g.params)))
    assert abs(volume_of(code) - mine) < 1, (volume_of(code), mine)
    # Las dos ruedas de la pareja, una a derechas y otra a izquierdas: ni se tocan…
    doc.add_meshing_gear(g.id, 40)
    pair = generate(doc).text
    body = pair.split("module ", 1)
    assert volume_of("intersection() {\n" + body[0] + "}\nmodule " + body[1]) == 0
    # …y juntas pesan lo que las dos por separado (o sea que no se solapan ni les falta nada)
    both = mine + abs(signed_volume(geometry.helical_gear(
        dict(g.params, teeth=40, left_hand=True))))
    assert abs(volume_of(pair) - both) < 2, (volume_of(pair), both)
    assert gears.helical_center_distance(1, 20, 40, 20) > 0


def test_espina_de_pescado_igual_que_la_vista_aproximada():
    """El espina de pescado de OpenSCAD pesa igual que la vista aproximada (las dos mitades
    siguen las mismas rebanadas), y la pareja -de mano contraria, igual que un helicoidal
    simple- no se toca."""
    from scadgui import geometry
    doc = Document()
    g = doc.add("herringbone_gear")
    for key, value in (("mod", 2), ("teeth", 18), ("thickness", 16), ("helix_angle", 25)):
        doc.set_param(g.id, key, value)
    code = generate(doc).text
    mine = abs(signed_volume(geometry.herringbone_gear(g.params)))
    assert abs(volume_of(code) - mine) < 1, (volume_of(code), mine)
    # La pareja va a la mano contraria (como un helicoidal simple): no se tocan…
    doc.add_meshing_gear(g.id, 40)
    pair = generate(doc).text
    body = pair.split("module ", 1)
    assert volume_of("intersection() {\n" + body[0] + "}\nmodule " + body[1]) == 0
    # …y juntas pesan lo que las dos por separado (o sea que no se solapan ni les falta nada)
    both = mine + abs(signed_volume(geometry.herringbone_gear(
        dict(g.params, teeth=40, left_hand=True))))
    assert abs(volume_of(pair) - both) < 2, (volume_of(pair), both)
    # Con ranura central: menos volumen que sin ella, y sigue sin avisos de CGAL.
    doc2 = Document()
    g2 = doc2.add("herringbone_gear")
    for key, value in (("mod", 2), ("teeth", 18), ("thickness", 16), ("helix_angle", 25),
                       ("groove", 3), ("bore", 8), ("keyway", True)):
        doc2.set_param(g2.id, key, value)
    assert volume_of(generate(doc2).text) < volume_of(code)


def test_conico_su_pareja_y_las_operaciones_normales():
    """El cónico sale con el volumen calculado, su pareja no lo toca, y aguanta las operaciones
    de siempre: buje soldado, agujero del eje y aligeramientos, sin avisos de CGAL."""
    from scadgui import geometry
    doc = Document()
    g = doc.add("bevel_gear")
    for key, value in (("mod", 2), ("teeth", 20), ("mate_teeth", 20), ("face_width", 8)):
        doc.set_param(g.id, key, value)
    mine = abs(signed_volume(geometry.bevel_gear(g.params)))
    assert abs(volume_of("$fn = 48;\n" + generate(doc).text) - mine) < 1
    doc.add_meshing_gear(g.id)                       # la pareja, girada 90°: no se tocan
    pair = generate(doc).text
    body = pair.split("module ", 1)
    assert volume_of("intersection() {\n" + body[0] + "}\nmodule " + body[1]) == 0
    assert abs(volume_of(pair) - 2 * mine) < 2       # y juntas pesan lo que las dos por separado
    doc.children.pop()                               # fuera la pareja
    doc.set_param(g.id, "bore", 8)
    body = generate(doc).text.split("module ", 1)
    render("$fn = 48;\ndifference() { union() { " + body[0] +
           " translate([0, 0, 26]) cylinder(h = 14, d = 18); }\n"
           "  for (i = [0:3]) rotate([0, 0, 90 * i]) translate([12, 0, 20]) cylinder(h = 30, d = 5);\n"
           "}\nmodule " + body[1])


def test_cremallera_y_su_engranaje():
    """La cremallera sale con el volumen calculado y el engranaje que se le pone encima no la toca.
    Lo mismo con el dentado inclinado y su helicoidal."""
    from scadgui import geometry
    for extra in ((), (("helix_angle", 20),)):
        doc = Document()
        r = doc.add("rack")
        for key, value in (("mod", 2), ("teeth", 8), ("thickness", 5), ("base", 4)) + extra:
            doc.set_param(r.id, key, value)
        mine = abs(signed_volume(geometry.rack(r.params)))
        assert abs(volume_of(generate(doc).text) - mine) < 1, extra
        doc.add_meshing_gear(r.id, 25)
        pair = generate(doc).text
        body = pair.split("module ", 1)
        assert volume_of("intersection() {\n" + body[0] + "}\nmodule " + body[1]) == 0, extra


def test_polea_dentada_volumen_y_agujero():
    """La polea sale con el volumen de la vista aproximada (mismas fórmulas en Python y
    OpenSCAD) y el agujero del eje la atraviesa entera."""
    from scadgui import geometry
    for section, teeth, width, bore in (("MXL", 24, 6, 3), ("XL", 20, 6, 5), ("H", 12, 10, 8)):
        doc = Document()
        pu = doc.add("pulley")
        for key, value in (("section", section), ("teeth", teeth), ("width", width)):
            doc.set_param(pu.id, key, value)
        mine = abs(signed_volume(geometry.pulley(pu.params)))
        assert abs(volume_of(generate(doc).text) - mine) < 1, (section, teeth)
        doc.set_param(pu.id, "bore", bore)
        n = max(32, teeth * 2)                        # el mismo $fn que pone el módulo
        hole = n * 0.5 * (bore / 2) ** 2 * math.sin(2 * math.pi / n) * width
        assert abs(volume_of(generate(doc).text) - (mine - hole)) < 1, (section, teeth, bore)


def test_polea_dentada_con_pestanas():
    """Las pestañas (collares que sobresalen del Ø exterior) pesan lo mismo en OpenSCAD que en
    la malla de la vista aproximada, a un lado, al otro y a los dos."""
    from scadgui import geometry
    for flange in ("superior", "inferior", "ambas"):
        doc = Document()
        pu = doc.add("pulley")
        for key, value in (("section", "XL"), ("teeth", 20), ("width", 6),
                           ("flange", flange), ("flange_height", 2)):
            doc.set_param(pu.id, key, value)
        mine = abs(signed_volume(geometry.pulley(pu.params)))
        assert abs(volume_of(generate(doc).text) - mine) < 1, flange


def test_pestanas_de_la_polea_en_todos_los_idiomas():
    """El módulo escrito en el archivo entiende el valor de flange en cualquier idioma: la pieza
    pesa lo mismo que en español y las pestañas no desaparecen."""
    from scadgui.i18n import LANGUAGES
    doc = Document()
    pu = doc.add("pulley")
    plain = volume_of(generate(doc).text)
    doc.set_param(pu.id, "flange_height", 2)
    for flange in ("superior", "inferior", "ambas"):
        doc.set_param(pu.id, "flange", flange)
        reference = volume_of(generate(doc, header_lang="es").text)
        assert reference > plain + 1, flange
        for lang in LANGUAGES:
            text = generate(doc, header_lang=lang).text
            assert abs(volume_of(text) - reference) < 1, (flange, lang)


def test_ranuras_de_anillo_y_oring_quitan_lo_que_toca():
    """La máscara restada de un eje o un agujero quita la corona de la tabla, en toda su altura."""
    from scadgui import hardware as hw
    n = hw.GROOVE_FN

    def area(d):
        return n * 0.5 * (d / 2) ** 2 * math.sin(2 * math.pi / n)

    def mask_code(node):
        doc = Document()
        doc.children.append(node)
        return generate(doc, header=False).text

    def removed(base, node, z=0.0):
        whole = volume_of(base)
        cut = volume_of(f"difference() {{ {base} translate([0, 0, {z}]) {{ {mask_code(node)} }} }}")
        return whole - cut

    shaft = "cylinder(h = 20, d = {d}, $fn = 96);"
    block = "difference() {{ cylinder(h = 20, d = 300, $fn = 96); translate([0, 0, -1]) cylinder(h = 22, d = {d}, $fn = 96); }}"
    for s in ("4", "20", "100"):
        r = hw.RETAINING_RINGS_3AM1[s]
        got = removed(shaft.format(d=s), hw.create_ring_groove_node("3am1", s), 5)
        want = (area(float(s)) - area(r["G"])) * r["W"]
        assert abs(got - want) < max(0.05, want * 1e-3), ("3am1", s, got, want)
    for s in ("8", "20", "100"):
        r = hw.RETAINING_RINGS_3BM1[s]
        got = removed(block.format(d=s), hw.create_ring_groove_node("3bm1", s), 5)
        want = (area(r["G"]) - area(float(s))) * r["W"]
        assert abs(got - want) < max(0.05, want * 1e-3), ("3bm1", s, got, want)
    f = hw.oring_groove("2.62")
    # Un eje de Ø29.9 para un agujero de Ø30: la ranura va al Ø de la tabla, no al del eje.
    got = removed(shaft.format(d=29.9), hw.create_oring_groove_node("shaft", "2.62", 30), 5)
    want = (area(29.9) - area(30 - 2 * f["gland"])) * f["width"]
    assert abs(got - want) < want * 1e-3, (got, want)
    got = removed(block.format(d=30), hw.create_oring_groove_node("bore", "2.62", 30), 5)
    want = (area(30 + 2 * f["gland"]) - area(30)) * f["width"]
    assert abs(got - want) < want * 1e-3, (got, want)
    base = "translate([0, 0, -20]) cylinder(h = 20, d = 100, $fn = 96);"     # la cara queda en z = 0
    got = removed(base, hw.create_oring_groove_node("face", "2.62", 40))
    want = (area(40) - area(40 - 2 * f["width"])) * f["gland"]
    assert abs(got - want) < want * 1e-3, (got, want)


def test_asiento_de_rodamiento_quita_lo_que_toca():
    """El asiento baja el ancho del rodamiento desde la cara, y el paso libre atraviesa la pared."""
    from scadgui import hardware as hw
    n = hw.GROOVE_FN

    def area(d):
        return n * 0.5 * (d / 2) ** 2 * math.sin(2 * math.pi / n)

    def cut(node, thick):
        doc = Document()
        doc.children.append(node)
        mask = generate(doc, header=False).text
        base = f"translate([0, 0, {-thick}]) cylinder(h = {thick}, d = 200, $fn = 96);"
        return volume_of(base) - volume_of(f"difference() {{ {base} {mask} }}")

    d = hw.bearing_seat("6204", "H7")
    got = cut(hw.create_bearing_seat_node("6204", "H7"), 30)
    want = area(d["bore"]) * 14
    assert abs(got - want) < want * 1e-3, (got, want)
    got = cut(hw.create_bearing_seat_node("6204", "H7", 5), 19)       # asiento + pared de 5 mm
    want = area(d["bore"]) * 14 + area(41) * 5
    assert abs(got - want) < want * 1e-3, (got, want)


def test_estriado_volumen_y_encaje():
    """La pieza de OpenSCAD pesa lo mismo que la vista aproximada, en todas las columnas de la tabla;
    el eje y el cubo encajan sin chocar y girar el eje medio paso los haría chocar."""
    from scadgui import geometry
    ctx = {"fn": 0, "fa": 12, "fs": 2}
    cases = ({"mod": 2}, {"mod": 2, "fillet_root": True}, {"mod": 2, "pressure_angle": 37.5},
             {"mod": 2, "pressure_angle": 45}, {"mod": 1.5, "teeth": 11, "clearance": 0.1},
             {"mod": 2, "internal": True}, {"mod": 2, "internal": True, "hub_d": 70, "center": True},
             {"mod": 2, "pressure_angle": 45, "internal": True}, {"mod": 1, "teeth": 9, "internal": True})
    for params in cases:
        doc = Document()
        node = doc.add("spline")
        for key, value in params.items():
            doc.set_param(node.id, key, value)
        mine = abs(signed_volume(geometry.spline(node.params, ctx)))
        got = volume_of(generate(doc).text)
        assert abs(got - mine) < max(1, mine * 1e-5), (params, got, mine)
    shaft, hub = ("spline(mod = 2, teeth = 20, length = 10);",
                  "spline(mod = 2, teeth = 20, length = 10, internal = true);")
    doc = Document()
    doc.add("spline")                                  # para que generate() escriba el módulo
    module = generate(doc, header=False).text
    module = module[module.index("module spline("):]
    assert volume_of(f"intersection() {{ {shaft} {hub} }}\n{module}") < 1      # encajan
    half = 360 / 20 / 2
    assert volume_of(f"intersection() {{ rotate([0, 0, {half}]) {shaft} {hub} }}\n{module}") > 100


def test_cunero_en_engranajes_y_poleas():
    """El fondo del cuñero queda a d/2 + t2 del eje, con el ancho de la tabla, a lo largo de toda la
    pieza; quita el volumen que le toca, y sin medida en la tabla no talla nada."""
    from scadgui import gears
    d = 20
    b, t2 = gears.keyway_size(d)
    # Lo que quita fuera del agujero: el rectángulo menos lo que ya estaba hueco (círculo en |y| < b/2).
    steps = 2000
    hollow = sum(math.sqrt((d / 2) ** 2 - ((i + 0.5) / steps * b - b / 2) ** 2) * b / steps for i in range(steps))
    area = b * (d / 2 + t2) - hollow
    pieces = (("spur_gear", {"mod": 2, "teeth": 40, "thickness": 10}),
              ("helical_gear", {"mod": 2, "teeth": 40, "thickness": 10, "helix_angle": 15}),
              ("bevel_gear", {"mod": 2, "teeth": 40, "mate_teeth": 40, "face_width": 10}),
              ("pulley", {"section": "H", "teeth": 30, "width": 10}),
              ("v_pulley", {"section": "A", "datum_d": 120}))
    for kind, params in pieces:
        doc = Document()
        doc.fn = 96
        node = doc.add(kind)
        for key, value in {**params, "bore": d}.items():
            doc.set_param(node.id, key, value)
        solid = volume_of(generate(doc).text)
        doc.set_param(node.id, "keyway", True)
        tris = render(generate(doc).text)
        pts = tris.reshape(-1, 3)
        corners = pts[(abs(pts[:, 0] - (d / 2 + t2)) < 0.01) & (abs(abs(pts[:, 1]) - b / 2) < 0.01)]
        assert {round(float(y), 2) for y in corners[:, 1]} == {-b / 2, b / 2}, kind
        length = float(corners[:, 2].max() - corners[:, 2].min())
        assert length > 1, kind
        removed = solid - abs(signed_volume(tris))
        assert abs(removed - area * length) < 0.03 * area * length, (kind, removed, area * length)
    doc = Document()
    node = doc.add("spur_gear")
    doc.set_param(node.id, "mod", 2)
    doc.set_param(node.id, "bore", 5)
    plain = volume_of(generate(doc).text)
    doc.set_param(node.id, "keyway", True)
    assert abs(volume_of(generate(doc).text) - plain) < 1e-6          # Ø 5 no está en la tabla
    doc.set_param(node.id, "key_width", 2)
    doc.set_param(node.id, "key_depth", 1)
    assert plain - volume_of(generate(doc).text) > 1                  # a medida, sí


def test_polea_trapecial_volumen_y_agujero():
    """La polea trapecial sale con el volumen de la vista aproximada (mismas fórmulas en Python
    y OpenSCAD, vía rotate_extrude) y el agujero del eje la atraviesa entera."""
    from scadgui import geometry
    ctx = {"fn": 0, "fa": 12, "fs": 2}
    for section, datum_d, grooves, bore in (("A", 80, 1, 8), ("B", 150, 2, 12), ("C", 250, 3, 15)):
        doc = Document()
        pu = doc.add("v_pulley")
        for key, value in (("section", section), ("datum_d", datum_d), ("grooves", grooves)):
            doc.set_param(pu.id, key, value)
        mine = abs(signed_volume(geometry.v_pulley(pu.params, ctx)))
        tol = max(1, mine * 1e-5)      # el STL de OpenSCAD 2021 lleva 6 cifras: el error crece con la pieza
        assert abs(volume_of(generate(doc).text) - mine) < tol, (section, datum_d, grooves)
        doc.set_param(pu.id, "bore", bore)
        from scadgui import gears
        width = gears.v_pulley_dims(section, datum_d, grooves)["face_width"]
        n = geometry.fragments(bore / 2, ctx)          # $fn=0 -> fórmula de fragments con $fa/$fs
        hole = n * 0.5 * (bore / 2) ** 2 * math.sin(2 * math.pi / n) * width
        assert abs(volume_of(generate(doc).text) - (mine - hole)) < tol, (section, datum_d, grooves, bore)


def _engines() -> tuple:
    """CGAL siempre; Manifold solo si esta versión de OpenSCAD tiene --backend (2021.01 no)."""
    if not EXE:
        return ((),)
    help_text = subprocess.run([EXE, "--help"], capture_output=True, text=True).stdout
    return ((), ("--backend=manifold",)) if "--backend" in help_text else ((),)


def test_bridas_volumen_en_los_dos_motores():
    """Bridas de las dos normas, de todos los tipos y caras: OpenSCAD pesa lo mismo que el perfil
    girado de la vista aproximada menos los agujeros de los tornillos, con CGAL y con Manifold."""
    from scadgui import flanges, geometry
    ENGINES = _engines()
    ctx = {"fn": 0, "fa": 12, "fs": 2}
    cases = (("asme_b16_5", "150", "4", "weld_neck", "raised"), ("asme_b16_5", "300", "1/2", "slip_on", "raised"),
             ("asme_b16_5", "600", "8", "blind", "raised"), ("asme_b16_5", "2500", "2", "weld_neck", "flat"),
             ("asme_b16_5", "400", "2", "weld_neck", "raised"),
             ("en_1092_1", "16", "100", "weld_neck", "raised"), ("en_1092_1", "6", "50", "plate", "raised"),
             ("en_1092_1", "40", "200", "slip_on", "flat"), ("en_1092_1", "100", "25", "blind", "raised"))
    module = None
    for std, rating, size, ftype, facing in cases:
        node = flanges.create_flange_node(std, rating, size, ftype, facing, bore=None if flanges.flange(
            std, rating, size, ftype, facing)["bore"] is not None else 50)
        doc = Document()
        doc.children.append(node)
        code = generate(doc).text
        module = module or code[code.index("module pipe_flange("):]
        p = node.params
        mine = abs(signed_volume(geometry.pipe_flange(p, ctx)))
        n = geometry.fragments(p["hole"] / 2, ctx)
        holes = p["bolts"] * n * 0.5 * (p["hole"] / 2) ** 2 * math.sin(2 * math.pi / n) * p["thickness"]
        for extra in ENGINES:
            folder = tempfile.mkdtemp()
            src, out = os.path.join(folder, "m.scad"), os.path.join(folder, "m.stl")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write(code)
            run = subprocess.run([EXE, *extra, "-o", out, src], capture_output=True, text=True, timeout=600)
            log = run.stdout + run.stderr
            assert run.returncode == 0 and "WARNING" not in log and "ERROR" not in log, log[-800:]
            got = abs(signed_volume(load_stl(out)))
            assert abs(got - (mine - holes)) < max(1, mine * 1e-5), (std, rating, size, ftype, facing, extra, got,
                                                                     mine - holes)
    # Los agujeros quedan a horcajadas de los ejes: ninguno corta el eje +X.
    flange = "pipe_flange(face_h = 0, hub_d = 0, bore = 0);"
    on_axis = "translate([95.25, 0, 10]) cube([0.5, 0.5, 0.5], center = true);"
    half_step = "rotate(22.5) " + on_axis
    assert volume_of(f"intersection() {{ {flange} {on_axis} }}\n{module}") > 0.1
    assert volume_of(f"intersection() {{ {flange} {half_step} }}\n{module}") < 1e-6


def test_arbol_de_levas_volumen_y_orientacion():
    """Cada lóbulo (leyes, ángulos, asimetría, resolución) pesa en OpenSCAD lo mismo que la vista
    aproximada; el árbol entero se renderiza sin avisos, y la punta está donde dice su ángulo."""
    from scadgui import geometry
    cases = ({}, {"motion": "armonica", "angle": 90}, {"motion": "parabolica", "rise_angle": 60, "fall_angle": 140},
             {"motion": "velocidad_constante", "dwell_angle": 0, "step": 2}, {"angle": -45, "step": 0.5, "lift": 3})
    for params in cases:
        doc = Document()
        node = doc.add("cam_lobe")
        for key, value in params.items():
            doc.set_param(node.id, key, value)
        mine = abs(signed_volume(geometry.cam_lobe(node.params)))
        assert abs(volume_of(generate(doc).text) - mine) < max(0.01, mine * 1e-5), params
    doc = Document()
    doc.add("camshaft_main_shaft")
    for i, z in enumerate((40, 100, 160, 220)):
        lobe = doc.add("cam_lobe")
        doc.set_param(lobe.id, "position", z)
        doc.set_param(lobe.id, "angle", 90 * i)
    code = generate(doc).text
    assert len(render(code)) > 1000
    module = code[code.index("module camshaft_main_shaft("):]
    nose = "translate([22, 0, 20]) cube(1, center = true);"            # radio 22 en +X, dentro del lóbulo
    assert volume_of(f"intersection() {{ cam_lobe(angle = 0); {nose} }}\n{module}") > 0.99
    assert volume_of(f"intersection() {{ cam_lobe(angle = 180); {nose} }}\n{module}") < 1e-6


def test_lobulo_perfiles_geometricos_en_openscad():
    """Los perfiles hechos con hull/circle/scale pesan en OpenSCAD lo mismo que la vista aproximada
    (los mismos vértices), y el periforme tiene la punta donde dice su ángulo."""
    from scadgui import geometry
    for params in ({"profile": "circular"}, {"profile": "excentrico", "angle": 60},
                   {"profile": "eliptico", "step": 2}, {"profile": "periforme", "nose_r": 6, "angle": -90},
                   {"profile": "periforme", "nose_r": 4, "lift": 10, "step": 0.5}):
        doc = Document()
        node = doc.add("cam_lobe")
        for key, value in params.items():
            doc.set_param(node.id, key, value)
        mine = abs(signed_volume(geometry.cam_lobe(node.params)))
        assert abs(volume_of(generate(doc).text) - mine) < max(0.01, mine * 1e-5), params
    doc = Document()
    doc.add("cam_lobe")
    code = generate(doc).text
    module = code[code.index("module cam_lobe("):]
    nose = "translate([0, -22, 20]) cube(1, center = true);"        # radio 22 en -Y
    pear = 'cam_lobe(profile = "periforme", nose_r = 6, angle = {a});'
    assert volume_of(f"intersection() {{ {pear.format(a=-90)} {nose} }}\n{module}") > 0.99
    assert volume_of(f"intersection() {{ {pear.format(a=90)} {nose} }}\n{module}") < 1e-6


def test_arbol_de_levas_completo_se_renderiza():
    """El grupo del asistente (eje y 8 lóbulos de perfiles distintos) sale de OpenSCAD sin avisos y
    pesa al menos lo que el eje más lo que sobresale cada lóbulo de él."""
    import math
    from scadgui import camshaft as cs, gears
    from scadgui.geometry import _area
    lobe = {"profile": "ley", "base_r": 15, "lift": 8, "width": 12, "motion": "cicloidal", "rise_angle": 110,
            "dwell_angle": 20, "fall_angle": 110, "nose_r": 5, "step": 1}
    doc = Document()
    doc.children.append(cs.create_camshaft({"length": 220, "d": 25}, lobe, cs.layout(4, 2, 20, 50, 20, 90, 110)))
    for n, profile in zip(doc.children[0].children[1:], ("ley", "excentrico", "eliptico", "periforme") * 2):
        n.params["profile"] = profile
        n.params["nose_r"] = 5
    got = volume_of(generate(doc).text)
    shaft = math.pi * 12.5 ** 2 * 220
    lobes = sum(abs(_area(gears.lobe_polygon(15, 8, 110, 20, 110, "cicloidal", 0, 1, n.params["profile"], 5))) * 12
                for n in doc.children[0].children[1:])
    inside = 8 * math.pi * 12.5 ** 2 * 12
    assert abs(got - (shaft + lobes - inside)) < 0.01 * shaft, (got, shaft + lobes - inside)


def test_calculadora_de_transmisiones_engrana():
    """Los trenes de la calculadora engranan: cada pareja no se toca (con la holgura de serie), en
    recto, helicoidal y espina de pescado, en una etapa, en dos y en un tren revertido."""
    import copy
    from scadgui import transmission as tm
    cases = (("spur_gear", 3.75, 1, False, {}),
             ("helical_gear", 12, 2, False, {"helix_angle": 20, "thickness": 8}),
             ("herringbone_gear", 9, 2, True, {"helix_angle": 25, "thickness": 12}))
    for kind, ratio, stages, coaxial, extra in cases:
        sol = tm.search(ratio, 1, stages, 12, 60, kind, 1, extra.get("helix_angle", 0), coaxial=coaxial)[0]
        params = dict(mod=1, backlash=0.1, bore=4, **extra)
        group = tm.create_train(sol, kind, params, coaxial=coaxial)
        doc = Document(children=[group])
        render(generate(doc).text)
        for a, b in ((0, 1), (2, 3))[:stages]:
            inter = make_node("intersection")
            inter.children = [copy.deepcopy(group.children[a]), copy.deepcopy(group.children[b])]
            assert volume_of(generate(Document(children=[inter])).text) == 0, (kind, sol.stages, a, b)
            if kind != "spur_gear":           # chocar dos helicoidales tarda minutos en CGAL
                continue
            # Medio diente girado, la misma pareja choca: están a la distancia justa, no separadas.
            wrong = copy.deepcopy(group.children[b])
            holder = wrong
            while holder.children and holder.children[0].kind in ("translate", "rotate"):
                holder = holder.children[0]
            z = sol.stages[a // 2][1]
            holder.children = [Node(kind="rotate", params={"a": [0, 0, 180 / z]}, children=holder.children)]
            inter.children = [copy.deepcopy(group.children[a]), wrong]
            assert volume_of(generate(Document(children=[inter])).text) > 1, (kind, sol.stages, a, b)

def test_calculadora_de_correas_en_openscad():
    """Las dos poleas y la correa de referencia se renderizan, y la correa no se mete en ninguna polea
    (ni en la dentada ni en las ranuras de la en V)."""
    import copy
    from scadgui import transmission as tm
    timing = tm.search_timing(3, 1, "XL", 10, 80)[0]
    for sol, params in ((timing, {"width": 8, "bore": 5}),
                        (timing, {"width": 8, "flange": "ambas", "flange_height": 2}),
                        (timing, {"width": 8, "flange": "inferior"}),
                        (tm.search_v(2.5, 1, "A", 0, 300, 5)[0], {"grooves": 2, "bore": 12})):
        g = tm.create_belt_drive(sol, params)
        render(generate(Document(children=[g])).text)
        for i in (0, 1):
            for belt in g.children[2:]:
                inter = make_node("intersection")
                inter.children = [copy.deepcopy(g.children[i]), copy.deepcopy(belt)]
                assert volume_of(generate(Document(children=[inter])).text) == 0, (sol.kind, i)



def test_plano_tecnico_queda_dentro_de_la_hoja():
    """OpenSCAD dibuja la lámina sin avisos y todo lo que dibuja (vistas y rótulos) queda dentro de
    la hoja, también con la pieza lejos del origen."""
    import re
    from scadgui.drawing import plan_sheet, generate_technical_drawing_code
    model = ("translate([40, 30, 0]) difference() { cube([120, 60, 40]); "
             "translate([60, 30, -1]) cylinder(h = 50, d = 30); }")
    box = ((40, 30, 0), (160, 90, 40))
    for border in (True, False):
        code = generate_technical_drawing_code(model, box=box, include_border=border)
        folder = tempfile.mkdtemp()
        src, out = os.path.join(folder, "p.scad"), os.path.join(folder, "p.svg")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(code)
        run = subprocess.run([EXE, "-o", out, src], capture_output=True, text=True, timeout=600)
        log = run.stdout + run.stderr
        assert run.returncode == 0 and "WARNING" not in log and "ERROR" not in log, log[-1500:]
        svg = open(out, encoding="utf-8").read()
        pts = [(float(a), -float(b)) for a, b in re.findall(r"(-?[\d.]+),(-?[\d.]+)", svg.split("<path", 1)[1])]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        if border:                                # el borde de la hoja es lo más exterior
            assert abs(min(xs)) < 1e-3 and abs(min(ys)) < 1e-3
            assert abs(max(xs) - 297) < 1e-3 and abs(max(ys) - 210) < 1e-3
        else:                                     # sin marco: lo dibujado cae en las casillas previstas
            _, place, _ = plan_sheet(box, "A4", 0.0, include_border=False)
            rects = [r for _, _, r in place.values()]
            assert min(r[0] for r in rects) - 1 <= min(xs) and max(xs) <= max(r[2] for r in rects) + 1
            assert min(r[1] for r in rects) - 1 <= min(ys) and max(ys) <= max(r[3] for r in rects) + 1


def test_plano_tecnico_en_pdf_del_tamano_de_la_hoja():
    """El PDF de la lámina no es el A4 vertical de OpenSCAD: la página mide lo que la hoja (A4 o A3
    apaisados), el dibujo va en trazo fino sin relleno y conserva todos los contornos."""
    import re
    from PySide6.QtGui import QGuiApplication
    from scadgui.drawing import generate_technical_drawing_code
    from scadgui.pdfsheet import line_drawing, svg_to_pdf, view_box
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841
    for sheet, (w, h) in (("A4", (297, 210)), ("A3", (420, 297))):
        code = generate_technical_drawing_code("spur_gear_like(); module spur_gear_like() cylinder(h = 10, d = 60);",
                                               sheet_size=sheet, box=((-30, -30, 0), (30, 30, 10)))
        folder = tempfile.mkdtemp()
        src, svg, pdf = (os.path.join(folder, n) for n in ("p.scad", "p.svg", "p.pdf"))
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(code)
        run = subprocess.run([EXE, "-o", svg, src], capture_output=True, text=True, timeout=600)
        assert run.returncode == 0, run.stderr[-800:]
        text = open(svg, encoding="utf-8").read()
        assert view_box(text) == (0, -h, w, h)
        lined = line_drawing(text)
        assert 'fill="none"' in lined and "lightgray" not in lined and lined.count(" z") == text.count(" z")
        svg_to_pdf(svg, pdf, w, h, "Lámina")
        data = open(pdf, "rb").read()
        box = [float(v) for v in re.search(rb"/MediaBox \[([\d. ]+)\]", data).group(1).split()]
        assert abs(box[2] - w * 72 / 25.4) < 1 and abs(box[3] - h * 72 / 25.4) < 1, (sheet, box)


def test_plano_con_lineas_ocultas_de_un_taladro():
    """Con la malla de OpenSCAD de una placa con un taladro vertical, el alzado dibuja el taladro con
    dos líneas ocultas a ±r de su eje en toda la altura y la planta lo ve como un círculo."""
    from scadgui.drawing_lines import mesh_edges, view_lines
    tris = render("$fn = 64; difference() { cube([80, 50, 20]); translate([30, 25, -1]) cylinder(h = 22, d = 16); }")
    me = mesh_edges(tris)
    vis, hid = view_lines(me, tris, "front")
    verticals = [line for line in hid if abs(line[0][0] - line[-1][0]) < 1e-6]
    xs = sorted({round(line[0][0], 2) for line in verticals})
    assert xs == [22.0, 38.0], xs
    for x in xs:
        span = [p[1] for line in verticals if round(line[0][0], 2) == x for p in line]
        assert min(span) < 0.5 and max(span) > 19.5
    vis, hid = view_lines(me, tris, "top")
    ring = [p for line in vis for p in line if math.hypot(p[0] - 30, p[1] - 25) < 8.5]
    assert ring and all(abs(math.hypot(p[0] - 30, p[1] - 25) - 8) < 0.1 for p in ring) and hid == []

if __name__ == "__main__":
    if not EXE:
        print("OpenSCAD no encontrado: se omiten estas pruebas (define OPENSCAD para indicar dónde está)")
        sys.exit(0)
    print("OpenSCAD:", EXE)
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print("FALLA", name, "->", str(exc)[:600])
    sys.exit(1 if failures else 0)
