"""Pruebas de la geometría del visor (necesitan numpy, no Qt ni OpenSCAD)."""

import math
import os
import struct
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np  # noqa: E402

from scadgui import geometry as g  # noqa: E402
from scadgui.model import Document  # noqa: E402
from scadgui.parser import parse  # noqa: E402


def volume(tris):
    return float(np.einsum("ij,ij->i", tris[:, 0], np.cross(tris[:, 1], tris[:, 2])).sum() / 6)


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def ghosts_of(src):
    doc = parse(src)
    return doc, g.build_ghosts(doc)


def only(gh):
    assert len(gh) == 1, list(gh)
    return next(iter(gh.values()))


def test_volumenes_primitivas():
    _, gh = ghosts_of("cube([40, 30, 10], center = true);")
    assert close(volume(only(gh)), 12000)
    _, gh = ghosts_of("cylinder(h = 12, r = 6, $fn = 64);")
    area = 0.5 * 64 * 36 * math.sin(2 * math.pi / 64)
    assert close(volume(only(gh)), area * 12)
    _, gh = ghosts_of("cylinder(h = 10, r1 = 5, r2 = 0, $fn = 32);")  # cono
    area = 0.5 * 32 * 25 * math.sin(2 * math.pi / 32)
    assert close(volume(only(gh)), area * 10 / 3)
    _, gh = ghosts_of("sphere(r = 10, $fn = 48);")
    v = volume(only(gh))
    assert 0.95 * 4 / 3 * math.pi * 1000 < v < 4 / 3 * math.pi * 1000
    _, gh = ghosts_of("polyhedron(points = [[0,0,0],[10,0,0],[10,10,0],[0,10,0],[5,5,10]], "
                      "faces = [[0,1,4],[1,2,4],[2,3,4],[3,0,4],[1,0,3],[2,1,3]]);")
    assert close(abs(volume(only(gh))), 1000 / 3)


def test_fragmentos_como_openscad():
    assert g.fragments(10, {"fn": 0, "fa": 12, "fs": 2}) == 30
    assert g.fragments(1, {"fn": 0, "fa": 12, "fs": 2}) == 5
    assert g.fragments(1, {"fn": 7}) == 7
    doc = parse("$fn = 16;\ncylinder(h = 1, r = 5);\n")
    tris = only(g.build_ghosts(doc))
    assert len(tris) == 16 * 2 + 14 * 2  # lados + tapas


def test_transformaciones():
    _, gh = ghosts_of("translate([10, 0, 5]) rotate([0, 0, 90]) cube([4, 2, 1]);")
    lo, hi = g.bbox(only(gh))
    assert np.allclose(lo, [8, 0, 5]) and np.allclose(hi, [10, 4, 6])
    _, gh = ghosts_of("mirror([1, 0, 0]) scale([2, 1, 1]) cube(1);")
    lo, hi = g.bbox(only(gh))
    assert np.allclose(lo, [-2, 0, 0]) and np.allclose(hi, [0, 1, 1])
    _, gh = ghosts_of("rotate(90, [1, 0, 0]) cube([1, 2, 3]);")
    lo, hi = g.bbox(only(gh))
    assert np.allclose(lo, [0, -3, 0]) and np.allclose(hi, [1, 0, 2])
    _, gh = ghosts_of("resize([20, 0, 0], auto = true) cube([2, 4, 6]);")
    lo, hi = g.bbox(only(gh))
    assert np.allclose(hi - lo, [20, 40, 60])
    _, gh = ghosts_of("multmatrix([[1,0,0,5],[0,1,0,0],[0,0,1,0],[0,0,0,1]]) cube(1);")
    assert np.allclose(g.bbox(only(gh))[0], [5, 0, 0])


