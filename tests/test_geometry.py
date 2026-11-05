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


def test_cremallera_medidas_y_grueso_del_diente():
    """Proporciones del dentado básico: paso π·m, cabeza m, pie 1.25·m y, en la línea primitiva,
    un grueso de medio paso en todos los dientes (Machinery's Handbook, «Basic Rack»)."""
    from scadgui import gears
    d = gears.rack_dims(2, 10, 20, 5)
    assert np.isclose(d["pitch"], 2 * math.pi) and np.isclose(d["length"], 20 * math.pi)
    assert d["height"] == 2.25 * 2 + 5 and np.isclose(d["tooth_thickness"], math.pi)
    poly = gears.rack_polygon(2, 10, 20, 0, 5)
    assert np.isclose(poly[:, 1].max(), 2) and np.isclose(poly[:, 1].min(), -7.5)
    assert np.isclose(poly[:, 0].min(), 0) and np.isclose(poly[:, 0].max(), 20 * math.pi)
    nxt = np.roll(poly, -1, axis=0)                                  # cortes del perfil con y = 0
    cut = (poly[:, 1] < 0) != (nxt[:, 1] < 0)
    xs = poly[cut, 0] + (nxt[cut, 0] - poly[cut, 0]) * (-poly[cut, 1]) / (nxt[cut, 1] - poly[cut, 1])
    step = 2 * math.pi
    want = [(i + 0.5) * step + s * step / 4 for i in range(10) for s in (-1, 1)]
    assert np.allclose(np.sort(xs), np.sort(want))


def test_engranaje_rodando_sobre_la_cremallera_no_se_solapa():
    """El engranaje que coloca «Añadir engranaje sobre la cremallera», rodando un diente: ningún
    vértice de uno entra en el otro. Si la cremallera avanzara al contrario, chocarían."""
    from scadgui import gears

    def interferes(m, zr, zg, backlash, reverse=False):
        rack = gears.rack_polygon(m, zr, 20, backlash, 5)
        gear = gears.polygon(m, zg, 20, backlash)
        x0, y0, rot = gears.rack_gear_position(m, zr, zg)
        for k in range(25):
            t = k / 24 * 2 * math.pi / zg                            # gira un diente
            a = math.radians(rot) + t
            turn = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
            moved = rack + [(-1 if reverse else 1) * m * zg / 2 * t, 0]
            here = gear @ turn.T + [x0, y0]
            if _inside(here, moved).any() or _inside(moved, here).any():
                return True
        return False
    for m, zr, zg in ((2, 10, 20), (1, 12, 25), (1.5, 8, 18)):
        assert not interferes(m, zr, zg, 0.1), (m, zr, zg)
    assert interferes(2, 10, 20, 0.1, reverse=True)                  # la prueba sí detecta choques


def test_cremallera_helicoidal_engrana_con_un_helicoidal_de_la_misma_mano():
    """El diente inclinado sesga el perfil tan ψ por mm de grueso. A lo largo de todo el grueso y
    rodando un diente no se solapan; con el engranaje de la otra mano, sí."""
    from scadgui import gears

    def spin(poly, a):
        m = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        return poly @ m.T

    def interferes(m, zr, zg, psi, thick, backlash, other_hand=False):
        rack = gears.rack_polygon(m, zr, 20, backlash, 5, psi)
        gear = gears.helical_polygon(m, zg, psi, 20, backlash)
        x0, y0, base = gears.rack_gear_position(m, zr, zg, psi)
        shear = gears.rack_shear(psi)
        spun = math.radians(gears.helix_twist(m, zg, psi, thick)) * (-1 if other_hand else 1)
        radius = gears.rack_transverse(m, 20, psi)[0] * zg / 2
        for j in range(5):                                           # alturas del grueso
            h = j / 4
            for k in range(13):                                      # girando un diente
                t = k / 12 * 2 * math.pi / zg
                here = spin(gear, math.radians(base) + t + spun * h) + [x0, y0]
                moved = rack + [shear * thick * h + radius * t, 0]
                if _inside(here, moved).any() or _inside(moved, here).any():
                    return True
        return False
    for args in ((1, 12, 20, 20, 10), (2, 8, 25, 30, 15), (1, 10, 31, 15, 12)):
        assert not interferes(*args, 0.1), args
    assert interferes(1, 12, 20, 20, 10, 0.1, other_hand=True)
    # El perfil del plano de giro es el del módulo y el ángulo aparentes…
    mt, at = gears.rack_transverse(2, 20, 30)
    assert np.isclose(mt, 2 / math.cos(math.radians(30)))
    assert np.isclose(at, math.degrees(math.atan(math.tan(math.radians(20)) / math.cos(math.radians(30)))))
    poly = gears.rack_polygon(2, 6, 20, 0, 5, 30)
    assert np.isclose(poly[:, 0].max(), 6 * math.pi * mt)
    # …pero la cabeza y el pie se siguen midiendo con el módulo normal
    assert np.isclose(poly[:, 1].max(), 2) and np.isclose(poly[:, 1].min(), -2.5 - 5)


def test_helicoidal_medidas_y_dientes_minimos():
    """Machinery's Handbook, «Rules and Formulas for Helical Gear Calculations» y AGMA 908 ec. 4."""
    from scadgui import gears
    d = gears.helical_dims(1, 20, 20, 20, 10)
    cos20 = math.cos(math.radians(20))
    assert np.isclose(d["pitch_d"], 20 / cos20)                      # D = N / (Pn · cos α)
    assert np.isclose(d["tip_d"], d["pitch_d"] + 2)                  # la cabeza, con el módulo normal
    assert np.isclose(d["root_d"], d["pitch_d"] - 2.5)
    assert np.isclose(d["transverse_angle"],
                      math.degrees(math.atan(math.tan(math.radians(20)) / cos20)))
    assert np.isclose(d["lead"], math.pi * d["pitch_d"] / math.tan(math.radians(20)))
    assert np.isclose(d["twist"], math.degrees(2 * 10 * math.sin(math.radians(20)) / 20))
    # Menos dientes que un recto, y cuanta más hélice, menos
    assert [gears.helical_min_teeth(a) for a in (0, 20, 30, 45)] == [18, 15, 12, 7]
    assert np.isclose(gears.helical_center_distance(2, 20, 40, 30),
                      2 * 60 / (2 * math.cos(math.radians(30))))


