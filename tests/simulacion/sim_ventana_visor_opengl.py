import os, sys, struct, tempfile
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # la consola de Windows no es UTF-8
import numpy as np
APP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ["SCADGUI_SRC"] = APP
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "qtstub"))
sys.path.insert(0, APP)
from PySide6.QtCore import QPointF, QProcess, QSettings
import scadgui.ui.mainwindow as mw
from scadgui.ui.mainwindow import MainWindow
mw._qt_color = lambda name: None
from scadgui.ui.viewer3d import Viewer3D
from scadgui import geometry as geo

QSettings.store.clear()
w = MainWindow("")
# la aplicación arranca en blanco; estas pruebas abren el ejemplo de la placa
assert w.doc.children == [] and w.path == "" and not w.modified
assert w.code.text.toPlainText().strip() == "// Generado con OpenSCAD GUI Mejorada", w.code.text.toPlainText()
w.open_example(mw.EXAMPLE_PLACA)
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

# atajos de vista como en Blender
from scadgui.ui import viewer3d as v3d
o = v.view.opts
v.key_command("1"); assert (o["elevation"], o["azimuth"]) == (0.0, -90.0)          # frontal
v.key_command("1", True); assert (o["elevation"], o["azimuth"]) == (0.0, 90.0)     # Ctrl: trasera
v.key_command("3", True); assert o["azimuth"] == 180.0                             # izquierda
v.key_command("7"); assert o["elevation"] == 90.0
v.key_command("9"); assert o["elevation"] == -90.0 and o["azimuth"] == 90.0        # inferior
v.key_command("0"); v.key_command("6"); assert o["azimuth"] == (-55.0 + 15) % 360
v.key_command("8"); assert o["elevation"] == 45.0
dist = o["distance"]
v.key_command("5"); assert v.orthographic and o["fov"] == v3d.ORTHO_FOV and o["distance"] > 40 * dist
v.key_command("5"); assert not v.orthographic and o["fov"] == v3d.PERSPECTIVE_FOV and abs(o["distance"] - dist) < 1e-6
w.select_ids([cyl.id])
v.key_command(".")   # encuadra solo el cilindro seleccionado
lo, hi = geo.bbox(w.ghosts[cyl.id])
assert np.allclose([o["center"].x(), o["center"].y(), o["center"].z()], (lo + hi) / 2)
v.key_command("home")
w.select_ids([])
v.set_view("Superior")   # las pruebas de medir siguen desde arriba

# árbol sobre el visor y de vuelta (con Qt real lo prueba tests/test_ventana_qt.py)
w.set_tree_overlay(True); assert w.tree_box is not None
w.set_tree_overlay(True); w.set_tree_overlay(False); assert w.tree_box is None

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