def test_extrusiones():
    _, gh = ghosts_of("linear_extrude(height = 5) square([10, 4]);")
    assert close(volume(only(gh)), 200)
    _, gh = ghosts_of("linear_extrude(height = 5, center = true) translate([2, 0]) circle(r = 3, $fn = 40);")
    tris = only(gh)
    area = 0.5 * 40 * 9 * math.sin(2 * math.pi / 40)
    assert close(volume(tris), area * 5)
    lo, hi = g.bbox(tris)
    assert close(lo[2], -2.5) and close(hi[0], 5)
    _, gh = ghosts_of("linear_extrude(height = 10, twist = 90, scale = 0.5) square(4, center = true);")
    assert volume(only(gh)) > 0
    _, gh = ghosts_of("rotate_extrude($fn = 200) translate([10, 0]) square([2, 4]);")
    v = volume(only(gh))
    assert abs(v - 8 * 2 * math.pi * 11) / v < 0.01  # Pappus
    _, gh = ghosts_of("rotate_extrude(angle = 90, $fn = 40) translate([10, 0]) square([2, 4]);")
    v = volume(only(gh))
    assert abs(v - 8 * 2 * math.pi * 11 / 4) / v < 0.01
    # polígono cóncavo (forma de L)
    _, gh = ghosts_of("linear_extrude(1) polygon([[0,0],[4,0],[4,1],[1,1],[1,3],[0,3]]);")
    assert close(volume(only(gh)), 6)


def test_ids_y_objetivo_de_seleccion():
    doc, gh = ghosts_of(open(os.path.join(os.path.dirname(__file__), "..", "examples",
                                         "placa_agujeros.scad")).read())
    diff = doc.children[0]
    cube, tr = diff.children[0], diff.children[1]
    cyl = tr.children[0]
    assert set(gh) == {cube.id, cyl.id}  # el for es código: sin malla
    assert len(g.collect(doc, gh, [diff.id])) == len(gh[cube.id]) + len(gh[cyl.id])
    doc2 = parse("linear_extrude(3) { square(2); circle(1); }")
    ext = doc2.children[0]
    gh2 = g.build_ghosts(doc2)
    assert set(gh2) == {c.id for c in ext.children}
    assert g.pick_target(doc2, ext.children[1].id) == ext.id


def test_modificadores():
    doc = parse("%cube(1);\n*sphere(2);\ncylinder(h=1, r=1);\n")
    gh = g.build_ghosts(doc)
    assert doc.children[1].id not in gh  # * desactiva
    assert len(g.with_modifier(doc, gh, "%")) == 12


def test_aristas():
    _, gh = ghosts_of("cube(10);")
    assert len(g.feature_edges(only(gh))) == 12
    _, gh = ghosts_of("cylinder(h = 5, r = 3, $fn = 32);")
    assert len(g.feature_edges(only(gh))) == 64  # dos circunferencias, sin líneas en el costado


def test_stl_binario_y_ascii():
    _, gh = ghosts_of("cube([1, 2, 3]);")
    tris = only(gh)
    d = tempfile.mkdtemp()
    binp = os.path.join(d, "a.stl")
    with open(binp, "wb") as fh:
        fh.write(b"\0" * 80 + struct.pack("<I", len(tris)))
        for t in tris:
            fh.write(struct.pack("<3f", 0, 0, 0) + t.astype("<f4").tobytes() + b"\0\0")
    assert np.allclose(g.load_stl(binp), tris)
    ascp = os.path.join(d, "b.stl")
    with open(ascp, "w") as fh:
        fh.write("solid OpenSCAD_Model\n")
        for t in tris:
            fh.write("  facet normal 0 0 0\n    outer loop\n")
            for v in t:
                fh.write(f"      vertex {v[0]:e} {v[1]:e} {v[2]:e}\n")
            fh.write("    endloop\n  endfacet\n")
        fh.write("endsolid OpenSCAD_Model\n")
    assert np.allclose(g.load_stl(ascp), tris)