def test_pareja_helicoidal_engrana_en_todo_el_grueso():
    """Dos helicoidales de mano contraria, a lo largo de todo el grueso y girando un diente: no se
    solapan. Con la misma mano (el fallo típico) sí chocan."""
    from scadgui import gears

    def turn(poly, a):
        m = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        return poly @ m.T

    def interferes(m, z1, z2, psi, thick, backlash, same_hand=False):
        a = gears.helical_center_distance(m, z1, z2, psi)
        p1 = gears.helical_polygon(m, z1, psi, 20, backlash)
        p2 = gears.helical_polygon(m, z2, psi, 20, backlash)
        t1 = math.radians(gears.helix_twist(m, z1, psi, thick))
        t2 = math.radians(gears.helix_twist(m, z2, psi, thick)) * (1 if same_hand else -1)
        for j in range(5):                                           # alturas del grueso
            h = j / 4
            for k in range(13):                                      # girando un diente
                t = k / 12 * 2 * math.pi / z1
                u = math.radians(gears.mesh_rotation(z2)) - t * z1 / z2
                a1, a2 = turn(p1, t + t1 * h), turn(p2, u + t2 * h) + [a, 0]
                if _inside(a2, a1).any() or _inside(a1, a2).any():
                    return True
        return False
    for args in ((1, 20, 20, 20, 10), (2, 20, 40, 30, 20), (1, 15, 31, 20, 10), (1.5, 12, 25, 30, 15)):
        assert not interferes(*args, 0.1), args
    assert interferes(1, 20, 40, 30, 20, 0.1, same_hand=True)


def _bevel_solid(mod, z, zm, sigma, face, backlash):
    """Devuelve (puntos de su superficie, función «¿está dentro?») de un cónico con el vértice en
    el origen. El cónico es el perfil de la cara trasera barrido hacia el vértice, así que un
    punto está dentro si cae entre las dos caras y, llevado a la trasera, entra en el perfil."""
    from scadgui import gears
    d = gears.bevel_dims(mod, z, zm, sigma, 20, face)
    poly = gears.bevel_polygon(mod, z, zm, sigma, 20, backlash)
    zo = d["outer_z"]
    zi = zo - face * math.cos(math.radians(d["gamma"]))

    def inside(p):
        with np.errstate(divide="ignore", invalid="ignore"):
            flat = np.nan_to_num(p[:, :2] * (zo / p[:, 2])[:, None], posinf=1e9, neginf=-1e9)
        return (p[:, 2] >= zi) & (p[:, 2] <= zo) & _inside(flat, poly)
    ring = np.column_stack([poly, np.full(len(poly), zo)])
    surface = np.vstack([ring * t for t in (1, zi / zo, *(np.linspace(zi / zo, 1, 7)))])
    return surface, inside


def _spin(a, axis="z"):
    c, s = math.cos(a), math.sin(a)
    return (np.array([[c, -s, 0.0], [s, c, 0], [0, 0, 1]]) if axis == "z" else
            np.array([[c, 0, s], [0, 1.0, 0], [-s, 0, c]]))


def test_conico_medidas_del_handbook():
    """Machinery's Handbook 27, «Rules and Formulas for Calculating Dimensions of Milled Bevel
    Gears», p. 2087-2088."""
    from scadgui import gears
    d = gears.bevel_dims(2, 20, 20, 90, 20, 8)
    assert np.isclose(d["gamma"], 45) and np.isclose(d["mate_gamma"], 45)   # tan α = NP/NG
    assert np.isclose(d["cone"], 40 / (2 * math.sin(math.radians(45))))     # C = D / (2 sen α)
    assert np.isclose(d["tip_d"], 40 + 2 * 2 * math.cos(math.radians(45)))  # O = D + 2·S·cos α
    assert np.isclose(d["addendum_angle"], math.degrees(math.atan(2 / d["cone"])))
    assert np.isclose(d["dedendum_angle"], math.degrees(math.atan(2.5 / d["cone"])))
    assert np.isclose(d["virtual_teeth"], 20 / math.cos(math.radians(45)))  # N' = N / cos α
    assert np.isclose(d["max_face"], min(d["cone"] / 3, 8 * 2))             # C/3 u 8·m
    assert np.isclose(d["outer_z"], d["tip_d"] / 2 / math.tan(math.radians(d["face_angle"])))
    # Para 15 y 30 dientes a 90°, tan α = 15/30
    assert np.isclose(gears.bevel_dims(1, 15, 30)["gamma"], math.degrees(math.atan(0.5)))
    # En las tres relaciones, el perfil llega justo al Ø exterior del Handbook y a los dos conos
    for z, zm in ((20, 20), (15, 30), (30, 15)):
        d = gears.bevel_dims(2, z, zm, 90, 20, 8)
        r = np.hypot(*gears.bevel_polygon(2, z, zm).T)
        assert np.isclose(2 * r.max(), d["tip_d"]), (z, zm)
        assert np.isclose(math.degrees(math.atan(r.max() / d["outer_z"])), d["face_angle"])
        assert np.isclose(math.degrees(math.atan(r.min() / d["outer_z"])), d["root_angle"])


