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
from scadgui.model import Document, generate, make_node  # noqa: E402
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
