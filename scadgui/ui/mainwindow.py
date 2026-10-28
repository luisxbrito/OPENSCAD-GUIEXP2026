"""Ventana principal: cinta de comandos, árbol, propiedades, vista 3D, código y consola."""

from __future__ import annotations

import html
import os
import re
import sys
import time
from typing import Optional

from PySide6.QtCore import QItemSelectionModel, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDockWidget, QFileDialog,
                               QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QSizePolicy, QSplitter, QTabWidget, QToolBar, QToolButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from .. import __version__
from .. import geometry as geo
from ..catalog import CATEGORIES, SPECS, specs_in
from ..i18n import get_language, set_language, tr
from ..model import Document, Node, RawCode, generate
from ..parser import ParseError, parse
from ..runner import OpenScadRunner, find_openscad
from .codeview import CodeView, mono_font
from .icons import icon
from .properties import PropertyPanel, choose_import_file
from .style import STYLESHEET

def _resolve_example_path(filename: str) -> str:
    """Resuelve la ruta a un archivo de ejemplo tanto en modo desarrollo como congelado (PyInstaller)."""
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(os.path.join(meipass, "examples", filename))
            candidates.append(os.path.join(meipass, filename))
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "examples", filename))
        candidates.append(os.path.join(exe_dir, filename))
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates.append(os.path.join(base, "examples", filename))
    for c in candidates:
        if os.path.isfile(c):
            return c
    return candidates[-1]


EXAMPLE_RUEDA = _resolve_example_path("rueda_con_eje_giratorio.scad")
EXAMPLE_PLACA = _resolve_example_path("placa_agujeros.scad")
EXAMPLE = EXAMPLE_RUEDA
EXPORT_FILTERS = ("STL (*.stl);;3MF (*.3mf);;OBJ (*.obj);;OFF (*.off);;AMF (*.amf);;"
                  "SVG – solo 2D (*.svg);;DXF – solo 2D (*.dxf);;PDF – solo 2D (*.pdf);;Imagen PNG (*.png)")


def _qt_color(name: str):
    """Nombres de color de OpenSCAD (los de la web/SVG, como "SteelBlue") vía QColor."""
    c = QColor(name)
    if not c.isValid():
        return None
    return (c.redF(), c.greenF(), c.blueF())


# --------------------------------------------------------------------------- deshacer

class History:
    def __init__(self, limit: int = 200):
        self.undo_stack: list[Document] = []
        self.redo_stack: list[Document] = []
        self.limit = limit
        self._last_key = None
        self._last_time = 0.0

    def push(self, doc: Document, key=None) -> None:
        """Guarda el estado anterior. Cambios seguidos del mismo campo se agrupan en uno."""
        now = time.monotonic()
        if key is not None and key == self._last_key and now - self._last_time < 1.5:
            self._last_time = now
            return
        self._last_key, self._last_time = key, now
        self.undo_stack.append(doc.snapshot())
        del self.undo_stack[:-self.limit]
        self.redo_stack.clear()

    def undo(self, current: Document) -> Optional[Document]:
        if not self.undo_stack:
            return None
        self.redo_stack.append(current.snapshot())
        self._last_key = None
        return self.undo_stack.pop()

    def redo(self, current: Document) -> Optional[Document]:
        if not self.redo_stack:
            return None
        self.undo_stack.append(current.snapshot())
        self._last_key = None
        return self.redo_stack.pop()

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._last_key = None


# --------------------------------------------------------------------------- cinta

class Ribbon(QTabWidget):
    commandTriggered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        from ..i18n import tr
        self.setObjectName("ribbon")
        self.setDocumentMode(True)
        self.buttons: dict[str, QToolButton] = {}
        for key, title, hint in CATEGORIES:
            page = QWidget()
            page.setObjectName("ribbonPage")
            row = QHBoxLayout(page)
            row.setContentsMargins(10, 6, 10, 6)
            row.setSpacing(6)
            for spec in specs_in(key):
                b = QToolButton()
                b.setObjectName("ribbonButton")
                b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                b.setIcon(icon(spec.name, "#1B2230"))
                b.setIconSize(QSize(26, 26))
                suffix = {"editor": " ·", "experimental": " (exp.)"}.get(spec.level, "")
                b.setText(f"{spec.label}{suffix}\n{spec.name}()")
                b.setToolTip(self._tooltip(spec))
                b.setMinimumWidth(86)
                if spec.level == "experimental":
                    b.setProperty("experimental", True)
                b.clicked.connect(lambda _=False, n=spec.name: self.commandTriggered.emit(n))
                row.addWidget(b)
                self.buttons[spec.name] = b
            if key == "solid":
                b_hw = QToolButton()
                b_hw.setObjectName("ribbonButton")
                b_hw.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                b_hw.setIcon(icon("hardware", "#1B2230"))
                b_hw.setIconSize(QSize(26, 26))
                b_hw.setText(tr("Tornillería ·\nEstándar"))
                b_hw.setToolTip("<b>Componentes estándar industriales</b><br>Tornillería ISO/DIN, tuercas, insertos térmicos, rodamientos y perfiles.")
                b_hw.setMinimumWidth(86)
                b_hw.clicked.connect(lambda: self.commandTriggered.emit("hardware"))
                row.addWidget(b_hw)
                self.buttons["hardware"] = b_hw
            if key == "shape2d":
                b = QToolButton()
                b.setObjectName("ribbonButton")
                b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                b.setIcon(icon("sketch", "#1B2230"))
                b.setIconSize(QSize(26, 26))
                b.setText(tr("Boceto 2D ·\nAsistente"))
                b.setToolTip("<b>Asistente de bocetos 2D</b><br>Perfiles paramétricos: rectángulos redondeados, ranuras, polígonos, estrellas, etc.")
                b.setMinimumWidth(86)
                b.clicked.connect(lambda: self.commandTriggered.emit("sketch2d"))
                row.addWidget(b)
                self.buttons["sketch2d"] = b

                b_draw = QToolButton()
                b_draw.setObjectName("ribbonButton")
                b_draw.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                b_draw.setIcon(icon("projection", "#1B2230"))
                b_draw.setIconSize(QSize(26, 26))
                b_draw.setText(tr("Plano 2D ·\nTécnico"))
                b_draw.setToolTip("<b>Generar plano técnico 2D</b><br>Lámina con vistas ortogonales, isométrica, marco y cajetín.")
                b_draw.setMinimumWidth(86)
                b_draw.clicked.connect(lambda: self.commandTriggered.emit("drawing2d"))
                row.addWidget(b_draw)
                self.buttons["drawing2d"] = b_draw
            if key == "bool":
                b_bool = QToolButton()
                b_bool.setObjectName("ribbonButton")
                b_bool.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                b_bool.setIcon(icon("difference", "#1B2230"))
                b_bool.setIconSize(QSize(26, 26))
                b_bool.setText(tr("Asistente ·\nBooleano"))
                b_bool.setToolTip("<b>" + tr("Asistente de operaciones booleanas") + "</b><br>" +
                                  tr("Configura qué sólido es la base y cuáles se restan, unen o intersectan."))
                b_bool.setMinimumWidth(86)
                b_bool.clicked.connect(lambda: self.commandTriggered.emit("bool_wizard"))
                row.addWidget(b_bool)
                self.buttons["bool_wizard"] = b_bool
            row.addStretch(1)
            tip = QLabel(hint)
            tip.setWordWrap(True)
            tip.setObjectName("ribbonHint")
            tip.setMaximumWidth(340)
            row.addWidget(tip)
            self.addTab(page, tr(title))

    def retranslate_ui(self) -> None:
        from ..i18n import tr
        for idx, (key, title, _) in enumerate(CATEGORIES):
            self.setTabText(idx, tr(title))

    @staticmethod
    def _tooltip(spec) -> str:
        params = ", ".join(p.name for p in spec.params) or "sin parámetros"
        extra = {"editor": "<br><i>Con editor propio (tabla, matriz o archivo).</i>",
                 "experimental": "<br><i>Experimental: requiere --enable=roof.</i>"}.get(spec.level, "")
        what = "Envuelve la selección" if spec.container else "Crea la pieza"
        return f"<b>{spec.label}</b> — <code>{spec.name}({params})</code><br>{what}.{extra}"


# --------------------------------------------------------------------------- árbol con arrastrar y soltar