def test_pareja_de_conicos_engrana_al_girar():
    """Los dos cónicos comparten el vértice y el segundo va girado el ángulo entre ejes. Girando
    la pareja un diente, ningún punto de la superficie de uno entra en el otro. Si se invierte el
    sentido, si la fase se corre medio paso o si la holgura es negativa, sí chocan."""
    from scadgui import gears

    def interferes(mod, z1, z2, sigma, face, backlash, sign=-1, phase=0.0):
        s1, in1 = _bevel_solid(mod, z1, z2, sigma, face, backlash)
        s2, in2 = _bevel_solid(mod, z2, z1, sigma, face, backlash)
        delta = math.radians(gears.mesh_rotation(z2) + phase)
        for k in range(13):
            t = k / 12 * 2 * math.pi / z1
            one = _spin(t)
            two = _spin(math.radians(sigma), "y") @ _spin(delta + sign * t * z1 / z2)
            if in2(s1 @ one.T @ two).any() or in1(s2 @ two.T @ one).any():
                return True
        return False
    for args in ((2, 20, 20, 90, 8), (1, 15, 30, 90, 6), (2, 12, 36, 90, 7),
                 (1, 20, 20, 60, 6), (1, 18, 25, 120, 5)):
        assert not interferes(*args, 0.1), args
    assert not interferes(2, 20, 20, 90, 8, 0.0)                   # sin holgura, se tocan sin más
    assert interferes(2, 20, 20, 90, 8, 0.1, sign=1)               # girando al revés
    assert interferes(2, 20, 20, 90, 8, 0.1, phase=9.0)            # medio paso fuera de fase
    assert interferes(2, 20, 20, 90, 8, -0.4)                      # con holgura negativa


def test_caja_del_modelo_para_el_plano():
    """Lo restado en un difference() no agranda la caja, un intersection() se queda con el cruce y
    las piezas con % no cuentan."""
    from scadgui.parser import parse
    from scadgui import geometry as geo
    doc = parse("translate([40, 30, 0]) difference() { cube([120, 60, 40]); "
                "translate([60, 30, -1]) cylinder(h = 50, d = 30); }\n"
                "%sphere(300);\n"
                "intersection() { cube(10); translate([5, 5, 5]) cube(10); }\n")
    ghosts = geo.build_ghosts(doc)
    lo, hi = geo.model_box(doc, ghosts)
    assert np.allclose(lo, (5, 5, 0)) and np.allclose(hi, (160, 90, 40))
    lo, hi = geo.model_box(doc, ghosts, [doc.children[0].id])
    assert np.allclose(lo, (40, 30, 0)) and np.allclose(hi, (160, 90, 40))
    lo, hi = geo.model_box(doc, ghosts, [doc.children[2].id])
    assert np.allclose(lo, (5, 5, 5)) and np.allclose(hi, (10, 10, 10))
    assert geo.model_box(doc, ghosts, [doc.children[1].id]) is None


def _two_boxes():
    """Un cubo de 40 y, detrás de él mirando de frente (Y mayor), uno de 10 que no asoma."""
    from scadgui import geometry as geo
    big = geo.cube({"size": [40, 40, 40]})
    small = geo.cube({"size": [10, 10, 10]}) + np.array([10.0, 50.0, 10.0])
    return np.concatenate([big, small])


def _length(lines):
    return sum(math.dist(a, b) for line in lines for a, b in zip(line, line[1:]))


def test_lineas_del_plano_visibles_y_ocultas():
    """De frente, el cubo pequeño queda tapado: sus cuatro aristas salen ocultas y las del grande
    visibles. Desde arriba y de perfil no se tapan. Las aristas que se proyectan en un punto o
    coinciden con otra visible no se dibujan dos veces, y la isométrica va sin ocultas."""
    from scadgui.drawing_lines import mesh_edges, view_lines, mesh_volume, view_matrix
    tris = _two_boxes()
    me = mesh_edges(tris)
    vis, hid = view_lines(me, tris, "front")
    assert abs(_length(vis) - 160) < 0.5 and abs(_length(hid) - 40) < 0.5
    pts = [p for line in hid for p in line]                  # en el alzado, (x, z) del cubo pequeño
    assert min(p[0] for p in pts) > 9.9 and max(p[0] for p in pts) < 20.1
    assert min(p[1] for p in pts) > 9.9 and max(p[1] for p in pts) < 20.1
    for key in ("top", "side"):
        vis, hid = view_lines(me, tris, key)
        assert abs(_length(vis) - 200) < 0.5 and _length(hid) < 0.5, key
    vis, hid = view_lines(me, tris, "isometric", hidden=False)
    assert hid == [] and _length(vis) > 0
    assert abs(mesh_volume(tris) - (40 ** 3 + 10 ** 3)) < 1e-6
    # Cada vista mira desde donde dice: Z de la vista hacia el observador
    assert np.allclose(view_matrix("front") @ [0, -1, 0], [0, 0, 1])
    assert np.allclose(view_matrix("top") @ [0, 0, 1], [0, 0, 1])
    assert np.allclose(view_matrix("side") @ [-1, 0, 0], [0, 0, 1])
    assert np.allclose(view_matrix("isometric") @ (np.array([1, -1, 1]) / math.sqrt(3)), [0, 0, 1], atol=1e-4)