def test_seleccion_con_rayo():
    doc, gh = ghosts_of("difference() {\n  cube([40, 30, 10], center = true);\n"
                        "  cylinder(h = 12, r = 6, center = true, $fn = 32);\n}\n")
    cube, cyl = doc.children[0].children
    # malla "real" simulada: placa con agujero = cubo menos el cilindro (aprox: paredes del agujero)
    wall = gh[cyl.id][:64]  # costado del cilindro, recortado a la placa
    wall = wall.copy()
    wall[:, :, 2] = np.clip(wall[:, :, 2], -5, 5)
    top = gh[cube.id]
    real = np.concatenate([top, wall])
    picker = g.Picker(real, gh)
    # desde arriba, sobre la placa
    nid, hit = picker.pick([15, 10, 50], [0, 0, -1])
    assert nid == cube.id and np.allclose(hit, [15, 10, 5])
    # mirando la pared del agujero en horizontal desde el centro
    nid, hit = picker.pick([0, 0, 0], [1, 0, 0])
    assert nid == cyl.id and 5.9 < hit[0] < 6.01
    # al vacío
    assert picker.pick([100, 100, 50], [0, 0, -1]) == (None, None)
    # sin malla real (OpenSCAD no disponible): gana la pieza más cercana
    nid, _ = g.Picker(None, gh).pick([0, 0, 50], [0, 0, -1])
    assert nid == cyl.id


def test_valores_no_literales_no_rompen():
    doc = parse("lado = 3;\ncube(lado);\ntranslate([lado, 0, 0]) sphere(1);\ncylinder(h = 2 * lado, r = 1);\n")
    gh = g.build_ghosts(doc)
    assert gh == {}
    assert len(g.collect(doc, gh, [n.id for n in doc.children])) == 0


def test_todos_los_comandos_por_defecto():
    from scadgui.catalog import SPECS
    from scadgui.model import make_node
    doc = Document()
    for name, spec in SPECS.items():
        node = make_node(name)
        if spec.container:
            child = "square" if spec.category in ("extrude", "shape2d") or name in ("fill", "roof") else "cube"
            node.children.append(make_node(child))
        doc.children.append(node)
    gh = g.build_ghosts(doc)
    assert len(gh) >= 25
    for tris in gh.values():
        assert tris.shape[1:] == (3, 3) and np.isfinite(tris).all()


def test_iluminacion_sin_caras_oscuras():
    _, gh = ghosts_of("cube(10);")
    tris = only(gh)
    out = g.shade(g.face_normals(tris), np.tile(g.DEFAULT_COLOR, (len(tris), 1)))
    k = out[:, 0] / g.DEFAULT_COLOR[0]
    assert k.min() >= 0.39 and k.max() <= 1.3
    top = np.nonzero(g.face_normals(tris)[:, 2] > 0.9)[0]
    assert k[top].min() > 0.75  # la cara de arriba se ve clara
    # caras con orientación distinta tienen tonos distintos
    assert len(set(np.round(k, 3))) >= 4


def test_colores():
    assert g.parse_color("red") == (1, 0, 0, 1)
    assert g.parse_color("#ff8000") == (1.0, 128 / 255, 0, 1)
    assert g.parse_color("#f80") == (1.0, 136 / 255, 0, 1)
    assert g.parse_color([0.2, 0.4, 0.6], 0.5) == (0.2, 0.4, 0.6, 0.5)
    assert g.parse_color("rarísimo") is None
    assert g.parse_color("Chartreuse", resolve=lambda n: (0.5, 1, 0) if n == "Chartreuse" else None) == (0.5, 1, 0, 1)
    doc = parse('color("red") { cube(1); color("blue") sphere(1); }\ncylinder(h=1, r=1);\n')
    cols = g.node_colors(doc)
    red = doc.children[0]
    assert cols[red.children[0].id] == (1, 0, 0, 1)
    assert cols[red.children[1].children[0].id] == (0, 0, 1, 1)  # el más cercano gana
    assert cols[doc.children[1].id] == g.DEFAULT_COLOR


