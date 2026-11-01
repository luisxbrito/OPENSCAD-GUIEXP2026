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