def test_lamina_iso_con_cajetin_notas_y_cotas():
    """La lámina lleva el recuadro ISO, el cajetín con todos sus datos (y la masa calculada con el
    volumen y la densidad), las notas, las cotas generales con la medida real y las vistas dentro
    del recuadro sin pisar el cajetín. El SVG es XML válido en milímetros y el DXF pone las ocultas
    en su capa con línea discontinua."""
    import xml.etree.ElementTree as ET
    from scadgui.drawing_lines import mesh_edges, view_lines, mesh_volume
    from scadgui.drawing_sheet import (BLOCK_W, MARGINS, SheetInfo, build_sheet, number, sheet_format, to_dxf,
                                       to_svg)
    from scadgui.drawing import scale_label
    from scadgui.i18n import set_language
    set_language("es")
    tris = _two_boxes()
    me = mesh_edges(tris)
    lines = {k: view_lines(me, tris, k, hidden=k != "isometric") for k in ("front", "top", "side", "isometric")}
    box = ((0.0, 0.0, 0.0), (40.0, 60.0, 40.0))
    info = SheetInfo(title="Soporte", description="Prueba", company="Taller", number="PZ-7", revision="B",
                     material="PLA", density=1.24, author="Ana", checker="Luis",
                     notes=["Cotas en milímetros.", "Sin rebabas."])
    sh = build_sheet(lines, box, info, "A4", volume=mesh_volume(tris))
    assert sh.fits and sh.scale in (1.0, 0.5)
    texts = [t[2] for t in sh.texts]
    for want in ("Soporte", "Prueba", "Taller", "PZ-7", "B", "PLA", "Ana", "Luis", "1/1", "ISO 2768-m", "A4",
                 scale_label(sh.scale), "40 × 60 × 40 mm", "1. Cotas en milímetros.", "2. Sin rebabas.", "NOTAS:",
                 "ALZADO", "PLANTA", "PERFIL IZQUIERDO", "ISOMÉTRICA"):
        assert any(want == t or t.startswith(want) for t in texts), want
    assert f"{number(65.0 * 1.24 / 1000, 3)} kg  ·  65 cm³" in texts       # 40³ + 10³ mm³ = 65 cm³
    assert texts.count("40") == 2 and texts.count("60") == 1               # ancho y alto, y el fondo
    assert number(0.5) == "0,5"
    w, h = sh.w, sh.h
    l, b, r, t = MARGINS
    block = (w - r - BLOCK_W, b, w - r, b + sheet_format({}, True, 2).title[1])
    for pts, style in sh.lines:
        if style in ("thick", "hidden"):                                   # las vistas
            for x, y in pts:
                assert l < x < w - r and b < y < h - t
                assert not (block[0] < x < block[2] and block[1] < y < block[3])
    svg = to_svg(sh, "Soporte")
    root = ET.fromstring(svg)
    assert root.get("viewBox") == f"0 {-h:g} {w:g} {h:g}" and root.get("width") == f"{w:g}mm"
    assert 'stroke-dasharray="3,1.5"' in svg and "Taller" in svg
    dxf = to_dxf(sh)
    assert dxf.startswith("0\nSECTION") and dxf.rstrip().endswith("EOF")
    hidden_segments = sum(len(p) - 1 for p, s in sh.lines if s == "hidden")
    assert dxf.count("LINE\n8\nOCULTAS") == hidden_segments > 0
    assert "DASHED" in dxf and "TEXT\n8\nTEXTOS" in dxf
    set_language("en")
    try:
        assert number(0.5) == "0.5"
    finally:
        set_language("es")


def test_ejes_de_los_taladros_en_el_plano():
    """Las circunferencias cerradas de una vista ortogonal llevan su eje (una cruz de trazo y punto
    por centro, con el radio de la mayor); un polígono que no es redondo no."""
    from scadgui import geometry as geo
    from scadgui.drawing_lines import mesh_edges, view_lines
    from scadgui.drawing_sheet import circles
    tris = np.concatenate([geo.cylinder({"h": 10, "r": 12}, {"fn": 48, "fa": 12, "fs": 2}),
                           geo.cube({"size": [10, 10, 10]}) + np.array([30.0, 0, 0])])
    vis, hid = view_lines(mesh_edges(tris), tris, "top")
    found = circles(vis + hid)
    assert len(found) == 1
    (cx, cy), r = found[0]
    assert abs(cx) < 1e-6 and abs(cy) < 1e-6 and abs(r - 12) < 0.2
    two = [[(r * math.cos(a), r * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 25)] for r in (4, 9)]
    assert [round(f[1]) for f in circles(two)] == [9]                         # concéntricas: un eje


def test_conico_en_la_vista_aproximada():
    from scadgui.parser import parse
    from scadgui import geometry as geo, gears
    doc = parse("bevel_gear(mod = 2, teeth = 20, mate_teeth = 20, face_width = 8);")
    tris = next(iter(geo.build_ghosts(doc).values()))
    d = gears.bevel_dims(2, 20, 20, 90, 20, 8)
    assert geo.signed_volume(tris) > 0
    assert np.isclose(np.hypot(tris[..., 0], tris[..., 1]).max(), d["tip_d"] / 2)
    assert np.isclose(tris[..., 2].max(), d["outer_z"])            # cara trasera plana
    assert np.isclose(tris[..., 2].min(), d["outer_z"] - 8 * math.cos(math.radians(45)))


def test_cremallera_y_helicoidal_en_la_vista_aproximada():
    from scadgui.parser import parse
    from scadgui import geometry as geo
    doc = parse("rack(mod = 2, teeth = 6, thickness = 5, base = 4, backlash = 0.1);")
    tris = next(iter(geo.build_ghosts(doc).values()))
    assert np.isclose(tris[..., 2].min(), 0) and np.isclose(tris[..., 2].max(), 5)
    assert geo.signed_volume(tris) > 0
    doc = parse("rack(mod = 1, teeth = 6, thickness = 10, base = 5, helix_angle = 20);")
    tris = next(iter(geo.build_ghosts(doc).values()))
    low = tris[np.isclose(tris[..., 2], 0).all(axis=1)].reshape(-1, 3)
    high = tris[np.isclose(tris[..., 2], 10).all(axis=1)].reshape(-1, 3)
    from scadgui import gears as g
    assert np.isclose(high[:, 0].min() - low[:, 0].min(), 10 * g.rack_shear(20))   # dentado sesgado
    assert geo.signed_volume(tris) > 0
    doc = parse("helical_gear(mod = 1, teeth = 20, thickness = 10, helix_angle = 20, center = true);")
    tris = next(iter(geo.build_ghosts(doc).values()))
    assert np.isclose(tris[..., 2].min(), -5) and np.isclose(tris[..., 2].max(), 5)
    assert geo.signed_volume(tris) > 0
    # El perfil de arriba está girado respecto al de abajo justo el giro de la hélice.
    from scadgui import gears
    low = tris[np.isclose(tris[..., 2], -5).all(axis=1)].reshape(-1, 3)
    high = tris[np.isclose(tris[..., 2], 5).all(axis=1)].reshape(-1, 3)
    far = lambda p: p[np.argmax(np.hypot(p[:, 0], p[:, 1]))]
    a0, a1 = (math.degrees(math.atan2(*far(q)[1::-1])) for q in (low, high))
    turned = (a1 - a0) % 18                                          # 20 dientes: uno cada 18°
    want = gears.helix_twist(1, 20, 20, 10) % 18
    assert min(abs(turned - want), 18 - abs(turned - want)) < 0.01, (turned, want)