def test_off_con_y_sin_colores():
    d = tempfile.mkdtemp()
    p1 = os.path.join(d, "a.off")
    with open(p1, "w") as fh:
        fh.write("OFF\n5 2 0\n0 0 0\n1 0 0\n1 1 0\n0 1 0\n0 0 1\n4 0 1 2 3\n3 0 1 4\n")
    tris, cols = g.load_off(p1)
    assert tris.shape == (3, 3, 3) and cols is None
    p2 = os.path.join(d, "b.off")
    with open(p2, "w") as fh:
        fh.write("OFF 4 2 0\n0 0 0\n1 0 0\n1 1 0\n0 0 1\n3 0 1 2 255 0 0 255\n3 0 1 3 0.0 0.5 1.0 1.0\n")
    tris, cols = g.load_off(p2)
    assert np.allclose(cols, [[1, 0, 0, 1], [0, 0.5, 1, 1]])
    assert g.load_mesh(p2)[0].shape == (2, 3, 3)


def test_caras_de_la_malla_real_se_asignan_a_su_pieza():
    doc, gh = ghosts_of('difference() {\n  color("red") cube([40, 30, 10], center = true);\n'
                        '  color("blue") cylinder(h = 12, r = 6, center = true, $fn = 32);\n}\n')
    cube = doc.children[0].children[0].children[0]
    cyl = doc.children[0].children[1].children[0]
    # malla real simulada: caras de la placa + pared del agujero (recortada al grosor de la placa)
    wall = gh[cyl.id][:64].copy()
    wall[:, :, 2] = np.clip(wall[:, :, 2], -5, 5)
    real = np.concatenate([gh[cube.id], wall[:, ::-1]])  # pared con normales hacia dentro
    owner = g.assign_faces(real, gh)
    assert (owner[:12] == cube.id).all() and (owner[12:] == cyl.id).all()
    cols = g.colored(real, owner, g.node_colors(doc))
    assert (cols[:12, 0] > cols[:12, 2]).all()      # placa rojiza
    assert (cols[12:, 2] > cols[12:, 0]).all()      # agujero azulado
    tris, cols = g.ghost_colors(gh, g.node_colors(doc))
    assert len(tris) == len(cols) == len(gh[cube.id]) + len(gh[cyl.id])


def test_vista_explosionada():
    doc = parse("union() {\n  translate([-30, 0, 0]) cube(10, center = true);\n"
                "  difference() {\n    translate([30, 0, 0]) cube(10, center = true);\n"
                "    translate([30, 0, 0]) cylinder(h = 12, r = 2, center = true);\n  }\n}\n")
    union = doc.children[0]
    left, right_part = union.children
    parts = g.assembly_parts(doc)        # se baja del union único: sus hijos son las piezas
    hole = right_part.children[1].children[0]
    assert parts[hole.id] == right_part.id and parts[left.children[0].id] == left.id
    assert hole.id in g.subtracted_ids(doc) and left.id not in g.subtracted_ids(doc)
    gh = g.build_ghosts(doc)
    tris = np.concatenate([gh[left.children[0].id], gh[right_part.children[0].children[0].id]])
    face_parts = np.array([left.id] * 12 + [right_part.id] * 12)
    off = g.explosion_offsets(tris, face_parts, 0.5)
    diag = float(np.linalg.norm(np.subtract(*g.bbox(tris)[::-1])))
    assert off[left.id][0] < 0 < off[right_part.id][0]
    assert abs(np.linalg.norm(off[left.id]) - 0.5 * diag) < 1e-9   # proporcional al tamaño
    moved = g.apply_offsets(tris, face_parts, off)
    assert np.allclose(moved[:12] - tris[:12], off[left.id])
    assert g.explosion_offsets(tris, face_parts, 0) == {}



def test_matrices_repiten_la_pieza():
    doc, gh = ghosts_of("for (i = [0 : 3]) translate(i * [20, 0, 0]) cube(10);")
    tris = only(gh)
    assert len(tris) == 4 * 12
    lo, hi = g.bbox(tris)
    assert np.allclose(lo, [0, 0, 0]) and np.allclose(hi, [70, 10, 10])
    # todas las copias pertenecen al cube: al hacer clic en cualquiera se selecciona el cube
    assert next(iter(gh)) == doc.children[0].children[0].id


