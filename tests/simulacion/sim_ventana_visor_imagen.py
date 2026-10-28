import os, sys, tempfile
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
APP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ["SCADGUI_SRC"] = APP
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "qtstub"))
sys.path.insert(0, APP)

from PySide6.QtWidgets import QFileDialog, QMainWindow
from PySide6.QtCore import QProcess
from scadgui.ui.mainwindow import MainWindow
from scadgui.model import Node, RawCode, generate
from scadgui.catalog import SPECS

from PySide6.QtCore import QSettings
QSettings.store["viewer"] = "image"
w = MainWindow("")
assert not w.gl
# 1. arranca con el ejemplo
kinds = [type(n).__name__ + ":" + getattr(n, "kind", "") for n, _, _ in w.doc.walk()]
print("ejemplo:", kinds)
assert w.doc.fn == 64 and len(w._items()) == 6, len(w._items())
assert w.code.text.toPlainText() == generate(w.doc).text
print("consola:", w.console.toPlainText().strip()[:120])

# 2. nuevo + crear piezas
w.new_file()
assert not w.doc.children
w.run_command("cube"); cube = w.current_node()
w.run_command("cylinder"); cyl = w.current_node()
assert cube.kind == "cube" and cyl.kind == "cylinder", (cube, cyl)
w.select_ids([cube.id, cyl.id])
w.run_command("difference")
diff = w.current_node()
assert diff.kind == "difference" and [c.id for c in diff.children] == [cube.id, cyl.id]
# añadir dentro del contenedor seleccionado
w.run_command("sphere")
sph = w.current_node()
assert sph in diff.children
# 3. propiedades + coalescencia de deshacer
n_undo = len(w.history.undo_stack)
w.on_param_changed(cyl.id, "r", 3.0)
w.on_param_changed(cyl.id, "r", 4.0)
assert len(w.history.undo_stack) == n_undo + 1
w.on_param_changed(cyl.id, "center", True)
w.on_renamed(cyl.id, "Agujero")
assert "cylinder(h = 10, r = 4, center = true); // Agujero" in w.code.text.toPlainText()
w.select_ids([cyl.id])
w.toggle_modifier("#")
assert w.doc.find(cyl.id).modifier == "#"
w.undo(); assert w.doc.find(cyl.id).modifier == ""
w.redo(); assert w.doc.find(cyl.id).modifier == "#"
w.undo(); w.undo()
assert w.doc.find(cyl.id).name == "Cilindro", w.doc.find(cyl.id).name
# 4. formularios de propiedades para todos los comandos
from scadgui.model import make_node
for k in SPECS:
    w.props.show_node(make_node(k), w.doc)