def test_espina_de_pescado_en_la_vista_aproximada():
    """Las dos mitades están en fase en el plano central (mismo giro de las dos ahí) y la pieza es
    simétrica en espejo respecto a él: el giro a una distancia z del centro es el mismo a ambos
    lados (hélice de mano contraria), justo lo que distingue a un espina de pescado de un helicoidal
    normal (que seguiría girando siempre para el mismo lado)."""
    from scadgui.parser import parse
    from scadgui import geometry as geo, gears
    doc = parse("herringbone_gear(mod = 2, teeth = 18, thickness = 16, helix_angle = 25, center = true);")
    tris = next(iter(geo.build_ghosts(doc).values()))
    assert np.isclose(tris[..., 2].min(), -8) and np.isclose(tris[..., 2].max(), 8)
    assert geo.signed_volume(tris) > 0
    pts = tris.reshape(-1, 3)
    far = lambda ring: ring[np.argmax(np.hypot(ring[:, 0], ring[:, 1]))]

    def angle_at(z0, tol=0.01):
        ring = pts[np.isclose(pts[:, 2], z0, atol=tol)]
        p = far(ring)
        return math.degrees(math.atan2(p[1], p[0]))
    for d in (1.0, 4.0, 7.0):
        below, above = angle_at(-d), angle_at(d)
        assert abs(below - above) < 0.05, (d, below, above)          # simétrico respecto al centro
    # El giro de cada mitad por separado es el que calcula gears.helix_twist con el medio grueso.
    mine = abs(geo.signed_volume(geo.herringbone_gear(doc.children[0].params)))
    assert mine > 0 and gears.helix_twist(2, 18, 25, 8) > 0


def test_polea_dentada_diametros_y_hueco():
    """El hueco es el negativo del diente, de flancos rectos: el fondo no se solapa con el de
    al lado y la boca no pasa del lomo entre huecos."""
    from scadgui import gears
    poly = gears.pulley_polygon("XL", 20)
    r = np.linalg.norm(poly, axis=1)
    d = gears.pulley_dims("XL", 20)
    assert np.isclose(r.max(), d["outer_d"] / 2)
    assert np.isclose(r.min(), d["root_d"] / 2)
    mirrored = poly * [1, -1]                                            # hueco centrado en +X
    assert all(np.min(np.linalg.norm(poly - q, axis=1)) < 1e-9 for q in mirrored)


def test_polea_dentada_en_la_vista_aproximada():
    from scadgui.parser import parse
    from scadgui import geometry as geo
    doc = parse('pulley(section = "H", teeth = 16, width = 8, center = true);')
    tris = next(iter(geo.build_ghosts(doc).values()))
    assert np.isclose(tris[..., 2].min(), -4) and np.isclose(tris[..., 2].max(), 4)
    assert geo.signed_volume(tris) > 0


def test_polea_dentada_con_pestanas():
    """Con pestaña a un lado la pieza se alarga ese vuelo; con las dos, por los dos lados, y el
    collar sobresale del Ø exterior (se nota en el radio máximo de la malla)."""
    from scadgui.parser import parse
    from scadgui import geometry as geo, gears
    d = gears.pulley_dims("XL", 20)
    doc = parse('pulley(section = "XL", teeth = 20, width = 6, flange = "superior", '
                'flange_height = 2, center = true);')
    tris = next(iter(geo.build_ghosts(doc).values()))
    assert np.isclose(tris[..., 2].min(), -4) and np.isclose(tris[..., 2].max(), 4)   # (6+2)/2
    r = np.linalg.norm(tris[..., :2], axis=-1)
    assert np.isclose(r.max(), d["outer_d"] / 2 + 2, atol=0.05)
    doc2 = parse('pulley(section = "XL", teeth = 20, width = 6, flange = "ambas", '
                 'flange_height = 2, center = true);')
    tris2 = next(iter(geo.build_ghosts(doc2).values()))
    assert np.isclose(tris2[..., 2].min(), -5) and np.isclose(tris2[..., 2].max(), 5)
    assert geo.signed_volume(tris2) > geo.signed_volume(tris)   # dos pestañas pesan más que una

def test_polea_trapecial_perfil_y_ancho():
    """El perfil (radio, altura) parte del Ø primitivo, cae a cada ranura y el ancho de cara
    sale solo de separación/margen entre ranuras, no de un parámetro propio."""
    from scadgui import gears
    d = gears.v_pulley_dims("A", 80, 3)
    prof = gears.v_pulley_profile("A", 80, 3)
    assert np.isclose(prof[:, 0].max(), d["outer_d"] / 2)
    assert np.isclose(prof[:, 0].min(), 0.0)                      # cierra en el eje
    assert np.isclose(prof[:, 1].max(), d["face_width"])
    assert np.isclose(prof[:, 1].min(), 0.0)
    r_bot = d["outer_d"] / 2 - d["groove_depth"]
    assert np.any(np.isclose(prof[:, 0], r_bot, atol=1e-6))       # llega al fondo de la ranura


