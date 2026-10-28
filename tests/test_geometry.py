"""Pruebas de la geometría del visor (necesitan numpy, no Qt ni OpenSCAD)."""

import math
import os
import struct
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np  # noqa: E402

from scadgui import geometry as g  # noqa: E402
from scadgui.model import Document, generate  # noqa: E402
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