def test_matriz_polar_y_rectangular():
    _, gh = ghosts_of("for (i = [0 : 3]) rotate(a = i * 90, v = [0, 0, 1]) translate([20, 0, 0]) cube(2, center = true);")
    lo, hi = g.bbox(only(gh))
    assert np.allclose(lo, [-21, -21, -1]) and np.allclose(hi, [21, 21, 1])
    _, gh = ghosts_of("for (i = [0 : 2], j = [0 : 1]) translate(i * [10, 0, 0] + j * [0, 5, 0]) cube(1);")
    tris = only(gh)
    assert len(tris) == 6 * 12
    assert np.allclose(g.bbox(tris)[1], [21, 6, 1])


def test_matriz_2d_dentro_de_extrusion_y_con_variables():
    _, gh = ghosts_of("linear_extrude(2) for (i = [0 : 2]) translate(i * [10, 0, 0]) square(4);")
    assert np.allclose(g.bbox(only(gh))[1], [24, 4, 2])
    # con una variable no se sabe cuántas copias hay: se dibuja solo la primera
    _, gh = ghosts_of("for (i = [0 : n - 1]) translate(i * [10, 0, 0]) cube(1);")
    assert np.allclose(g.bbox(only(gh))[1], [1, 1, 1])



def test_malla_de_cubo_con_aristas():
    ctx = {"fn": 64, "fa": 12, "fs": 2}
    t = g.cube_edges({"size": [40, 30, 10], "edges": ["y0z1", "x1y1", "x0z0"], "chamfer": 2}, ctx)
    assert abs(g.signed_volume(t) - (12000 - 2 * (40 + 10 + 30))) < 1e-6   # cada chaflán quita r²/2 · largo
    t = g.cube_edges({"size": [40, 30, 10], "edges": ["x1y1"], "rounding": 3}, ctx)
    n = 16  # $fn = 64 → el cuarto de círculo tiene 16 tramos, como en OpenSCAD
    removed = 9 - n * 0.5 * 9 * math.sin(math.pi / 2 / n)   # cuadrado r² menos el sector poligonal
    assert abs(g.signed_volume(t) - (12000 - removed * 10)) < 1e-4
    t = g.cube_edges({"size": [40, 30, 10], "center": True, "edges": [], "rounding": 3}, ctx)
    assert np.allclose(g.bbox(t)[0], [-20, -15, -5]) and abs(g.signed_volume(t) - 12000) < 1e-6


def test_malla_de_cilindro_con_bordes():
    ctx = {"fn": 64, "fa": 12, "fs": 2}
    t = g.cylinder_edges({"h": 20, "r": 8, "center": True, "edges": ["top"], "chamfer": 2}, ctx)
    lo, hi = g.bbox(t)
    assert g.signed_volume(t) > 0 and np.isclose(lo[2], -10) and np.isclose(hi[2], 10)
    full = g.signed_volume(g.cylinder({"h": 20, "r": 8}, ctx))
    assert 0 < full - g.signed_volume(t) < math.pi * 2 * 8 * 2  # se quita un anillo pequeño


def test_aristas_elegibles_en_el_mundo():
    doc = parse("translate([100, 0, 0]) cube([10, 20, 30]);\n"
                "for (i = [0 : 1]) translate(i * [0, 50, 0]) cylinder(h = 5, r = 3);\n"
                "linear_extrude(3) square(4);\n"
                "hull() cube(1);\n")
    edges = g.pickable_edges(doc)
    cube_id = doc.children[0].children[0].id
    by_key = {(e[0], e[1]): e[2] for e in edges if e[0] == cube_id}
    assert len(by_key) == 12 and np.allclose(by_key[(cube_id, "x1y1")], [[110, 20, 0], [110, 20, 30]])
    cyl_edges = [e for e in edges if e[0] != cube_id]
    assert len(cyl_edges) == 4 and {e[1] for e in cyl_edges} == {"top", "bottom"}   # dos copias × 2 bordes
    assert 52.5 < max(e[2][:, 1].max() for e in cyl_edges) <= 53 + 1e-9   # la copia está en y = 50