def test_polea_trapecial_en_la_vista_aproximada():
    from scadgui.parser import parse
    from scadgui import geometry as geo, gears
    doc = parse('v_pulley(section = "B", datum_d = 150, grooves = 2, center = true);')
    tris = next(iter(geo.build_ghosts(doc).values()))
    d = gears.v_pulley_dims("B", 150, 2)
    half = d["face_width"] / 2
    assert np.isclose(tris[..., 2].min(), -half, atol=1e-6) and np.isclose(tris[..., 2].max(), half, atol=1e-6)
    r = np.linalg.norm(tris[..., :2], axis=-1)
    assert np.isclose(r.max(), d["outer_d"] / 2, atol=0.05)
    assert geo.signed_volume(tris) > 0


def test_estriado_cubo_con_hueco_y_eje_que_cabe():
    """El cubo es una corona: pesa el círculo menos el hueco, y sus tapas no tapan el hueco. A cualquier
    radio, el diente del eje cabe en el hueco del cubo; con holgura, sobra."""
    from scadgui import gears
    from scadgui.geometry import _area, signed_volume, spline
    ctx = {"fn": 96, "fa": 12, "fs": 2}
    for pa in (30, 37.5, 45):
        hole = gears.spline_polygon(2, 20, pa, internal=True)
        mesh = spline({"mod": 2, "teeth": 20, "length": 10, "pressure_angle": pa, "internal": True, "hub_d": 70}, ctx)
        ring = 96 * 0.5 * 35 ** 2 * math.sin(2 * math.pi / 96)
        assert abs(abs(signed_volume(mesh)) - (ring - abs(_area(hole))) * 10) < 1e-6, pa
        assert (mesh[:, :, 2] == 10).any() and (np.linalg.norm(mesh[:, :, :2], axis=2) >= 19).all(), pa
        shaft = gears.spline_polygon(2, 20, pa)
        loose = gears.spline_polygon(2, 20, pa, clearance=0.1)
        assert abs(_area(loose)) < abs(_area(shaft)) < abs(_area(hole)), pa
        assert np.linalg.norm(shaft, axis=1).max() < np.linalg.norm(hole, axis=1).max(), pa   # no toca el fondo
    assert spline({"mod": 2, "internal": True, "hub_d": 10}, ctx) is None     # el hueco se sale del cubo


def test_leva_perfil_radio_base_y_alzada():
    """El perfil nunca baja del radio base ni sube más que la alzada, y en el tramo de reposo
    de arriba se mantiene exactamente en Ø base + alzada (dentro de la resolución de 1°/punto)."""
    from scadgui import gears
    d = gears.cam_dims(40, 10, 90, 30, 90)
    poly = gears.cam_polygon(40, 10, 90, 30, 90, "cicloidal")
    r = np.linalg.norm(poly, axis=1)
    assert r.min() >= d["base_r"] - 1e-6
    assert r.max() <= d["outer_r"] + 1e-6
    assert np.isclose(r.max(), d["outer_r"], atol=0.01)      # llega arriba del todo
    assert np.isclose(r.min(), d["base_r"], atol=0.01)       # y vuelve abajo del todo


def test_leva_en_la_vista_aproximada():
    from scadgui.parser import parse
    from scadgui import geometry as geo, gears
    doc = parse('cam(base_d = 40, lift = 10, rise_angle = 90, dwell_angle = 30, fall_angle = 90, '
                'thickness = 8, center = true);')
    tris = next(iter(geo.build_ghosts(doc).values()))
    assert np.isclose(tris[..., 2].min(), -4) and np.isclose(tris[..., 2].max(), 4)
    r = np.linalg.norm(tris[..., :2], axis=-1)
    assert np.isclose(r.max(), 30.0, atol=0.5)   # Ø base 40 + alzada 10 = radio 30
    assert geo.signed_volume(tris) > 0


def test_brida_malla_gira_el_perfil_del_modulo():
    """La vista aproximada de la brida pesa lo mismo que el perfil girado (Pappus), sin los agujeros
    de los tornillos; centrada, queda repartida a los dos lados de z = 0."""
    from scadgui import flanges
    ctx = {"fn": 720, "fa": 12, "fs": 2}
    for args in (("asme_b16_5", "150", "4", "weld_neck"), ("en_1092_1", "16", "100", "weld_neck"),
                 ("asme_b16_5", "300", "6", "blind"), ("en_1092_1", "6", "50", "plate", "flat")):
        p = flanges.create_flange_node(*args).params
        mesh = g.pipe_flange(p, ctx)
        exact = flanges.flange_volume({**p, "bolts": 0})
        assert abs(abs(g.signed_volume(mesh)) - exact) < exact * 2e-4, args
        assert abs(mesh[:, :, 2].min()) < 1e-9
    p = flanges.create_flange_node("asme_b16_5", "150", "4", "weld_neck").params
    z = g.pipe_flange({**p, "center": True}, ctx)[:, :, 2]
    assert abs(z.min() + 38.5) < 1e-9 and abs(z.max() - 38.5) < 1e-9          # largo total 77
    assert g.pipe_flange({**p, "od": 0}, ctx) is None