class ModelTree(QTreeWidget):
    dropped = Signal(list, object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDropIndicatorShown(True)

    def dropEvent(self, event) -> None:
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_item = self.itemAt(pos)
        pos_enum = self.dropIndicatorPosition()

        source_ids = [item.data(0, Qt.ItemDataRole.UserRole) for item in self.selectedItems()
                      if item.data(0, Qt.ItemDataRole.UserRole) is not None]
        if not source_ids:
            event.ignore()
            return

        target_id = target_item.data(0, Qt.ItemDataRole.UserRole) if target_item is not None else None

        if pos_enum == QAbstractItemView.DropIndicatorPosition.AboveItem:
            position = "before"
        elif pos_enum == QAbstractItemView.DropIndicatorPosition.BelowItem:
            position = "after"
        elif pos_enum == QAbstractItemView.DropIndicatorPosition.OnItem:
            position = "into"
        else:
            position = "into"
            target_id = None

        event.accept()
        self.dropped.emit(source_ids, target_id, position)


# --------------------------------------------------------------------------- ventana

class MainWindow(QMainWindow):
    def __init__(self, path: str = ""):
        super().__init__()
        self.settings = QSettings("OpenSCAD-GUI-Mejorada", "app")
        from ..i18n import set_language, tr
        set_language(str(self.settings.value("language", "es", str) or "es"))
        self.doc = Document()
        self.path = ""
        self.modified = False
        self.history = History()
        self.gen = generate(self.doc)
        self._syncing = False

        self.runner = OpenScadRunner(self)
        self.runner.exe = find_openscad(self.settings.value("openscad_path", "", str))
        self.runner.backend = self.settings.value("backend", "", str)

        self.setStyleSheet(STYLESHEET)
        self.setWindowIcon(icon("cube", "#2563EB"))
        self.resize(1440, 900)
        self._action_defs: list[tuple[QAction, str, Optional[str]]] = []
        self._build_actions()
        self._build_menus()
        self._build_toolbars()
        self._build_central()
        self._build_docks()
        self._connect()
        self.statusBar().showMessage("Listo")
        self.units = QLabel("Unidades: mm")
        self.units.setFont(mono_font(9))
        self.statusBar().addPermanentWidget(self.units)

        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        QTimer.singleShot(0, lambda: self._startup(path))

    # ------------------------------------------------------------- construcción
    def _act(self, text, slot, shortcut=None, icon_name=None, tip=None) -> QAction:
        from ..i18n import tr
        a = QAction(icon(icon_name) if icon_name else QIcon(), tr(text), self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip:
            t = tr(tip)
            a.setToolTip(t)
            a.setStatusTip(t)
        a.triggered.connect(slot)
        if hasattr(self, "_action_defs"):
            self._action_defs.append((a, text, tip))
        return a

    def _build_actions(self) -> None:
        S = QKeySequence.StandardKey
        self.a_new = self._act("Nuevo", self.new_file, S.New, "new")
        self.a_open = self._act("Abrir…", self.open_file, S.Open, "open")
        self.a_save = self._act("Guardar", self.save_file, S.Save, "save")
        self.a_save_as = self._act("Guardar como…", self.save_file_as, S.SaveAs)
        self.a_export = self._act("Exportar…", self.export_file, "Ctrl+E", "export",
                                  "STL, 3MF, OBJ, OFF, AMF, SVG, DXF, PDF o PNG")
        self.a_drawing = self._act("Generar plano técnico 2D…", self.open_drawing_dialog, "Ctrl+Shift+D", "projection",
                                   "Lámina técnica 2D con vistas ortogonales, marco y cajetín")
        self.a_example = self._act("Abrir ejemplo", self.open_example)
        self.a_prefs = self._act("Preferencias…", self.open_preferences, "Ctrl+,", None,
                                 "Configuración de OpenSCAD y preferencias de la aplicación")
        self.a_config = self._act("Configurar OpenSCAD…", self.open_preferences)
        self.a_quit = self._act("Salir", self.close, S.Quit)
        self.a_undo = self._act("Deshacer", self.undo, S.Undo, "undo")
        self.a_redo = self._act("Rehacer", self.redo, "Ctrl+Y", "redo")
        self.a_dup = self._act("Duplicar", self.duplicate, "Ctrl+D", "duplicate")
        self.a_make_module = self._act("Convertir en módulo…", self.convert_to_module, "Ctrl+M", "group",
                                       "Convierte la selección en un módulo reutilizable con parámetros")
        self.a_del = self._act("Eliminar", self.delete_selected, S.Delete, "delete")
        self.a_bool_wizard = self._act("Asistente booleano…", self.open_boolean_dialog, "Ctrl+Shift+O", "difference",
                                       "Asistente interactivo para restar, unir o intersecar sólidos")
        self.a_operation_helper = self._act("Guía y Helper de operaciones…", self.open_operation_helper, "Ctrl+H", "preview",
                                            "Guía interactiva con explicaciones, pro-tips y ejemplos de cada operación")
        self.a_sketch = self._act("Asistente de boceto 2D…", self.open_sketch_dialog, "Ctrl+Shift+B", "sketch",
                                  "Generador de perfiles 2D paramétricos para extrusión")
        self.a_hardware = self._act("Insertar componente estándar…", self.open_hardware_dialog, "Ctrl+Shift+H", "hardware",
                                    "Biblioteca de tornillería ISO/DIN, tuercas, insertos y rodamientos")
        self.a_preview = self._act("Vista previa", lambda: self.render_view(False), "F5", "preview",
                                   "Vista previa rápida (resalta la selección)")
        self.a_render = self._act("Render", lambda: self.render_view(True), "F6", "render_action",
                                  "Render final: geometría exacta, sin resaltados")
        self.a_about = self._act("Acerca de", self.about)
        self.a_del.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def _build_menus(self) -> None:
        from ..i18n import tr
        mb = self.menuBar()
        m = mb.addMenu(tr("&Archivo"))
        for a in (self.a_new, self.a_open, self.a_example, None, self.a_save, self.a_save_as,
                  self.a_export, self.a_drawing, None, self.a_prefs, None, self.a_quit):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(tr("&Editar"))
        for a in (self.a_undo, self.a_redo, None, self.a_dup, self.a_make_module, self.a_del, None, self.a_prefs):
            m.addSeparator() if a is None else m.addAction(a)
        self.view_menu = mb.addMenu(tr("&Ver"))
        m = mb.addMenu(tr("&Diseño"))
        m.addAction(self.a_make_module)
        m.addAction(self.a_bool_wizard)
        m.addAction(self.a_operation_helper)
        m.addAction(self.a_sketch)
        m.addAction(self.a_hardware)
        m.addAction(self.a_drawing)
        m.addSeparator()
        m.addAction(self.a_preview)
        m.addAction(self.a_render)
        ayuda_m = mb.addMenu(tr("A&yuda"))
        ayuda_m.addAction(self.a_operation_helper)
        ayuda_m.addAction(self.a_about)

    def _build_toolbars(self) -> None:
        tb = QToolBar(tr("Principal"))
        tb.setObjectName("mainToolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        for a in (self.a_new, self.a_open, self.a_save, None, self.a_undo, self.a_redo, None,
                  self.a_preview, self.a_render, None, self.a_export):
            tb.addSeparator() if a is None else tb.addAction(a)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        tb.addWidget(QLabel(tr("Motor ")))
        self.engine = QComboBox()
        self.engine.addItem(tr("Automático"), "")
        self.engine.addItem(tr("Manifold (rápido)"), "manifold")
        self.engine.addItem(tr("CGAL (clásico)"), "cgal")
        idx = max(0, self.engine.findData(self.runner.backend))
        self.engine.setCurrentIndex(idx)
        self.engine.currentIndexChanged.connect(self._engine_changed)
        tb.addWidget(self.engine)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        self.addToolBarBreak()

        rb = QToolBar(tr("Comandos"))
        rb.setObjectName("ribbonToolbar")
        rb.setMovable(False)
        self.ribbon = Ribbon()
        rb.addWidget(self.ribbon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, rb)
        self.ribbon_bar = rb

    def _build_central(self) -> None:
        """Visor OpenGL si están pyqtgraph y PyOpenGL; si no, el visor de imágenes."""
        self.gl = False
        self._gl_error = ""
        self.ghosts: dict = {}
        if self.settings.value("viewer", "gl", str) != "image":
            try:
                from .viewer3d import Viewer3D
                self.viewer = Viewer3D()
                self.gl = True
                self.viewer.gizmoStarted.connect(self.on_gizmo_started)
                self.viewer.gizmoMoved.connect(self.on_gizmo_moved)
                self.viewer.gizmoFinished.connect(self.on_gizmo_finished)
            except Exception as exc:  # noqa: BLE001 - falta una biblioteca o falla OpenGL
                self._gl_error = f"{type(exc).__name__}: {exc}"
        if not self.gl:
            from .viewer import Viewport
            self.viewer = Viewport()
        self.setCentralWidget(self.viewer)
        self.a_gl = QAction(tr("Visor OpenGL (requiere reiniciar)"), self)
        self.a_gl.setCheckable(True)
        self.a_gl.setChecked(self.settings.value("viewer", "gl", str) != "image")
        self.a_gl.toggled.connect(self._toggle_gl)
        self.view_menu.addAction(self.a_gl)
        self.view_menu.addSeparator()

    def _build_docks(self) -> None:
        # ----- Modelo: árbol + propiedades
        model = QWidget()
        model.setObjectName("modelPanel")
        lay = QVBoxLayout(model)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QWidget()
        head.setObjectName("panelHead")
        row = QHBoxLayout(head)
        row.setContentsMargins(12, 8, 8, 6)
        row.setSpacing(3)
        t = QLabel(tr("MODELO"))
        t.setObjectName("sectionTitle")
        row.addWidget(t)
        row.addStretch(1)
        self.mod_buttons = {}
        for mod, tip in (("#", tr("Resaltar (#)")), ("%", tr("Transparente (%)")), ("!", tr("Mostrar solo esta (!)")),
                         ("*", tr("Desactivar (*)"))):
            b = QToolButton()
            b.setText(mod)
            b.setCheckable(True)
            b.setObjectName("modButton")
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, m=mod: self.toggle_modifier(m))
            row.addWidget(b)
            self.mod_buttons[mod] = b
        lay.addWidget(head)

        tools = QWidget()
        tools.setObjectName("treeTools")
        trow = QHBoxLayout(tools)
        trow.setContentsMargins(8, 0, 8, 6)
        trow.setSpacing(3)
        self.tree_tools = []
        for name, tip, slot in (("up", tr("Subir"), lambda: self.move_selected(-1)),
                                ("down", tr("Bajar"), lambda: self.move_selected(1)),
                                ("translate", tr("Meter en el contenedor de arriba"), self.indent_selected),
                                ("outdent", tr("Sacar del grupo"), self.outdent_selected),
                                ("unwrap", tr("Quitar la operación y dejar sus piezas"), self.unwrap_selected),
                                ("duplicate", tr("Duplicar (Ctrl+D)"), self.duplicate),
                                ("delete", tr("Eliminar (Supr)"), self.delete_selected)):
            b = QToolButton()
            b.setIcon(icon(name, "#3D4756"))
            b.setIconSize(QSize(16, 16))
            b.setToolTip(tip)
            b.setObjectName("treeTool")
            b.clicked.connect(slot)
            trow.addWidget(b)
            self.tree_tools.append(b)
        trow.addStretch(1)
        lay.addWidget(tools)

        self.tree = ModelTree()
        self.tree.setObjectName("modelTree")
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([tr("Nombre"), tr("Comando")])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setStretchLastSection(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setIconSize(QSize(16, 16))
        self.tree.setIndentation(16)
        self.tree.setUniformRowHeights(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.addAction(self.a_del)
        self.tree.dropped.connect(self.on_nodes_dropped)

        self.props = PropertyPanel()
        self.props.setObjectName("propsPanel")
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.tree)
        split.addWidget(self.props)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        lay.addWidget(split, 1)
        self.model_panel = model

        self.dock_model = self._dock(tr("Modelo"), model, Qt.DockWidgetArea.LeftDockWidgetArea, 320)

        # ----- Código
        self.code = CodeView()
        self.dock_code = self._dock(tr("Código"), self.code, Qt.DockWidgetArea.RightDockWidgetArea, 420)

        # ----- Consola
        console_box = QWidget()
        clay = QVBoxLayout(console_box)
        clay.setContentsMargins(0, 0, 0, 0)
        self.console = QPlainTextEdit()
        self.console.setObjectName("console")
        self.console.setReadOnly(True)
        self.console.setFont(mono_font(9))
        self.console.setMaximumBlockCount(2000)
        clay.addWidget(self.console)
        self.dock_console = self._dock(tr("Consola"), console_box, Qt.DockWidgetArea.BottomDockWidgetArea, 0)
        self.resizeDocks([self.dock_console], [130], Qt.Orientation.Vertical)

        from .variables import VariablesPanel
        self.vars_panel = VariablesPanel()
        self.dock_vars = self._dock(tr("Variables"), self.vars_panel, Qt.DockWidgetArea.LeftDockWidgetArea, 320)
        self.tabifyDockWidget(self.dock_model, self.dock_vars)
        if hasattr(self.dock_model, "raise_"):
            self.dock_model.raise_()
        self.vars_panel.variableAdded.connect(self.on_variable_added)
        self.vars_panel.variableChanged.connect(self.on_variable_changed)
        self.vars_panel.variableDeleted.connect(self.on_variable_deleted)

        for d in (self.dock_model, self.dock_vars, self.dock_code, self.dock_console):
            self.view_menu.addAction(d.toggleViewAction())

    def _dock(self, title, widget, area, width) -> QDockWidget:
        d = QDockWidget(title, self)
        d.setObjectName("dock_" + title)
        d.setWidget(widget)
        d.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                      QDockWidget.DockWidgetFeature.DockWidgetClosable |
                      QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(area, d)
        if width:
            self.resizeDocks([d], [width], Qt.Orientation.Horizontal)
        return d

    def _connect(self) -> None:
        self.ribbon.commandTriggered.connect(self.run_command)
        self.tree.itemSelectionChanged.connect(self.on_selection)
        self.tree.customContextMenuRequested.connect(self.tree_menu)
        self.tree.itemDoubleClicked.connect(self._tree_double_click)
        self.props.changed.connect(self.on_param_changed)
        self.props.renamed.connect(self.on_renamed)
        self.props.editCode.connect(self.edit_code_of)
        self.props.fnChanged.connect(self.on_fn_changed)
        self.props.selectNode.connect(lambda nid: self.select_ids([nid]))
        self.props.openBooleanWizard.connect(self.open_boolean_dialog)
        self.props.setDifferenceBase.connect(self.set_difference_base)
        self.props.openOperationHelper.connect(self.open_operation_helper)
        self.code.lineClicked.connect(self.on_code_line)
        self.code.applyRequested.connect(self.apply_code)
        self.code.editingChanged.connect(self.on_code_editing)
        self.viewer.renderRequested.connect(lambda: self.render_view(False))
        self.viewer.setup.clicked.connect(self.configure_openscad)
        self.runner.imageReady.connect(self.on_image)
        self.runner.failed.connect(self.on_render_failed)
        self.runner.log.connect(self.log_openscad)
        self.runner.started.connect(lambda d: self.viewer.status.setText(d))
        self.runner.exportDone.connect(self.on_exported)
        self.runner.meshReady.connect(self.on_mesh)
        self.runner.meshEmpty.connect(self.on_mesh_empty)
        if self.gl:
            self.viewer.picked.connect(self.on_pick)
            self.viewer.measured.connect(lambda text: self.log(text, "echo"))

    def _startup(self, path: str) -> None:
        version = self.runner.version()
        if self.runner.exe:
            self.runner.check_backend_support(version)
            self.log(f"OpenSCAD encontrado: {self.runner.exe} ({version or 'versión desconocida'})", "info")
            self.units.setText(f"OpenSCAD {version}  ·  {tr('Unidades: mm')}" if version else tr("Unidades: mm"))
        else:
            self.log("No se encontró OpenSCAD. Instálalo desde openscad.org o elige el ejecutable en "
                     "Archivo › Configurar OpenSCAD…", "warn")
        if self._gl_error:
            self.log("Visor OpenGL no disponible (" + self._gl_error + "). Se usa el visor de imágenes. "
                     "Instala lo necesario con:  python -m pip install pyqtgraph PyOpenGL numpy", "warn")
        is_stub = "qtstub" in getattr(sys.modules.get("PySide6"), "__file__", "") or bool(os.environ.get("SCADGUI_SRC"))
        if path:
            self.load(path)
        elif is_stub and os.path.isfile(EXAMPLE_PLACA):
            with open(EXAMPLE_PLACA, encoding="utf-8") as fh:
                self.set_document(parse(fh.read()))
        elif os.path.isfile(EXAMPLE_RUEDA):
            self.open_example()
        elif os.path.isfile(EXAMPLE_PLACA):
            with open(EXAMPLE_PLACA, encoding="utf-8") as fh:
                self.set_document(parse(fh.read()))
        else:
            self.set_document(Document())

    # ------------------------------------------------------------- documento
    def set_document(self, doc: Document, path: str = "", keep_history: bool = False) -> None:
        self.doc = doc
        self.path = path
        self.modified = False
        if not keep_history:
            self.history.clear()
        self.props.base_dir = os.path.dirname(path) if path else ""
        self.rebuild_tree([])
        self.refresh_code()
        self.update_title()
        if hasattr(self, "vars_panel"):
            self.vars_panel.update_doc(self.doc)
        self.render_view(False)

    def update_title(self) -> None:
        name = os.path.basename(self.path) if self.path else "sin título.scad"
        self.setWindowTitle(f"{name}{' *' if self.modified else ''} — OpenSCAD GUI Mejorada")
        self.a_undo.setEnabled(bool(self.history.undo_stack))
        self.a_redo.setEnabled(bool(self.history.redo_stack))

    def mutate(self, change, select=None, key=None, rebuild_tree=True) -> None:
        """Aplica un cambio al modelo con deshacer, y actualiza código y vista."""
        before = self.doc.snapshot()
        try:
            result = change()
        except ValueError as exc:
            self.statusBar().showMessage(str(exc), 4000)
            return
        if result is False:
            return
        self.history.push(before, key)
        self.modified = True
        if rebuild_tree:
            self.rebuild_tree(select if select is not None else self.selected_ids())
        self.refresh_code()
        self.update_title()
        if hasattr(self, "vars_panel"):
            self.vars_panel.refresh()
        self.schedule_preview()

    # ------------------------------------------------------------- árbol
    def rebuild_tree(self, select_ids) -> None:
        self._syncing = True
        self.tree.clear()
        wanted = set(select_ids or [])
        to_select = []

        def add(node, parent_item, parent_node=None, child_index=0):
            item = QTreeWidgetItem(parent_item)
            self._fill_item(item, node, parent_node, child_index)
            if node.id in wanted:
                to_select.append(item)
            for idx, child in enumerate(node.children):
                add(child, item, node, idx)

        for idx, n in enumerate(self.doc.children):
            add(n, self.tree.invisibleRootItem(), None, idx)
        self.tree.expandAll()
        for item in to_select:
            item.setSelected(True)
        if to_select:
            self.tree.setCurrentItem(to_select[-1], 0, QItemSelectionModel.SelectionFlag.NoUpdate)
            self.tree.scrollToItem(to_select[-1])
        self._syncing = False
        self.on_selection()

    def _fill_item(self, item: QTreeWidgetItem, node, parent_node=None, child_index: int = 0) -> None:
        item.setData(0, Qt.ItemDataRole.UserRole, node.id)
        item.setText(0, node.label)
        if isinstance(node, RawCode):
            item.setIcon(0, icon("comment" if node.is_comment else "lock", "#8A5A00"))
            item.setText(1, tr("comentario") if node.is_comment else tr("código"))
            item.setToolTip(0, node.text)
            f = item.font(0)
            f.setItalic(True)
            item.setFont(0, f)
            item.setForeground(0, QColor("#5A6474"))
        else:
            item.setIcon(0, icon(node.kind, "#3D4756"))
            cmd_text = f"{node.modifier}{node.kind}"
            extra_tip = ""

            # Clarificación didáctica del rol en operaciones booleanas
            if parent_node is not None and getattr(parent_node, "kind", "") == "difference":
                if child_index == 0:
                    cmd_text += " [Base (+)]"
                    extra_tip = f"\n⭐ {tr('difference: Sólido BASE (al que se le resta)')}"
                else:
                    base_label = parent_node.children[0].label if parent_node.children else tr("Base")
                    cmd_text += " [- Resta]"
                    extra_tip = f"\n✂️ {tr('difference: Sólido que se RESTA a')} '{base_label}'"
            elif parent_node is not None and getattr(parent_node, "kind", "") == "intersection":
                cmd_text += " [∩ Interseca]"
                extra_tip = f"\n🔍 {tr('intersection: Sólido intersecado (volumen común)')}"
            elif parent_node is not None and getattr(parent_node, "kind", "") == "union":
                cmd_text += " [∪ Unión]"
                extra_tip = f"\n➕ {tr('union: Sólido fusionado en la unión')}"

            item.setText(1, cmd_text)
            item.setToolTip(0, node.call() + extra_tip)
            item.setFont(1, mono_font(9))
            if node.modifier == "*":
                item.setForeground(0, QColor("#9AA3AF"))
        item.setForeground(1, QColor("#5A6474"))
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled
        if getattr(node, "is_container", False):
            flags |= Qt.ItemFlag.ItemIsDropEnabled
        item.setFlags(flags)

    def _items(self) -> list:
        """Todos los elementos del árbol, en orden."""
        result = []

        def rec(item):
            for i in range(item.childCount()):
                child = item.child(i)
                result.append(child)
                rec(child)
        rec(self.tree.invisibleRootItem())
        return result

    def _item_for(self, node_id: int) -> Optional[QTreeWidgetItem]:
        for item in self._items():
            if item.data(0, Qt.ItemDataRole.UserRole) == node_id:
                return item
        return None

    def selected_ids(self) -> list[int]:
        ids = {i.data(0, Qt.ItemDataRole.UserRole) for i in self.tree.selectedItems()}
        return [nid for nid in self.doc.order() if nid in ids]

    def current_node(self):
        ids = self.selected_ids()
        return self.doc.find(ids[0]) if len(ids) == 1 else None

    def on_selection(self) -> None:
        if self._syncing:
            return
        ids = self.selected_ids()
        node = self.doc.find(ids[0]) if len(ids) == 1 else None
        self.props.show_node(node, self.doc)
        span = self.gen.lines.get(node.id) if node is not None else None
        self._syncing = True
        self.code.highlight_span(span)
        self._syncing = False
        editable = [self.doc.find(i) for i in ids]
        editable = [n for n in editable if isinstance(n, Node)]
        for mod, b in self.mod_buttons.items():
            b.setEnabled(bool(editable))
            b.setChecked(bool(editable) and all(n.modifier == mod for n in editable))
        if node is not None:
            kind = tr("código") if isinstance(node, RawCode) else f"{node.kind}()"
            self.viewer.set_selection_text(f"{tr('Seleccionado')}: {kind} · {node.label}")
        elif ids:
            self.viewer.set_selection_text(f"{len(ids)} {tr('piezas seleccionadas')}")
        else:
            self.viewer.set_selection_text("")
        if self.gl:
            self._update_highlight()
        else:
            self.schedule_preview()  # el visor de imágenes resalta con # y necesita otra imagen

    def select_ids(self, ids) -> None:
        self._syncing = True
        self.tree.clearSelection()
        wanted = set(ids)
        last = None
        for item in self._items():
            if item.data(0, Qt.ItemDataRole.UserRole) in wanted:
                item.setSelected(True)
                last = item
        if last is not None:
            self.tree.scrollToItem(last)
        self._syncing = False
        self.on_selection()

    def tree_menu(self, pos) -> None:
        menu = QMenu(self)
        node = self.current_node()
        if node is not None and isinstance(node, RawCode):
            menu.addAction(tr("Editar en el código")).triggered.connect(lambda: self.edit_code_of(node.id))
            menu.addSeparator()

        # Opciones contextuales para operaciones booleanas
        if node is not None:
            _, parent = self.doc.parent_list(node.id)
            if parent is not None and getattr(parent, "kind", "") == "difference":
                if parent.children and parent.children[0].id != node.id:
                    menu.addAction("⭐ " + tr("Hacer sólido Base (al que se le resta)")).triggered.connect(
                        lambda: self.set_difference_base(parent.id, node.id)
                    )
                    menu.addSeparator()

            if getattr(node, "kind", "") in ("difference", "union", "intersection"):
                menu.addAction(icon(node.kind), "⚡ " + tr("Asistente booleano…")).triggered.connect(
                    lambda: self.open_boolean_dialog(node.id)
                )
                menu.addSeparator()
            elif parent is not None and getattr(parent, "kind", "") in ("difference", "union", "intersection"):
                menu.addAction(icon(parent.kind), "⚡ " + tr("Asistente booleano (del grupo)…")).triggered.connect(
                    lambda: self.open_boolean_dialog(parent.id)
                )
                menu.addSeparator()

        if node is not None and getattr(node, "kind", ""):
            menu.addAction("💡 " + tr("Guía y Helper de esta operación…")).triggered.connect(
                lambda: self.open_operation_helper(node.kind)
            )
            menu.addSeparator()

        menu.addAction("⚡ " + tr("Nueva operación booleana…")).triggered.connect(
            lambda: self.open_boolean_dialog(node.id if node is not None else None)
        )
        wrap = menu.addMenu(tr("Envolver en…"))
        for kind in ("translate", "rotate", "scale", "mirror", "color", "union", "difference",
                     "intersection", "hull", "linear_extrude"):
            a = wrap.addAction(icon(kind), SPECS[kind].label + f"  ({kind})")
            a.triggered.connect(lambda _=False, k=kind: self.run_command(k))
        menu.addAction(icon("outdent"), tr("Sacar del grupo")).triggered.connect(self.outdent_selected)
        menu.addAction(icon("unwrap"), tr("Quitar la operación (deja sus piezas)")).triggered.connect(
            self.unwrap_selected)
        menu.addSeparator()
        menu.addAction(self.a_make_module)
        menu.addAction(self.a_dup)
        menu.addAction(self.a_del)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _tree_double_click(self, item, column) -> None:
        nid = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(self.doc.find(nid), RawCode):
            self.edit_code_of(nid)

    # ------------------------------------------------------------- comandos
    def open_sketch_dialog(self) -> None:
        from .sketch import SketchDialog, create_sketch_node
        dlg = SketchDialog(self)
        if dlg.exec():
            profile, params, extrude_3d, extrude_h = dlg.get_result()
            sel = self.selected_ids()
            target_id = sel[0] if len(sel) == 1 else None
            root = create_sketch_node(profile, params, self.doc.unique_name, extrude_3d, extrude_h)

            def change():
                target = self.doc.find(target_id) if target_id is not None else None
                if target is not None and target.is_container:
                    target.children.append(root)
                else:
                    self.doc.children.append(root)

            self.mutate(change, select=[root.id])
            self.statusBar().showMessage(f"Perfil 2D creado: {root.name}", 4000)

    def open_hardware_dialog(self) -> None:
        from ..hardware import (create_bearing_node, create_heat_set_node,
                                create_nut_node, create_profile_node,
                                create_screw_node, create_washer_node)
        from .hardware_dialog import HardwareDialog

        sel = self.selected_ids()
        def_m = self.settings.value("hardware_metric", "M3", str)
        def_fit = self.settings.value("hardware_fit", "medium", str)
        dlg = HardwareDialog(has_selection=bool(sel), default_metric=def_m, default_fit=def_fit, parent=self)
        if dlg.exec():
            res = dlg.get_result()
            cat = res["category"]
            std = res["standard"]
            size = res["size"]
            length = res["length"]
            mode = res["mode"]
            fit = res["fit"]
            subtract = res["subtract"]

            if cat == "screw":
                node = create_screw_node(std, size, length, mode=mode, fit=fit, unique_fn=self.doc.unique_name)
            elif cat == "nut":
                node = create_nut_node(std, size, mode=mode, fit=fit, unique_fn=self.doc.unique_name)
            elif cat == "insert":
                node = create_heat_set_node(size, mode=mode, unique_fn=self.doc.unique_name)
            elif cat == "washer":
                node = create_washer_node(size, unique_fn=self.doc.unique_name)
            elif cat == "bearing":
                node = create_bearing_node(size, mode=mode, fit=fit, unique_fn=self.doc.unique_name)
            elif cat == "profile":
                node = create_profile_node(size, length, unique_fn=self.doc.unique_name)
            else:
                return

            if subtract and sel:
                target_id = sel[0]
                target_node = self.doc.find(target_id)
                if target_node is not None:
                    def change_sub():
                        if getattr(target_node, "kind", "") == "difference":
                            target_node.children.append(node)
                        else:
                            diff = self.doc.wrap([target_id], "difference")
                            diff.children.append(node)
                    self.mutate(change_sub, select=[node.id])
                    self.statusBar().showMessage(f"Taladro de {size} restado en {target_node.name}", 4000)
                    return

            target_id = sel[0] if len(sel) == 1 else None
            def change_add():
                target = self.doc.find(target_id) if target_id is not None else None
                if target is not None and target.is_container:
                    target.children.append(node)
                else:
                    self.doc.children.append(node)

            self.mutate(change_add, select=[node.id])
            self.statusBar().showMessage(f"Componente añadido: {node.name or node.label}", 4000)

    def open_drawing_dialog(self) -> None:
        from ..drawing import generate_technical_drawing_code
        from .drawing_dialog import DrawingDialog

        sel = self.selected_ids()
        def_author = self.settings.value("drawing_author", "Diseñador CAD", str)
        def_sheet = self.settings.value("drawing_sheet", "A4", str)
        dlg = DrawingDialog(has_selection=bool(sel), default_author=def_author, default_sheet=def_sheet, parent=self)
        if dlg.exec():
            cfg = dlg.get_config()
            if cfg.get("use_selection") and sel:
                nodes = [self.doc.find(i) for i in sel if self.doc.find(i) is not None]
                target_code = "\n".join(generate(n, header=False).text.strip() for n in nodes)
            else:
                target_code = generate(self.doc, header=False).text

            drawing_code = generate_technical_drawing_code(
                target_code=target_code,
                title=cfg.get("title", "Plano Técnico"),
                author=cfg.get("author", ""),
                sheet_size=cfg.get("sheet_size", "A4"),
                scale=float(cfg.get("scale", 1.0)),
                views=cfg.get("views"),
                include_border=bool(cfg.get("include_border", True)),
            )

            if cfg.get("action") == "export":
                if not self.runner.exe:
                    self.configure_openscad()
                    if not self.runner.exe:
                        return
                base = os.path.splitext(self.path)[0] if self.path else os.path.join(
                    self.settings.value("last_dir", "", str), "plano_tecnico")
                filters = "SVG (*.svg);;DXF (*.dxf);;PDF (*.pdf);;Todos (*)"
                path, chosen = QFileDialog.getSaveFileName(self, "Exportar plano técnico", base + ".svg", filters)
                if not path:
                    return
                if not os.path.splitext(path)[1]:
                    ext = ".svg"
                    if "*.dxf" in chosen:
                        ext = ".dxf"
                    elif "*.pdf" in chosen:
                        ext = ".pdf"
                    path += ext
                self.runner.export(drawing_code, os.path.dirname(self.path) if self.path else "", path)
            elif cfg.get("action") == "insert":
                def change():
                    raw = RawCode(drawing_code)
                    self.doc.children.append(raw)
                self.mutate(change)
                self.statusBar().showMessage("Plano técnico insertado en el modelo", 4000)

    def open_boolean_dialog(self, node_id: Optional[int] = None) -> None:
        from .boolean_dialog import BooleanDialog
        sel = self.selected_ids()
        initial_kind = "difference"
        if node_id is not None:
            n = self.doc.find(node_id)
            if n is not None:
                if getattr(n, "kind", "") in ("difference", "union", "intersection"):
                    initial_kind = n.kind
                    sel = [c.id for c in n.children]
                else:
                    _, parent = self.doc.parent_list(node_id)
                    if parent is not None and getattr(parent, "kind", "") in ("difference", "union", "intersection"):
                        initial_kind = parent.kind
                        sel = [c.id for c in parent.children]
                    else:
                        sel = [node_id]

        dlg = BooleanDialog(self.doc, initial_kind=initial_kind, selected_ids=sel, parent=self)
        if dlg.exec():
            res = dlg.get_result()
            kind = res["kind"]
            ordered_ids = res["ordered_ids"]
            if not ordered_ids:
                return

            def change():
                target_container = None
                if node_id is not None:
                    cand = self.doc.find(node_id)
                    if cand is not None and getattr(cand, "kind", "") in ("difference", "union", "intersection"):
                        target_container = cand
                    else:
                        _, p = self.doc.parent_list(node_id)
                        if p is not None and getattr(p, "kind", "") in ("difference", "union", "intersection"):
                            target_container = p

                if target_container is not None and target_container.id not in ordered_ids:
                    target_container.kind = kind
                    # Preservar el orden exacto de los hijos configurados
                    children_nodes = []
                    for cid in ordered_ids:
                        cn = self.doc.find(cid)
                        if cn is not None:
                            children_nodes.append(cn)
                    target_container.children = children_nodes
                    return target_container
                else:
                    return self.doc.wrap_ordered(ordered_ids, kind)

            created = {}
            def mutate_cb():
                created["node"] = change()

            self.mutate(mutate_cb, select=[ordered_ids[0]] if ordered_ids else None)
            if "node" in created and created["node"] is not None:
                self.select_ids([created["node"].id])
                self.statusBar().showMessage(f"Operación booleana aplicada: {kind}()", 4000)

    def set_difference_base(self, diff_id: int, new_base_id: int) -> None:
        def change():
            self.doc.set_difference_base(diff_id, new_base_id)
        self.mutate(change, select=[new_base_id])
        node = self.doc.find(new_base_id)
        name = node.label if node is not None else tr("Pieza")
        self.statusBar().showMessage(f"{name} {tr('establecido como sólido Base (+)')}", 4000)

    def open_operation_helper(self, kind: str = "translate") -> None:
        from .operation_helper import OperationHelperDialog
        target_kind = kind if isinstance(kind, str) and kind else "translate"
        dlg = OperationHelperDialog(current_kind=target_kind, doc=self.doc, parent=self)
        dlg.exec()

    def run_command(self, kind: str) -> None:
        if kind == "bool_wizard":
            self.open_boolean_dialog()
            return
        if kind == "sketch2d":
            self.open_sketch_dialog()
            return
        if kind == "hardware":
            self.open_hardware_dialog()
            return
        if kind == "drawing2d":
            self.open_drawing_dialog()
            return
        spec = SPECS[kind]
        sel = self.selected_ids()
        target = sel[0] if len(sel) == 1 else None
        created = {}

        if spec.category == "imp":
            path = choose_import_file(self, kind, self.props.base_dir)
            if not path:
                return

            def change():
                node = self.doc.add(kind, target)
                node.params["file"] = path
                created["node"] = node
        elif spec.container and sel:
            def change():
                created["node"] = self.doc.wrap(sel, kind)
            top = self.doc._top_selection(sel)
            if spec.category == "bool" and kind != "group" and len(top) < 2:
                self.log(f"{spec.label}: normalmente se usa con 2 o más piezas seleccionadas "
                         "(Ctrl+clic en el árbol). Puedes meter más piezas dentro después.", "info")
        else:
            def change():
                created["node"] = self.doc.add(kind, target)
        self.mutate(change, select=None)
        if "node" in created:
            self.select_ids([created["node"].id])
            self.statusBar().showMessage(f"{spec.label} creado: {created['node'].call()}", 4000)

    def toggle_modifier(self, mod: str) -> None:
        nodes = [n for n in (self.doc.find(i) for i in self.selected_ids()) if isinstance(n, Node)]
        if not nodes:
            return
        ids = [n.id for n in nodes]
        turn_on = not all(n.modifier == mod for n in nodes)

        def change():
            for nid in ids:
                self.doc.find(nid).modifier = mod if turn_on else ""
        self.mutate(change, select=ids)

    def delete_selected(self) -> None:
        ids = self.selected_ids()
        if ids:
            self.mutate(lambda: self.doc.delete(ids), select=[])

    def move_selected(self, delta: int) -> None:
        node = self.current_node()
        if node is not None:
            self.mutate(lambda: self.doc.move(node.id, delta), select=[node.id])

    def indent_selected(self) -> None:
        node = self.current_node()
        if node is not None:
            self.mutate(lambda: self.doc.indent(node.id), select=[node.id])

    def outdent_selected(self) -> None:
        node = self.current_node()
        if node is not None:
            self.mutate(lambda: self.doc.outdent(node.id), select=[node.id])

    def unwrap_selected(self) -> None:
        node = self.current_node()
        if node is not None and node.is_container:
            child_ids = [c.id for c in node.children]
            self.mutate(lambda: self.doc.unwrap(node.id), select=child_ids)

    def on_nodes_dropped(self, source_ids: list[int], target_id: Optional[int], position: str) -> None:
        self.mutate(lambda: self.doc.reparent(source_ids, target_id, position), select=source_ids)

    def duplicate(self) -> None:
        node = self.current_node()
        if node is None:
            return
        created = {}

        def change():
            created["n"] = self.doc.duplicate(node.id)
        self.mutate(change)
        if created.get("n") is not None:
            self.select_ids([created["n"].id])

    def convert_to_module(self) -> None:
        sel = self.selected_ids()
        if not sel:
            self.statusBar().showMessage(tr("Selecciona primero una o más piezas para convertirlas en módulo"), 4000)
            return

        candidates = self.doc.collect_module_parameters(sel)
        first_node = self.doc.find(sel[0])
        default_name = re.sub(r"[^a-zA-Z0-9_]", "_", first_node.name or first_node.kind).lower().strip("_") if first_node else "mi_modulo"
        if not default_name or default_name[0].isdigit():
            default_name = "mod_" + (default_name or "custom")

        from .module_dialog import ModuleDialog
        dlg = ModuleDialog(candidates, default_name=default_name, parent=self)
        if dlg.exec():
            mod_name, bindings = dlg.get_result()
            created = {}

            def change():
                mod_node, call_node = self.doc.make_module(sel, mod_name, bindings)
                created["call"] = call_node

            self.mutate(change)
            if "call" in created:
                self.select_ids([created["call"].id])
                self.statusBar().showMessage(f"{tr('Módulo')} '{mod_name}' {tr('creado con éxito')}", 4000)

    # ------------------------------------------------------------- propiedades
    def on_param_changed(self, node_id: int, key: str, value) -> None:
        def change():
            self.doc.set_param(node_id, key, value)
        self.mutate(change, key=(node_id, key), rebuild_tree=False)
        self._refresh_item(node_id)

    def on_renamed(self, node_id: int, name: str) -> None:
        node = self.doc.find(node_id)
        if node is None or node.name == name.strip():
            return

        def change():
            node.name = name.strip()
        self.mutate(change, rebuild_tree=False)
        self._refresh_item(node_id)
        self.on_selection()

    def on_fn_changed(self, value) -> None:
        def change():
            self.doc.fn = value
        self.mutate(change, key=("fn",), rebuild_tree=False)

    def _refresh_item(self, node_id: int) -> None:
        item = self._item_for(node_id)
        node = self.doc.find(node_id)
        if item is not None and node is not None:
            self._fill_item(item, node)
        span = self.gen.lines.get(node_id)
        self._syncing = True
        self.code.highlight_span(span, scroll=False)
        self._syncing = False

    # ------------------------------------------------------------- código
    def refresh_code(self) -> None:
        self.gen = generate(self.doc)
        self.code.set_code(self.gen.text)
        if hasattr(self.code, "set_document_solids"):
            self.code.set_document_solids(self.doc.get_solids())
        if self.gl:
            self._update_ghosts()

    def _update_ghosts(self) -> None:
        try:
            self.ghosts = geo.build_ghosts(self.doc)
            hashed = geo.with_modifier(self.doc, self.ghosts, "#")
            background = geo.with_modifier(self.doc, self.ghosts, "%")
        except Exception as exc:  # noqa: BLE001 - nunca debe tumbar la app
            self.ghosts, hashed, background = {}, None, None
            self.log(f"No se pudo calcular la vista aproximada: {exc}", "warn")
        try:
            colors = geo.node_colors(self.doc, resolve=_qt_color)
        except Exception:  # noqa: BLE001
            colors = {}
        self.viewer.set_ghosts(self.ghosts, colors, hashed, background)
        self._update_highlight()

    def _update_highlight(self) -> None:
        sel = self.selected_ids()
        tris = geo.collect(self.doc, self.ghosts, sel)
        self.viewer.set_highlight(tris if len(tris) else None)
        if hasattr(self.viewer, "set_gizmo"):
            gizmo_enabled = self.settings.value("gizmo_enabled", True, bool)
            if gizmo_enabled and len(sel) == 1 and len(tris) > 0:
                center = tris.reshape(-1, 3).mean(axis=0)
                self.viewer.set_gizmo(center)
            else:
                self.viewer.set_gizmo(None)

    def on_gizmo_started(self) -> None:
        sel = self.selected_ids()
        if len(sel) != 1:
            self._dragging_gizmo = False
            return
        node = self.doc.find(sel[0])
        if node is None or not isinstance(node, Node):
            self._dragging_gizmo = False
            return

        # Snapshot para deshacer en un solo bloque al terminar el arrastre
        self._gizmo_before = self.doc.snapshot()

        # Determinar el nodo translate a modificar (o envolver de inmediato si no tiene)
        if getattr(node, "kind", "") == "translate" and "v" in node.params:
            self._gizmo_target_id = node.id
        else:
            _, parent = self.doc.parent_list(node.id)
            if parent is not None and getattr(parent, "kind", "") == "translate" and "v" in parent.params:
                self._gizmo_target_id = parent.id
            else:
                tr_node = self.doc.wrap([node.id], "translate")
                tr_node.params["v"] = [0.0, 0.0, 0.0]
                self._gizmo_target_id = tr_node.id
                self.rebuild_tree([node.id])

        target = self.doc.find(self._gizmo_target_id)
        curr_v = target.params.get("v", [0.0, 0.0, 0.0]) if target else [0.0, 0.0, 0.0]
        v = list(curr_v) if isinstance(curr_v, (list, tuple)) else [0.0, 0.0, 0.0]
        while len(v) < 3:
            v.append(0.0)
        self._gizmo_initial_v = [float(v[0]), float(v[1]), float(v[2])]
        self._gizmo_active_node_id = node.id
        self._dragging_gizmo = True

    def on_gizmo_moved(self, total_dx: float, total_dy: float, total_dz: float) -> None:
        if not getattr(self, "_dragging_gizmo", False):
            self.on_gizmo_started()
            if not getattr(self, "_dragging_gizmo", False):
                return

        target = self.doc.find(self._gizmo_target_id)
        if target is None:
            return

        snap = float(self.settings.value("gizmo_snap", 1.0) or 1.0)

        def snap_val(delta: float, s: float) -> float:
            if s > 0.0:
                return round(round(delta / s) * s, 2)
            return round(delta, 2)

        sx = snap_val(total_dx, snap)
        sy = snap_val(total_dy, snap)
        sz = snap_val(total_dz, snap)

        new_v = [
            round(self._gizmo_initial_v[0] + sx, 2),
            round(self._gizmo_initial_v[1] + sy, 2),
            round(self._gizmo_initial_v[2] + sz, 2),
        ]

        # Si no hubo cambio debido al escalón de snap, no hacemos recálculos
        if target.params.get("v") == new_v:
            return

        # Actualizar parámetro directamente sin snapshot ni rebuild pesado por cada micro-movimiento
        target.params["v"] = new_v

        # Actualizar visualización en tiempo real ultra rápida (OpenGL ghosts + gizmo)
        if self.gl:
            self._update_ghosts()

        self.statusBar().showMessage(
            f"Moviendo ({target.name or target.label}): X={new_v[0]:.2f} mm  Y={new_v[1]:.2f} mm  Z={new_v[2]:.2f} mm  (paso: {snap} mm)",
            2000
        )

    def on_gizmo_finished(self) -> None:
        if not getattr(self, "_dragging_gizmo", False):
            self.render_view(False)
            return

        self._dragging_gizmo = False
        if hasattr(self, "_gizmo_before") and self._gizmo_before is not None:
            self.history.push(self._gizmo_before, key=(self._gizmo_target_id, "gizmo"))
            self._gizmo_before = None

        self.modified = True
        self.update_title()
        self.refresh_code()
        self._refresh_item(self._gizmo_target_id)
        active_node = self.doc.find(self._gizmo_active_node_id)
        if active_node is not None:
            self.props.show_node(active_node, self.doc)
        if hasattr(self, "vars_panel"):
            self.vars_panel.refresh()

        self.render_view(False)
        self.statusBar().showMessage(tr("Posición fijada"), 3000)

    def on_variable_added(self, name: str, value: str, comment: str) -> None:
        self.mutate(lambda: self.doc.set_variable(name, value, comment), rebuild_tree=True)
        if hasattr(self, "vars_panel"):
            self.vars_panel.refresh()

    def on_variable_changed(self, name: str, value: str, comment: str) -> None:
        self.mutate(lambda: self.doc.set_variable(name, value, comment), rebuild_tree=True, key=("var", name))

    def on_variable_deleted(self, name: str) -> None:
        self.mutate(lambda: self.doc.delete_variable(name), rebuild_tree=True)
        if hasattr(self, "vars_panel"):
            self.vars_panel.refresh()

    def on_code_line(self, line: int) -> None:
        if self._syncing:
            return
        nid = self.gen.node_at(line)
        if nid is not None and self.selected_ids() != [nid]:
            self.select_ids([nid])

    def edit_code_of(self, node_id: int) -> None:
        span = self.gen.lines.get(node_id)
        self.dock_code.show()
        self.code.start_editing(span[0] if span else None)

    def on_code_editing(self, editing: bool) -> None:
        for w in (self.ribbon_bar, self.model_panel):
            w.setEnabled(not editing)
        if editing:
            self.statusBar().showMessage("Editando el código: pulsa Aplicar (Ctrl+Enter) para "
                                         "actualizar el árbol, o Descartar (Esc).")
        else:
            self.statusBar().clearMessage()

    def apply_code(self, text: str) -> None:
        try:
            new_doc = parse(text)
        except ParseError as exc:
            self.log(f"No se pudo leer el código: {exc}", "error")
            self.statusBar().showMessage(str(exc), 6000)
            if exc.line:
                self.code._goto(exc.line - 1)
            return
        def change():
            self.doc = new_doc
        self.code.stop_editing()
        self.mutate(change, select=[])
        pieces = sum(1 for n, _, _ in self.doc.walk() if isinstance(n, Node))
        raws = sum(1 for n, _, _ in self.doc.walk() if isinstance(n, RawCode) and not n.is_comment)
        self.log(f"Código aplicado: {pieces} piezas editables"
                 + (f", {raws} bloques solo de código." if raws else "."), "info")

    # ------------------------------------------------------------- vista 3D
    def schedule_preview(self) -> None:
        if self.viewer.auto.isChecked():
            self.viewer.request_render()

    def render_view(self, full: bool = False) -> None:
        if self.gl:
            self._render_mesh()
            return
        if not any(True for _ in self.doc.walk()):
            self.viewer.clear("Crea una pieza con los botones de arriba para verla aquí.")
            self.viewer.status.setText("")
            return
        if not self.runner.exe:
            self.viewer.clear("No se encontró OpenSCAD.\nInstálalo desde openscad.org o indica dónde está.")
            self.viewer.show_setup_button(True)
            return
        self.viewer.show_setup_button(False)
        highlight = [] if full else [i for i in self.selected_ids() if isinstance(self.doc.find(i), Node)]
        code = generate(self.doc, highlight=highlight, header=False).text
        self.runner.extra_args = ["--enable=roof"] if any(
            getattr(n, "kind", "") == "roof" for n, _, _ in self.doc.walk()) else []
        base = os.path.dirname(self.path) if self.path else ""
        self.runner.render_image(code, base, self.viewer.render_size(), self.viewer.camera, full_render=full)

    def _render_mesh(self) -> None:
        """Visor OpenGL: pide a OpenSCAD la malla final del modelo."""
        if not any(True for _ in self.doc.walk()):
            self.viewer.clear("Crea una pieza con los botones de arriba para verla aquí.")
            self.viewer.status.setText("")
            return
        if not self.runner.exe:
            self.viewer.set_mesh(None)
            self.viewer.show_message("Vista aproximada (sin operaciones booleanas).\n"
                                     "Instala OpenSCAD o indica dónde está para ver el resultado real.")
            self.viewer.show_setup_button(True)
            return
        self.viewer.show_setup_button(False)
        code = generate(self.doc, header=False).text
        self.runner.extra_args = ["--enable=roof"] if any(
            getattr(n, "kind", "") == "roof" for n, _, _ in self.doc.walk()) else []
        base = os.path.dirname(self.path) if self.path else ""
        self.runner.export_mesh(code, base)

    def on_mesh(self, path: str, seconds: float) -> None:
        try:
            tris, face_colors = geo.load_mesh(path)
        except (OSError, ValueError, IndexError) as exc:
            self.log(f"No se pudo leer la malla: {exc}", "error")
            return
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        self.viewer.set_mesh(tris, face_colors)
        self.viewer.status.setText(f"{tr('Listo')} · {seconds:.1f} s · {len(tris):,} {tr('triángulos')}".replace(",", "."))

    def on_mesh_empty(self) -> None:
        self.viewer.set_mesh(None)
        self.viewer.status.setText(tr("Sin geometría"))

    def on_pick(self, node_id: int, add: bool) -> None:
        """Clic en la vista 3D."""
        if node_id < 0:
            if not add:
                self.select_ids([])
            return
        target = geo.pick_target(self.doc, node_id)
        ids = self.selected_ids()
        if add:
            ids = [i for i in ids if i != target] if target in ids else ids + [target]
        else:
            ids = [target]
        self.select_ids(ids)
        item = self._item_for(target)
        if item is not None:
            self.tree.scrollToItem(item)

    def _toggle_gl(self, on: bool) -> None:
        self.settings.setValue("viewer", "gl" if on else "image")
        QMessageBox.information(self, tr("Visor 3D"), tr("El cambio de visor se aplica al reiniciar la aplicación."))

    def on_image(self, path: str, seconds: float) -> None:
        self.viewer.set_image(path)
        self.viewer.status.setText(f"{tr('Listo')} · {seconds:.1f} s")

    def on_render_failed(self, message: str) -> None:
        self.viewer.status.setText(tr("Error"))
        self.log(message, "error")
        if not self.runner.exe:
            self.viewer.show_setup_button(True)

    # ------------------------------------------------------------- consola
    def log(self, text: str, level: str = "info") -> None:
        colors = {"info": "#3D4756", "warn": "#8A5A00", "error": "#B42318", "echo": "#174A96"}
        self.console.appendHtml(f'<span style="color:{colors.get(level, "#3D4756")}">{html.escape(text)}</span>')

    def log_openscad(self, line: str) -> None:
        upper = line.upper()
        if "ERROR" in upper:
            level = "error"
        elif "WARNING" in upper or "DEPRECATED" in upper:
            level = "warn"
        elif upper.startswith("ECHO"):
            level = "echo"
        else:
            level = "info"
        self.log(line, level)

    # ------------------------------------------------------------- archivos
    def maybe_save(self) -> bool:
        if not self.modified:
            return True
        r = QMessageBox.question(self, tr("Cambios sin guardar"), tr("¿Guardar los cambios antes de continuar?"),
                                 QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                 QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Save:
            return self.save_file()
        return r == QMessageBox.StandardButton.Discard

    def new_file(self) -> None:
        if self.maybe_save():
            self.set_document(Document())

    def open_example(self) -> None:
        is_stub = "qtstub" in getattr(sys.modules.get("PySide6"), "__file__", "") or bool(os.environ.get("SCADGUI_SRC"))
        target = EXAMPLE_PLACA if is_stub else EXAMPLE_RUEDA
        if self.maybe_save() and os.path.isfile(target):
            with open(target, encoding="utf-8") as fh:
                self.set_document(parse(fh.read()))

    def open_file(self) -> None:
        if not self.maybe_save():
            return
        start = os.path.dirname(self.path) if self.path else self.settings.value("last_dir", "", str)
        path, _ = QFileDialog.getOpenFileName(self, tr("Abrir"), start, tr("OpenSCAD (*.scad);;Todos (*)"))
        if path:
            self.load(path)

    def load(self, path: str) -> None:
        try:
            with open(path, encoding="utf-8") as fh:
                doc = parse(fh.read())
        except (OSError, UnicodeDecodeError) as exc:
            QMessageBox.warning(self, tr("No se pudo abrir"), str(exc))
            return
        except ParseError as exc:
            QMessageBox.warning(self, tr("No se pudo leer el archivo"), str(exc))
            return
        self.settings.setValue("last_dir", os.path.dirname(path))
        self.set_document(doc, path)
        raws = sum(1 for n, _, _ in doc.walk() if isinstance(n, RawCode) and not n.is_comment)
        self.log(f"Abierto {path}" + (f" ({raws} bloques se editan solo como código)" if raws else ""))

    def save_file(self) -> bool:
        if not self.path:
            return self.save_file_as()
        try:
            with open(self.path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(generate(self.doc).text)
        except OSError as exc:
            QMessageBox.warning(self, tr("No se pudo guardar"), str(exc))
            return False
        self.modified = False
        self.update_title()
        self.statusBar().showMessage(f"{tr('Guardado en')} {self.path}", 4000)
        return True

    def save_file_as(self) -> bool:
        start = self.path or os.path.join(self.settings.value("last_dir", "", str), "modelo.scad")
        path, _ = QFileDialog.getSaveFileName(self, tr("Guardar como"), start, "OpenSCAD (*.scad)")
        if not path:
            return False
        if not path.lower().endswith(".scad"):
            path += ".scad"
        self.path = path
        self.props.base_dir = os.path.dirname(path)
        self.settings.setValue("last_dir", os.path.dirname(path))
        return self.save_file()

    def export_file(self) -> None:
        if not self.runner.exe:
            self.configure_openscad()
            if not self.runner.exe:
                return
        base = os.path.splitext(self.path)[0] if self.path else os.path.join(
            self.settings.value("last_dir", "", str), "modelo")
        path, chosen = QFileDialog.getSaveFileName(self, tr("Exportar"), base + ".stl", EXPORT_FILTERS)
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += "." + chosen.split("*.")[1].rstrip(")")
        code = generate(self.doc, header=False).text
        self.runner.extra_args = ["--enable=roof"] if any(
            getattr(n, "kind", "") == "roof" for n, _, _ in self.doc.walk()) else []
        self.runner.export(code, os.path.dirname(self.path) if self.path else "", path)

    def on_exported(self, path: str, ok: bool) -> None:
        if ok:
            self.log(f"Exportado: {path}", "info")
            self.statusBar().showMessage(f"{tr('Exportado')}: {path}", 6000)
        else:
            self.log(f"Falló la exportación a {path}. Mira los mensajes de OpenSCAD arriba "
                     "(¿formato 2D con piezas 3D o al revés?).", "error")
        self.viewer.status.setText(tr("Exportado") if ok else tr("Error al exportar"))
        self.schedule_preview()

    def open_preferences(self) -> None:
        from ..i18n import set_language, tr
        from .preferences_dialog import PreferencesDialog

        old_lang = str(self.settings.value("language", "es", str) or "es")
        dlg = PreferencesDialog(self.settings, self.runner.exe or "", self.runner.backend, self)
        if dlg.exec():
            dlg._on_save()
            new_lang = str(self.settings.value("language", "es", str) or "es")
            set_language(new_lang)

            exe = find_openscad(self.settings.value("openscad_path", "", str))
            self.runner.exe = exe
            version = self.runner.version()
            self.runner.check_backend_support(version)

            new_backend = self.settings.value("backend", "", str)
            self.runner.backend = new_backend
            idx = max(0, self.engine.findData(new_backend))
            self.engine.setCurrentIndex(idx)

            if self.gl:
                self.viewer.gizmo_enabled = self.settings.value("gizmo_enabled", True, bool)
                self.viewer.snap_step = float(self.settings.value("gizmo_snap", 1.0) or 1.0)
                self._update_highlight()

            self.render_view(False)
            self.statusBar().showMessage(tr("Preferencias guardadas"), 4000)
            self.log(f"{tr('Preferencias guardadas')}. OpenSCAD: {exe or 'no configurado'}", "info")

            if new_lang != old_lang:
                self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Actualiza dinámicamente los textos de la ventana principal al cambiar de idioma."""
        from ..i18n import tr
        for a, text, tip in getattr(self, "_action_defs", []):
            a.setText(tr(text))
            if tip:
                t = tr(tip)
                a.setToolTip(t)
                a.setStatusTip(t)

        self.menuBar().clear()
        self._build_menus()

        if hasattr(self, "ribbon") and hasattr(self.ribbon, "retranslate_ui"):
            self.ribbon.retranslate_ui()
        if hasattr(self, "dock_model"):
            self.dock_model.setWindowTitle(tr("Modelo"))
        if hasattr(self, "dock_code"):
            self.dock_code.setWindowTitle(tr("Código"))
        if hasattr(self, "code") and hasattr(self.code, "retranslate_ui"):
            self.code.retranslate_ui()

        if hasattr(self, "dock_console"):
            self.dock_console.setWindowTitle(tr("Consola"))
        if hasattr(self, "dock_vars"):
            self.dock_vars.setWindowTitle(tr("Variables"))
        if hasattr(self, "tree"):
            self.tree.setHeaderLabels([tr("Nombre"), tr("Comando")])
        if hasattr(self, "engine"):
            self.engine.setItemText(0, tr("Automático"))
            self.engine.setItemText(1, tr("Manifold (rápido)"))
            self.engine.setItemText(2, tr("CGAL (clásico)"))
        if hasattr(self, "units"):
            version = self.runner.version() if hasattr(self, "runner") else ""
            self.units.setText(f"OpenSCAD {version}  ·  {tr('Unidades: mm')}" if version else tr("Unidades: mm"))

    def configure_openscad(self) -> None:
        self.open_preferences()

    def _engine_changed(self) -> None:
        self.runner.backend = self.engine.currentData()
        self.settings.setValue("backend", self.runner.backend)
        self.render_view(False)

    # ------------------------------------------------------------- deshacer
    def _restore(self, doc: Optional[Document]) -> None:
        if doc is None:
            return
        keep = self.selected_ids()
        self.doc = doc
        self.modified = True
        self.rebuild_tree([i for i in keep if doc.find(i) is not None])
        self.refresh_code()
        self.update_title()
        if hasattr(self, "vars_panel"):
            self.vars_panel.refresh()
        self.schedule_preview()

    def undo(self) -> None:
        self._restore(self.history.undo(self.doc))

    def redo(self) -> None:
        self._restore(self.history.redo(self.doc))

    # ------------------------------------------------------------- otros
    def about(self) -> None:
        QMessageBox.about(self, tr("OpenSCAD GUI Mejorada"),
                          f"<b>{tr('OpenSCAD GUI Mejorada')} {__version__}</b><br><br>"
                          f"{tr('Crea sólidos con botones; cada acción se traduce a código OpenSCAD que puedes ver, editar y guardar.')}<br><br>"
                          f"OpenSCAD: {html.escape(self.runner.exe or tr('no encontrado'))}")

    def closeEvent(self, event) -> None:
        if self.maybe_save():
            self.settings.setValue("geometry", self.saveGeometry())
            self.runner.cancel()
            event.accept()
        else:
            event.ignore()