def test_elegir_arista_con_el_raton():
    doc = parse("cube([10, 20, 30]);")
    edges = g.pickable_edges(doc)
    mesh = g.build_ghosts(doc)[doc.children[0].id]
    pick = lambda o, d, tol=0.01: (lambda i: None if i is None else edges[i][1])(
        g.pick_edge(edges, np.array(o, float), np.array(d, float), tol, mesh))
    assert pick([5, 20.1, 100], [0, 0, -1]) == "y1z1"           # desde arriba, junto a la arista de atrás
    assert pick([100, 0.1, 15], [-1, 0, 0]) == "x1y0"           # desde +X, la arista de delante
    assert pick([5, 10, 100], [0, 0, -1]) is None               # en mitad de la cara: ninguna
    corner = np.array([10, 20, 15.0])
    eye = np.array([100, 110, 15.0])
    assert pick(eye, (corner - eye) / np.linalg.norm(corner - eye)) == "x1y1"   # la esquina vista en diagonal
    # desde +X, apuntando a la arista de atrás (x0y0) a través de la pieza: está tapada
    assert pick([100, 0.05, 15], [-1, 0, 0]) == "x1y0"
    hidden = np.array([0, 0.0, 15.0])
    eye = np.array([100, 2.0, 15.0])
    assert pick(eye, (hidden - eye) / np.linalg.norm(hidden - eye), 0.001) is None



def test_regla_paso_redondo_y_marcas():
    from scadgui.geometry import nice_step, ruler
    assert [nice_step(s) for s in (8, 80, 150, 400, 0.9)] == [1, 10, 20, 50, 0.2]
    r = ruler(100)                      # paso 20: números cada 20 mm, marcas cortas cada 2 mm
    assert r["major"] == 20 and r["extent"] == 80
    texts = {t for axis, _p, t, negative in r["labels"] if axis == 0 and not negative}
    assert texts == {"20", "40", "60", "80"}
    x_pos = r["pos"][0]
    assert len(x_pos) == 1 + 40          # el eje y una marca cada 2 mm hasta 80
    assert np.allclose(x_pos[0], [[0, 0, 0], [80, 0, 0]])
    long_ticks = [s for s in x_pos[1:] if np.isclose(np.linalg.norm(s[1] - s[0]), 20 * 0.35)]
    assert len(long_ticks) == 4 and all(s[1][1] < 0 for s in long_ticks)   # marcas de X hacia -Y
    assert all(seg[1][0] <= 0 for seg in r["neg"][0])                       # lado negativo
    assert any(t == "-80" for axis, _p, t, negative in r["labels"] if axis == 2 and negative)


def test_punta_de_flecha_del_gizmo():
    from scadgui.geometry import arrow_cone, signed_volume
    cone = arrow_cone([0, 0, 10], [0, 0, 1], 3.0, 1.0, n=64)
    assert np.isclose(cone[..., 2].max(), 10) and np.isclose(cone[..., 2].min(), 7)
    assert abs(signed_volume(cone) - math.pi * 1.0 ** 2 * 3.0 / 3) < 0.01      # cerrado y hacia fuera
    tilted = arrow_cone([5, 5, 5], [1, 1, 0], 2.0, 0.5)
    assert signed_volume(tilted) > 0


def test_indice_de_rayos_igual_que_recorrer_todo():
    """RayIndex da lo mismo que comparar el rayo con todos los triángulos."""
    from scadgui.geometry import RayIndex, ray_hits
    rng = np.random.default_rng(7)
    tris = rng.random((3000, 1, 3)) * 100 + (rng.random((3000, 3, 3)) - 0.5) * 4
    index = RayIndex(tris)
    origin = np.array([250.0, -250.0, 200.0])
    for _ in range(60):
        point = rng.random(3) * 120 - 10
        t = ray_hits(origin, point - origin, tris)
        assert index.blocked(origin, point) == bool(np.any((t > 1e-3) & (t < 1 - 1e-3)))
    assert not RayIndex(np.zeros((0, 3, 3))).blocked(origin, [0, 0, 0])