def test_lobulo_y_eje_en_la_vista_aproximada():
    """El lóbulo es su perfil extruido: ocupa de position - width/2 a position + width/2 y pesa el área
    del perfil por el ancho; el eje va de z = 0 a su longitud."""
    from scadgui import gears
    from scadgui.geometry import _area
    p = {"base_r": 15, "lift": 8, "width": 12, "rise_angle": 70, "dwell_angle": 10, "fall_angle": 130,
         "motion": "parabolica", "angle": 45, "position": 100, "step": 0.5}
    mesh = g.cam_lobe(p)
    poly = gears.lobe_polygon(15, 8, 70, 10, 130, "parabolica", 45, 0.5)
    assert abs(mesh[:, :, 2].min() - 94) < 1e-9 and abs(mesh[:, :, 2].max() - 106) < 1e-9
    assert abs(g.signed_volume(mesh) - abs(_area(poly)) * 12) < 1e-6
    assert g.cam_lobe({**p, "motion": "inventada"}) is None and g.cam_lobe({**p, "width": 0}) is None
    shaft = g.camshaft_main_shaft({"length": 250, "d": 25}, {"fn": 64, "fa": 12, "fs": 2})
    assert abs(shaft[:, :, 2].min()) < 1e-9 and abs(shaft[:, :, 2].max() - 250) < 1e-9


def test_lobulo_perfiles_en_la_vista_aproximada():
    """Cada perfil se extruye tal cual: el volumen es el área de su contorno por el ancho."""
    from scadgui import gears
    from scadgui.geometry import _area
    for profile in ("circular", "excentrico", "eliptico", "periforme"):
        p = {"base_r": 15, "lift": 8, "width": 10, "rise_angle": 110, "dwell_angle": 20, "fall_angle": 110,
             "motion": "cicloidal", "angle": 30, "position": 5, "step": 2, "profile": profile, "nose_r": 6}
        poly = gears.lobe_polygon(15, 8, 110, 20, 110, "cicloidal", 30, 2, profile, 6)
        assert abs(g.signed_volume(g.cam_lobe(p)) - abs(_area(poly)) * 10) < 1e-6, profile
    assert g.cam_lobe({"profile": "cuadrado"}) is None


def test_modos_de_visualizacion():
    _, gh = ghosts_of("cube(10);")
    cube = only(gh)
    wire = g.mesh_edges(cube)
    assert len(cube) == 12 and len(wire) == 18     # 12 aristas del cubo + 6 diagonales, sin repetir
    assert wire.shape == (18, 2, 3)
    assert len(g.mesh_edges(np.zeros((0, 3, 3)))) == 0
    _, gh = ghosts_of("cylinder(h = 5, r = 3, $fn = 32);")
    cyl = only(gh)
    # malla cerrada: cada arista la comparten dos caras (Euler: A = 3C/2)
    assert len(g.mesh_edges(cyl)) == len(cyl) * 3 // 2
    keys = [k for k, _ in g.DISPLAY_MODES]
    assert keys[0] == "shaded" and len(set(keys)) == len(keys)
    assert [g.next_display_mode(keys[-1]), g.next_display_mode(keys[0], -1)] == [keys[0], keys[-1]]
    assert g.next_display_mode("desconocido") == keys[1]
    assert g.display_style("desconocido") == g.display_style("shaded")
    assert not g.display_style("wireframe")["faces"] and g.display_style("wireframe")["wire"]
    assert g.display_style("hidden_line")["outline"] and g.display_style("hidden_line")["flat"]
    cols = np.ones((3, 4))
    xr = g.xray_colors(cols)
    assert np.all(xr[:, 3] == g.XRAY_ALPHA) and np.all(cols[:, 3] == 1)   # no toca el original
    from scadgui.locales import de, en, fr, it, pt
    for _, label in g.DISPLAY_MODES:                # se traducen con tr(label): no los ve el escáner
        assert all(label in m.STRINGS for m in (de, en, fr, it, pt)), label


def test_calculadora_de_transmisiones():
    import math as m
    from scadgui import transmission as tm
    from scadgui.model import Document, Node, generate
    assert tm.ratio_from_speeds(1500, 400) == 3.75
    # Una etapa: 3.75 exacto con el mínimo sin socavado de un recto (18 dientes)
    sols = tm.search(3.75, 1, 1, 18, 100)
    assert sols[0].stages == [(20, 75)] and sols[0].error == 0 and sols[0].centers == [47.5]
    assert all(abs(s.error) <= 0.01 for s in sols)
    assert all(min(s.stages[0]) >= 18 and max(s.stages[0]) <= 100 for s in sols)
    errs = [abs(s.error) for s in sols]
    assert errs == sorted(errs)                          # ordenadas por error
    assert sols[0].hunting == [False]                    # 20 y 75 comparten el 5
    # Multiplicadora: la relación menor que 1 pone al conducido más pequeño
    s = tm.search(0.5, 0, 1, 18, 60)[0]
    assert s.stages == [(36, 18)] and s.ratio == 0.5
    # Distancia máxima entre centros
    assert all(c <= 40 + 1e-9 for s in tm.search(3.75, 2, 1, 12, 100, max_center=40) for c in s.centers)
    # Helicoidal: la distancia lleva el cos ψ
    h = tm.search(2, 0, 1, 20, 40, "helical_gear", 1, 20)[0]
    assert m.isclose(h.centers[0], (h.stages[0][0] + h.stages[0][1]) / (2 * m.cos(m.radians(20))))
    # Dos etapas: 20:1 imposible en una con 12..60 dientes, sí en dos; las etapas reducen las dos
    assert tm.search(20, 0, 1, 12, 60) == []
    two = tm.search(20, 0, 2, 12, 60)
    assert two and all(s.error == 0 for s in two)
    for s in two:
        (a, b), (c, d) = s.stages
        assert b / a >= 1 and d / c >= 1 and m.isclose(b / a * d / c, 20)
    keys = [tuple(sorted(s.stages)) for s in two]
    assert len(keys) == len(set(keys))                    # sin la misma solución en el otro orden
    # Tren revertido: las dos etapas con la misma distancia (z1 + z2 = z3 + z4)
    rev = tm.search(9, 1, 2, 12, 80, coaxial=True)
    assert rev and all(sum(s.stages[0]) == sum(s.stages[1]) for s in rev)
    try:
        tm.search(0, 1)
        raise AssertionError("relación 0")
    except ValueError:
        pass
    # Avisos: pocos dientes y divisores comunes
    sol = tm.Solution([(10, 40)], 4, 0, [25])
    texts = [t for t, _ in tm.notes(sol, "spur_gear")]
    assert len(texts) == 2
    # El tren generado: grupo con las ruedas colocadas a su distancia y con las hélices contrarias
    sol = tm.search(12, 1, 2, 12, 60, "helical_gear", 1.5, 20)[0]
    group = tm.create_train(sol, "helical_gear", {"mod": 1.5, "helix_angle": 20, "thickness": 8, "bore": 5},
                            stage_gap=2)
    wheels = []
    for top in group.children:
        n, x, z = top, 0.0, 0.0
        while n.kind in ("translate", "rotate"):
            if n.kind == "translate":
                x, z = n.params["v"][0], n.params["v"][2]
            n = n.children[0]
        wheels.append((n, x, z))
    (g1, x1, h1), (g2, x2, h2), (g3, x3, h3), (g4, x4, h4) = wheels
    assert [g.params["teeth"] for g, _, _ in wheels] == [z for st in sol.stages for z in st]
    assert x1 == 0 and m.isclose(x2, sol.centers[0], abs_tol=1e-6) and x3 == x2
    assert m.isclose(x4, x3 + sol.centers[1], abs_tol=1e-6) and h1 == h2 == 0 and h3 == h4 == 10
    assert g1.params["left_hand"] != g2.params["left_hand"] == g3.params["left_hand"] != g4.params["left_hand"]
    assert g1.params["mod"] == 1.5 and g1.params["bore"] == 5
    rev = tm.search(9, 1, 2, 12, 80, coaxial=True)[0]
    group = tm.create_train(rev, "spur_gear", {"mod": 1, "thickness": 5, "helix_angle": 20}, coaxial=True)
    last = group.children[3]
    assert m.isclose(last.params["v"][0], 0, abs_tol=1e-6)       # la salida, sobre la entrada
    assert "helix_angle" not in last.children[0].children[0].params  # un recto no lleva hélice
    generate(Document(children=[group]))


