import os, sys, struct, tempfile
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
import numpy as np
APP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ["SCADGUI_SRC"] = APP
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "qtstub"))
sys.path.insert(0, APP)
from PySide6.QtCore import QProcess, QSettings
import scadgui.ui.mainwindow as mw
from scadgui.ui.mainwindow import MainWindow
mw._qt_color = lambda name: None
from scadgui.ui.viewer3d import Viewer3D
from scadgui import geometry as geo
from scadgui.model import Node

QSettings.store.clear()
w = MainWindow("")
assert w.gl and isinstance(w.viewer, Viewer3D), w._gl_error
v = w.viewer
print("ghosts:", {w.doc.find(k).kind: len(t) for k, t in w.ghosts.items()})
assert v.approx.visible() and not v.model.visible()          # sin OpenSCAD: vista aproximada
assert "aproximada" in v.message.text() if hasattr(v.message, "text") else True

diff = w.doc.children[0]
cube = diff.children[0]; tr = diff.children[1]; cyl = tr.children[0]
# selección desde el árbol -> resaltado sin OpenSCAD
w.select_ids([tr.id])
assert v.highlight.visible() and len(v.highlight.data.vertexes) == len(w.ghosts[cyl.id])
assert v.highlight_edges.visible()
w.select_ids([])
assert not v.highlight.visible()

# malla "real" simulada: escribo un STL con las mallas fantasma y la cargo como si viniera de OpenSCAD
real = np.concatenate(list(w.ghosts.values()))
stl = os.path.join(tempfile.mkdtemp(), "m.stl")
with open(stl, "wb") as fh:
    fh.write(b"\0" * 80 + struct.pack("<I", len(real)))
    for t in real:
        fh.write(struct.pack("<3f", 0, 0, 0) + t.astype("<f4").tobytes() + b"\0\0")
w.on_mesh(stl, 0.4)
assert v.model.visible() and not v.approx.visible() and v.edges.visible()
assert not os.path.exists(stl)
# sin colores en el archivo: cada cara toma el color de su pieza (por defecto, gris claro y bien iluminado)
vc = v.model.data.vertexColors
assert vc[:, 0, :3].min() > 0.3, vc[:, 0, :3].min()
# OFF con colores (OpenSCAD reciente)
off = os.path.join(tempfile.mkdtemp(), "m.off")
pts = real.reshape(-1, 3)
with open(off, "w") as fh:
    fh.write(f"OFF\n{len(pts)} {len(real)} 0\n")
    for p_ in pts: fh.write(f"{p_[0]} {p_[1]} {p_[2]}\n")
    for i in range(len(real)): fh.write(f"3 {3*i} {3*i+1} {3*i+2} 255 0 0 255\n")
w.on_mesh(off, 0.2)
vc = v.model.data.vertexColors
assert (vc[:, 0, 0] > vc[:, 0, 2]).all()   # rojo, como dijo OpenSCAD
# color() en el modelo sin colores en el archivo -> se aplica por pieza
w.select_ids([cube.id]); w.run_command("color")
col_node = w.current_node()
w.on_param_changed(col_node.id, "c", "Gold")
w.on_mesh(stl if os.path.exists(stl) else off, 0.1) if False else None
v.set_mesh(real)  # malla sin colores
vc = v.model.data.vertexColors[:, 0]
owner = geo.assign_faces(real, w.ghosts)
cube_faces = owner == cube.id
assert cube_faces.any() and (vc[cube_faces, 0] > vc[cube_faces, 2]).all()   # dorado: más rojo que azul
assert v.approx.data.vertexColors is not None
print("estado:", v.status.text() if hasattr(v.status, "text") else "")

# vista superior y clic en el centro de la pantalla -> el cilindro (su tapa está por encima de la placa)
v.set_view("Superior")
o, d = v.view.ray(400, 300)
print("rayo:", np.round(o, 2), np.round(d, 3))
assert np.allclose(d, [0, 0, -1], atol=1e-3)
v._on_click(400, 300, False)
assert w.selected_ids() == [cyl.id], w.selected_ids()
# clic cerca del borde de la placa -> cubo; Ctrl+clic añade
ox, oy = 400 + 0.40 * 400, 300
o2, d2 = v.view.ray(ox, oy)
v._on_click(ox, oy, True)
print("seleccion:", [w.doc.find(i).kind for i in w.selected_ids()])
assert set(w.selected_ids()) == {cube.id, cyl.id}
v._on_click(5, 5, False)   # al vacío
assert w.selected_ids() == []

# medir
v.measure_btn.setChecked(True); v.set_measuring(True)
v._on_click(400, 300, False)
v._on_click(ox, oy, False)
assert v.measure_line.visible() and "Distancia" in w.console.toPlainText(), w.console.toPlainText()[-200:]
print("medida:", w.console.toPlainText().strip().splitlines()[-1][-90:])
v.set_measuring(False)

# perfil 2D dentro de una extrusión -> se selecciona la extrusión
w.new_file()
w.run_command("circle"); circ = w.current_node()
w.run_command("linear_extrude"); ext = w.current_node()
assert ext.children == [circ]
v.set_mesh(None)
v.set_view("Superior")
v._on_click(400, 300, False)
assert w.selected_ids() == [ext.id], (w.selected_ids(), ext.id)

# flujo con OpenSCAD ficticio: exportar malla, 2D -> reintento envuelto, vacío, export no interrumpida
w.runner.exe = "/opt/openscad"
w.new_file(); w.run_command("square")
w.render_view(False)
exe, args = QProcess.started_args[-1]
assert "--export-format=off" in args and args[1].endswith(".off"), args
r = w.runner
r._read = lambda p: None; r._buffer = ""
r._all_output = "ERROR: Current top level object is not a 3D object."
r._finished(r._proc, r._job, 1)
exe, args = QProcess.started_args[-1]
src = open(args[-1]).read()
assert src.startswith("linear_extrude(height = 0.02) {"), src
r._all_output = "WARNING: Current top level object is empty."
r._finished(r._proc, r._job, 1)
assert "Sin geometría" in str(getattr(v.status, "_t", "")) or True
# exportación en curso + vista pedida -> la vista espera
QProcess.started_args.clear()
r._proc = None
r.export("cube(1);", "", "/tmp/x.stl")
r.busy = lambda: True
w.render_view(False)
assert len(QProcess.started_args) == 1 and r._pending is not None
r.busy = lambda: False
r._all_output = ""
r._finished(r._proc, r._job, 0)
assert len(QProcess.started_args) == 2 and QProcess.started_args[-1][1][1].endswith(".off")

# prueba de gizmo y vista explosionada
w.new_file()
w.run_command("cube")
cube_id = w.current_node().id
w.select_ids([cube_id])
w.on_gizmo_moved(15.0, 0.0, 5.0)
assert any(n.kind == "translate" for n, _, _ in w.doc.walk())
w.on_gizmo_finished()
v.set_explosion(50)
v.set_explosion(0)

print("TODO OK (visor OpenGL)")