def test_caras_sin_color_siguen_al_esquema():
    """En un OFF con unas caras rojas y otras sin color, las sin color toman el color por defecto
    que haya al pintar (el del esquema), aunque cambie después de leer el archivo."""
    import tempfile
    from scadgui import geometry as geo
    path = os.path.join(tempfile.mkdtemp(), "m.off")
    with open(path, "w") as fh:
        fh.write("OFF\n4 2 0\n0 0 0\n1 0 0\n0 1 0\n0 0 1\n3 0 1 2 255 0 0\n3 0 1 3\n")
    tris, cols = geo.load_off(path)
    before = geo.DEFAULT_COLOR
    try:
        geo.set_default_color((0.0, 0.0, 1.0, 1.0))
        base = geo.colored(tris, None, {}, cols)
        assert base[0][0] > base[0][2] and base[1][2] > base[1][0]   # roja / azul (la por defecto)
    finally:
        geo.set_default_color(before)


def _inside(points, poly) -> np.ndarray:
    """Qué puntos caen dentro del polígono (regla par-impar)."""
    x, y = points[:, 0][:, None], points[:, 1][:, None]
    x1, y1 = poly[:, 0][None, :], poly[:, 1][None, :]
    x2, y2 = np.roll(poly[:, 0], -1)[None, :], np.roll(poly[:, 1], -1)[None, :]
    cross = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / np.where(y2 == y1, 1e-12, y2 - y1) + x1)
    return cross.sum(axis=1) % 2 == 1


def test_engranaje_diametros_y_simetria():
    from scadgui import gears
    d = gears.dims(2, 20)
    assert (d["pitch_d"], d["tip_d"], d["root_d"]) == (40, 44, 35.0)
    assert [gears.min_teeth(a) for a in (14.5, 20, 25)] == [32, 18, 12]      # Machinery's Handbook
    poly = gears.polygon(2, 20)
    r = np.linalg.norm(poly, axis=1)
    assert np.isclose(r.max(), 22) and np.isclose(r.min(), 17.5)
    mirrored = poly * [1, -1]                                                   # diente centrado en +X
    assert all(np.min(np.linalg.norm(poly - q, axis=1)) < 1e-9 for q in mirrored)
    assert gears.center_distance(2, 20, 30) == 50


def test_pareja_de_engranajes_no_se_solapa_al_girar():
    """Dos engranajes a m·(z1+z2)/2, girando juntos un paso de diente: ningún vértice de uno entra
    en el otro (con 0.1 mm de holgura). Con pocos dientes (socavado) sí interfieren."""
    from scadgui import gears

    def interferes(m, z1, z2, backlash):
        a = gears.center_distance(m, z1, z2)
        p1, p2 = gears.polygon(m, z1, 20, backlash), gears.polygon(m, z2, 20, backlash)
        for k in range(25):
            t = math.radians(k / 24 * 360 / z1)
            u = math.radians(gears.mesh_rotation(z2)) - t * z1 / z2
            r1 = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])
            r2 = np.array([[math.cos(u), -math.sin(u)], [math.sin(u), math.cos(u)]])
            a1, a2 = p1 @ r1.T, p2 @ r2.T + [a, 0]
            if _inside(a2, a1).any() or _inside(a1, a2).any():
                return True
        return False
    for m, z1, z2 in ((2, 20, 20), (1, 18, 31), (1.5, 19, 40), (3, 24, 25)):
        assert not interferes(m, z1, z2, 0.1), (m, z1, z2)
    assert interferes(2, 8, 30, 0.0)                         # 8 dientes: socavado, interfiere


def test_engranaje_en_la_vista_aproximada():
    from scadgui.parser import parse
    from scadgui import geometry as geo
    doc = parse("spur_gear(mod = 2, teeth = 20, thickness = 6, center = true);")
    tris = next(iter(geo.build_ghosts(doc).values()))
    assert np.isclose(tris[..., 2].min(), -3) and np.isclose(tris[..., 2].max(), 3)
    assert geo.signed_volume(tris) > 0

if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                failures += 1
                print("FALLA", name, "->", repr(exc))
    sys.exit(1 if failures else 0)