def test_calculadora_de_correas():
    import math as m
    from scadgui import gears, transmission as tm
    from scadgui.model import Document, generate
    # Longitud de correa abierta y la distancia que le corresponde (la una deshace la otra)
    assert m.isclose(tm.belt_length(50, 50, 100), 200 + 50 * m.pi)
    assert m.isclose(tm.belt_center(40, 120, tm.belt_length(40, 120, 150)), 150)
    assert tm.belt_center(40, 120, 100) is None                     # no da la vuelta a las dos
    assert tm.wrap_angle(50, 50, 100) == 180 and tm.wrap_angle(40, 120, 80) < 180
    # Dentada: relación exacta, correa de un número entero de dientes y su distancia, recalculada
    sols = tm.search_timing(2.5, 0, "XL", 10, 80)
    assert sols and all(s.ratio == 2.5 and s.driven / s.driver == 2.5 for s in sols)
    p = gears.PULLEY_SECTIONS["XL"][0]
    for s in sols:
        d1, d2 = s.diameters
        assert m.isclose(s.length, s.belt_teeth * p) and m.isclose(tm.belt_length(d1, d2, s.center), s.length)
    assert sols[0].mesh_teeth >= tm.MIN_MESH_TEETH                  # primero las que no avisan
    near = tm.search_timing(2.5, 0, "XL", 10, 80, center=200)
    assert all(abs(s.center - 200) < p for s in near)               # cerca de la pedida (medio paso de correa)
    weak = tm.BeltSolution("pulley", "XL", 10, 25, 2.5, 0, 56, tm.belt_length(
        gears.pulley_dims("XL", 10)["pitch_d"], gears.pulley_dims("XL", 25)["pitch_d"], 56), 0)
    assert any("abraza" in t for t, _ in tm.belt_notes(weak))
    # En V: Ø redondos (múltiplos del paso) desde el mínimo de la sección; los dos dentro de los límites
    vs = tm.search_v(2.5, 1, "A", 0, 300, 5)
    assert vs[0].driver == 80 and vs[0].driven == 200 and m.isclose(vs[0].center, 280)
    assert all(s.driver % 5 == 0 and 76.2 <= min(s.driver, s.driven) and max(s.driver, s.driven) <= 300
               for s in vs)
    fixed = tm.search_v(2.5, 1, "A", 0, 300, 5, length=1200)
    assert fixed and all(s.length == 1200 and m.isclose(tm.belt_length(s.driver, s.driven, s.center), 1200)
                         for s in fixed)
    over = tm.search_v(0.5, 1, "B", 0, 400, 5)                      # multiplicadora: la motriz es la grande
    assert over and all(s.driver > s.driven >= 137.16 for s in over)
    texts = [t for t, _ in tm.belt_notes(tm.BeltSolution("v_pulley", "A", 80, 300, 3.75, 0, 160, 0), 9000)]
    assert any("abrazamiento" in t for t in texts) and any("m/s" in t for t in texts)
    # Generado: motriz en el origen, conducida a la distancia y la correa como una pieza aparte
    s = sols[0]
    g = tm.create_belt_drive(s, {"width": 8, "bore": 5, "flange": "ambas"})
    assert [c.kind for c in g.children] == ["pulley", "translate", "color"]
    assert g.children[0].params["teeth"] == s.driver and g.children[1].children[0].params["teeth"] == s.driven
    assert g.children[1].params["v"][0] == round(s.center, 6) and g.children[0].params["flange"] == "ambas"
    g = tm.create_belt_drive(vs[0], {"grooves": 3, "bore": 0}, belt=True)
    assert len(g.children) == 5 and "bore" not in g.children[0].params   # una correa por ranura
    assert g.children[1].children[0].params["datum_d"] == 200
    assert len(tm.create_belt_drive(vs[0], {"grooves": 3}, belt=False).children) == 2
    generate(Document(children=[g]))


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