w.props.show_node(RawCode("for (i=[0:2]) cube(i);"), w.doc)
w.props.show_node(None, w.doc)
n = make_node("cube"); n.params["size"] = 5   # escalar en vez de vector -> editor de expresión
w.props.show_node(n, w.doc)
n.params["$fa"] = 12; w.props.show_node(n, w.doc)
# 5. operaciones del árbol
w.select_ids([sph.id]); w.move_selected(-1); w.outdent_selected()
assert sph in w.doc.children
w.select_ids([sph.id]); w.move_selected(-1); w.indent_selected()
# arrastrar y soltar (drag & drop)
w.tree.dropped.emit([sph.id], None, "into")
assert sph in w.doc.children
w.tree.dropped.emit([sph.id], diff.id, "into")
assert sph in diff.children
w.undo(); assert sph in w.doc.children
w.redo(); assert sph in diff.children
w.select_ids([diff.id]); w.duplicate()
dup = w.current_node(); assert dup.kind == "difference" and dup.id != diff.id
w.select_ids([dup.id]); w.unwrap_selected()
w.delete_selected()
print("arbol:", [ (n.kind, d) for n, d, _ in w.doc.walk()])
# 6. editar código a mano
w.code.start_editing()
assert w.code.editing
w.apply_code("difference() {\n cube(10);\n for(i=[0:1]) translate([i*5,0,0]) sphere(2);\n}\n")
assert not w.code.editing
d = w.doc.children[0]
assert d.kind == "difference" and isinstance(d.children[1], RawCode)
w.code.start_editing()
w.apply_code("difference() { cube(1);")   # error: se queda editando
assert w.code.editing and "No se pudo leer" in w.console.toPlainText()
w.code.stop_editing(discard=True)
# 7. clic en una línea del código selecciona la pieza
line = w.gen.lines[d.children[0].id][0]
w.on_code_line(line)
assert w.selected_ids() == [d.children[0].id]
w.edit_code_of(d.children[1].id); w.code.stop_editing(discard=True)
w.tree_menu(None)
# 8. vista previa y exportación con un openscad ficticio
w.runner.exe = None
w.render_view(False)
assert "No se encontró" in w.viewer.message
w.runner.exe = "/opt/openscad"
w.runner.backend = "manifold"
w.select_ids([d.children[0].id])
w.render_view(False)
exe, args = QProcess.started_args[-1]
print("args vista:", args)
src = args[-1]; code = open(src).read()
assert "#cube(10);" in code and "--preview" in args and "--backend=manifold" in args
# simular fallo por --backend no soportado -> reintento sin la opción
w.runner._read = lambda p: None
w.runner._buffer = ""
w.runner._all_output = "Error: unrecognised option '--backend=manifold'"
w.runner._finished(w.runner._proc, w.runner._job, 1)
exe, args2 = QProcess.started_args[-1]
assert not any(a.startswith("--backend") for a in args2), args2
w.runner._finished(w.runner._proc, w.runner._job, 1)
assert "no pudo generar la vista" in w.console.toPlainText()
w.render_view(True)
assert "--render" in QProcess.started_args[-1][1] and "#cube" not in open(QProcess.started_args[-1][1][-1]).read()
# roof -> --enable=roof
w.select_ids([d.children[0].id]); w.run_command("roof"); w.render_view(False)
assert "--enable=roof" in QProcess.started_args[-1][1]
w.undo()
out = os.path.join(tempfile.mkdtemp(), "pieza")
QFileDialog.next_save = out
w.export_file()
exe, args = QProcess.started_args[-1]
assert args[:2] == ["-o", out + ".stl"], args
# 9. guardar y volver a abrir
path = os.path.join(tempfile.mkdtemp(), "modelo")
QFileDialog.next_save = path
assert w.save_file_as()
saved = open(path + ".scad").read()
w.load(path + ".scad")
assert generate(w.doc).text == saved and w.path == path + ".scad"
# 10. importar archivo (ruta relativa al .scad)
stl = os.path.join(os.path.dirname(path), "piezas", "tornillo.stl")
QFileDialog.next_open = stl
w.select_ids([]); w.run_command("import")
assert w.current_node().params["file"] == "piezas/tornillo.stl", w.current_node().params
# 11. asistente de boceto 2D
w.run_command("sketch2d")
assert any(n.kind in ("offset", "square") for n, _, _ in w.doc.walk())
# 12. convertir selección en módulo y deshacer/rehacer
last_node = w.doc.children[-1]
w.select_ids([last_node.id])
w.convert_to_module()
assert "module " in w.code.text.toPlainText()
w.undo()
assert "module " not in w.code.text.toPlainText()
w.redo()
assert "module " in w.code.text.toPlainText()
# 13. variables y parámetros globales
w.on_variable_added("ancho", "50", "ancho base")
assert len(w.doc.get_variables()) == 1
w.on_variable_changed("ancho", "60", "nuevo ancho")
assert w.doc.get_variables()[0]["value"] == "60"
w.on_variable_deleted("ancho")
assert len(w.doc.get_variables()) == 0
# 14. plano técnico 2D
out_svg = os.path.join(tempfile.mkdtemp(), "plano")
QFileDialog.next_save = out_svg
w.open_drawing_dialog()
exe, args = QProcess.started_args[-1]
assert args[:2] == ["-o", out_svg + ".svg"], args
# 15. componentes estándar industriales (hardware)
w.select_ids([])
w.run_command("hardware")
assert any("ISO4762" in (n.name or "") or "Tornillo" in (n.name or "") for n, _, _ in w.doc.walk())
# 16. preferencias y configuración
w.open_preferences()
assert w.settings.value("colorscheme") is not None
assert w.settings.value("hardware_metric") == "M3"
assert w.settings.value("language") == "es"
print(w.code.text.toPlainText())
print("mensajes:", QMainWindow.messages[-3:])
print("TODO OK")