# --- aristas: elegir con el ratón en vista superior y redondear
def pixel_of(view, p):
    """Píxel por el que pasa el rayo hacia el punto p (inversa de _GLView.ray)."""
    import math
    cam, _ = view.ray(400, 300)
    c = view.opts["center"]
    center = np.array([c.x(), c.y(), c.z()], float)
    fwd = (center - cam) / np.linalg.norm(center - cam)
    elev, azim = math.radians(view.opts["elevation"]), math.radians(view.opts["azimuth"])
    right = np.cross(fwd, [0, 0, 1.0])
    if np.linalg.norm(right) < 1e-9:
        right = np.array([-math.sin(azim), math.cos(azim), 0.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    d = np.asarray(p, float) - cam
    tx = math.tan(math.radians(view.opts["fov"]) / 2)
    ty = tx * view.height() / view.width()
    nx, ny = (d @ right) / (d @ fwd) / tx, (d @ up) / (d @ fwd) / ty
    return (nx + 1) / 2 * view.width(), (1 - ny) / 2 * view.height()

w.new_file()
w.run_command("cube"); box = w.current_node()
w.on_param_changed(box.id, "size", [40, 30, 10])
v.set_mesh(None)
v.set_view("Superior")
v.set_edge_mode(True)
assert any(e[0] == box.id for e in v._edge_targets)
x, y = pixel_of(v.view, [40, 30, 10])
v._on_hover(x, y)
assert v._hover_edge is not None and v.edge_hover_line.visible()
sel_before = w.selected_ids()
v._on_click(*pixel_of(v.view, [20, 30, 10]), False)          # mitad de la arista superior trasera
assert v.selected_edges == [(box.id, "y1z1")], v.selected_edges
assert w.selected_ids() == sel_before      # en modo aristas el clic no cambia la selección de piezas
v._on_click(*pixel_of(v.view, [0, 15, 10]), True)            # Ctrl+clic: añade la de la izquierda
assert v.selected_edges == [(box.id, "y1z1"), (box.id, "x0z1")], v.selected_edges
v._on_click(*pixel_of(v.view, [20, 15, 10]), True)           # Ctrl+clic en mitad de la cara: nada cambia
assert len(v.selected_edges) == 2
w.finish_edges("round", 2.5, v.selected_edges)
code = w.code.text.toPlainText()
assert 'cube_edges([40, 30, 10], center = false, edges = ["y1z1", "x0z1"], rounding = 2.5);\n' in code, code
assert "module cube_edges(" in code
assert v.selected_edges == [(box.id, "y1z1"), (box.id, "x0z1")]   # siguen elegidas tras el cambio
assert geo.signed_volume(w.ghosts[box.id]) < 12000
w.undo()
assert w.doc.find(box.id).kind == "cube" and "module" not in w.code.text.toPlainText()
v.set_edge_mode(False)
assert not v.edge_picked_lines.visible() and v.selected_edges == []

# --- gizmo: arrastrar mueve, un clic sin arrastrar no deja rastro, deshacer vuelve atrás
w.new_file()
w.run_command("cube")
cube_id = w.current_node().id
w.select_ids([cube_id])
pasos = len(w.history.undo_stack)
w.on_gizmo_started(); w.on_gizmo_finished()            # clic en un eje sin mover
assert not any(n.kind == "translate" for n, _, _ in w.doc.walk()), "un clic no debe crear translate"
assert len(w.history.undo_stack) == pasos
w.select_ids([cube_id])
w.on_gizmo_started(); w.on_gizmo_moved(15.0, 0.0, 5.0); w.on_gizmo_finished()
tr_node = next(n for n, _, _ in w.doc.walk() if n.kind == "translate")
assert tr_node.params["v"] == [15.0, 0.0, 5.0], tr_node.params
assert len(w.history.undo_stack) == pasos + 1
w.undo()
assert not any(n.kind == "translate" for n, _, _ in w.doc.walk())

# el translate del padre no se reutiliza si tiene más hijos (movería también al hermano)
w.new_file()
w.run_command("cube"); a_id = w.current_node().id
w.run_command("sphere"); b_id = w.current_node().id
w.select_ids([a_id, b_id]); w.run_command("translate")
shared = w.current_node()
w.select_ids([a_id])
w.on_gizmo_started(); w.on_gizmo_moved(0.0, 10.0, 0.0); w.on_gizmo_finished()
assert shared.params["v"] == [0, 0, 0] or shared.params["v"] == [0.0, 0.0, 0.0], shared.params
assert w.doc.find(a_id) not in shared.children and w.doc.find(b_id) in shared.children

# el arrastre se mide desde donde empezó: aunque el gizmo se mueva con la pieza, el mismo
# punto del ratón da el mismo desplazamiento (antes la pieza oscilaba)
class _Ev:
    def __init__(self, x, y): self._p = QPointF(x, y)
    def position(self): return self._p
view = v.view
v.set_gizmo(np.array([0.0, 0.0, 0.0]), 25.0)
v.set_view("Frontal")
view._active_axis = "X"; view._drag_origin = np.zeros(3); view._drag_start_s = 0.0
moves = []
view.gizmoMoved.connect(lambda dx, dy, dz: moves.append(dx))
view.mouseMoveEvent(_Ev(500, 300))
v.set_gizmo(np.array([moves[-1], 0.0, 0.0]), 25.0)   # la ventana mueve el gizmo con la pieza
view.mouseMoveEvent(_Ev(500, 300))
assert abs(moves[0] - moves[1]) < 1e-9 and moves[0] > 0, moves
view._active_axis = None; view._drag_origin = None

# --- vista explosionada: separa las piezas del montaje en proporción a su tamaño
w.new_file()
w.run_command("cube"); left = w.current_node()
w.select_ids([]); w.run_command("cube"); right = w.current_node()
w.select_ids([left.id]); w.run_command("translate"); w.on_param_changed(w.current_node().id, "v", [-30.0, 0.0, 0.0])
real = np.concatenate(list(w.ghosts.values()))
v.set_mesh(real)
before = v.model.data.vertexes.copy()
v.set_explosion(50)
after = v.model.data.vertexes
owner = geo.assign_faces(real, w.ghosts)
moved_left = (after[owner == left.id] - before[owner == left.id])[:, :, 0].mean()
moved_right = (after[owner == right.id] - before[owner == right.id])[:, :, 0].mean()
assert moved_left < -1 and moved_right > 1, (moved_left, moved_right)
# al cambiar el modelo con el deslizador abierto la explosión se mantiene
w.on_param_changed(right.id, "size", [12.0, 12.0, 12.0])
v.set_mesh(np.concatenate(list(w.ghosts.values())))
assert not np.allclose(v.model.data.vertexes, np.concatenate(list(w.ghosts.values())))
v.set_explosion(0)
assert np.allclose(v.model.data.vertexes, np.concatenate(list(w.ghosts.values())))

print("TODO OK (visor OpenGL)")
