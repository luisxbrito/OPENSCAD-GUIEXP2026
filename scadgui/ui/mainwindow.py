"""Ventana principal: cinta de comandos, árbol, propiedades, vista 3D, código y consola."""

from __future__ import annotations

import html
import os
import re
import shlex
import shutil
import sys
import tempfile
import time
from typing import Optional

import numpy as np
from PySide6.QtCore import QEvent, QItemSelectionModel, QProcess, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QGuiApplication, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDockWidget, QFileDialog, QFrame,
                               QHBoxLayout,
                               QHeaderView, QLabel, QMainWindow, QMenu, QMessageBox, QPlainTextEdit,
                               QScrollArea, QSizePolicy, QSplitter, QTabWidget, QToolBar, QToolButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from .. import __version__
from .. import colorschemes
from .. import geometry as geo
from .. import meshcache
from ..catalog import CATEGORIES, SPECS, specs_in
from ..edges import finish_edges
from ..i18n import get_language, set_language, tr
from ..model import Document, Node, RawCode, generate, make_node
from ..parser import ParseError, parse
from ..runner import OpenScadRunner, find_openscad
from .codeview import CodeView, mono_font
from .icons import icon
from .properties import PropertyPanel, choose_import_file
from .style import ACCENT, c, dark_palette, indicator_stylesheet, set_theme, stylesheet, tooltip_stylesheet

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

N_ = str  # marca un texto que se traduce más tarde con tr() (lo recoge test_i18n)


class Ribbon(QTabWidget):
    commandTriggered = Signal(str)

    # Botones de asistentes que no son un módulo de OpenSCAD: (pestaña, comando, icono, texto, ayuda)
    EXTRA_BUTTONS = (
        ("mech", "hardware", "hardware", "Tornillería ·\nEstándar",
         "Tornillería ISO/DIN, tuercas, insertos térmicos, rodamientos y perfiles."),
        ("mech", "flange_wizard", "pipe_flange", "Bridas ·\nNormalizadas",
         "Bridas ASME B16.5 y EN 1092-1: de cuello, deslizantes, ciegas y planas, con sus medidas."),
        ("mech", "transmission_wizard", "transmission", "Calculadora ·\nde transmisión",
         "Busca los engranajes, o las poleas y la correa, para una relación o unas velocidades, y los genera "
         "ya colocados."),
        ("mech", "camshaft_wizard", "cam_lobe", "Árbol ·\nde levas",
         "Eje y lóbulos repartidos por cilindros, con sus desfases; luego se cambia cada lóbulo por separado."),
        ("shape2d", "sketch2d", "sketch", "Boceto 2D ·\nAsistente",
         "Perfiles paramétricos: rectángulos redondeados, ranuras, polígonos, estrellas, etc."),
        ("shape2d", "drawing2d", "projection", "Plano 2D ·\nTécnico",
         "Lámina con vistas ortogonales, isométrica, marco y cajetín."),
        ("bool", "bool_wizard", "difference", "Asistente ·\nBooleano",
         "Configura qué sólido es la base y cuáles se restan, unen o intersectan."),
    )

    # Grupos de cada pestaña, con su título debajo (como en Fusion). Un comando de la pestaña que
    # no esté en ningún grupo va al último, para que nunca se quede sin botón.
    GROUPS = {
        "solid": ((N_("Primitivas"), ("cube", "sphere", "cylinder", "polyhedron")),),
        "mech": ((N_("Engranajes"), ("spur_gear", "helical_gear", "herringbone_gear", "bevel_gear",
                                       "worm", "worm_gear", "rack")),
                 (N_("Transmisión"), ("pulley", "v_pulley", "spline")),
                 (N_("Levas"), ("cam", "camshaft_main_shaft", "cam_lobe", "camshaft_bearing", "camshaft_end")),
                 (N_("Uniones"), ("pipe_flange",)),
                 (N_("Asistentes"), ("transmission_wizard", "hardware", "flange_wizard", "camshaft_wizard"))),
        "shape2d": ((N_("Primitivas 2D"), ("square", "circle", "polygon", "text")), (N_("Modificar"), ("offset",)),
                    (N_("Asistentes"), ("sketch2d", "drawing2d"))),
        "transform": ((N_("Posición"), ("translate", "rotate", "mirror")), (N_("Tamaño"), ("scale", "resize", "multmatrix")),
                      (N_("Apariencia"), ("color",))),
        "bool": ((N_("Combinar"), ("union", "difference", "intersection")), (N_("Organizar"), ("group",)),
                 (N_("Asistentes"), ("bool_wizard",))),
        "extrude": ((N_("Extruir"), ("linear_extrude", "rotate_extrude")), (N_("3D → 2D"), ("projection",))),
        "array": ((N_("Matrices"), ("linear_array", "polar_array", "grid_array")),),
        "adv": ((N_("Envolventes"), ("hull", "minkowski")), (N_("Otros"), ("fill", "render", "roof"))),
        "imp": ((N_("Archivos"), ("import", "surface")),),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ribbon")
        self.setDocumentMode(True)
        self.buttons: dict[str, QToolButton] = {}
        self._hints: list[QLabel] = []
        self._group_titles: list[tuple[QLabel, str]] = []
        self._pages: list[QWidget] = []
        self.compact = False
        wizards = {command: icon_name for tab, command, icon_name, _t, _tip in self.EXTRA_BUTTONS}
        for key, _title, _hint in CATEGORIES:
            page = QWidget()
            page.setObjectName("ribbonPage")
            row = QHBoxLayout(page)
            row.setContentsMargins(8, 6, 10, 4)
            row.setSpacing(0)
            commands = [s.name for s in specs_in(key)] + [cmd for tab, cmd, *_ in self.EXTRA_BUTTONS if tab == key]
            groups = [(title, [cmd for cmd in cmds if cmd in commands]) for title, cmds in self.GROUPS.get(key, ())]
            grouped = {cmd for _t, cmds in groups for cmd in cmds}
            rest = [cmd for cmd in commands if cmd not in grouped]
            if rest:
                if groups:
                    groups[-1][1].extend(rest)
                else:
                    groups = [("", rest)]
            for i, (title, cmds) in enumerate(g for g in groups if g[1]):
                if i:
                    sep = QFrame()
                    sep.setObjectName("ribbonSep")
                    sep.setFixedWidth(1)
                    row.addWidget(sep)
                row.addWidget(self._group(title, cmds, wizards))
            row.addStretch(1)
            tip = QLabel()
            tip.setWordWrap(True)
            tip.setObjectName("ribbonHint")
            tip.setMaximumWidth(340)
            row.addWidget(tip)
            self._hints.append(tip)
            self._pages.append(page)

            scroll = QScrollArea()
            scroll.setObjectName("ribbonScroll")
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            self.addTab(scroll, "")
        self.currentChanged.connect(self._fit_current_page)
        self._fit_current_page()
        self.retranslate_ui()

    def _fit_current_page(self, _index: int = 0) -> None:
        self.updateGeometry()

    def _height_for_current(self, size: QSize) -> QSize:
        """QTabWidget toma la altura de la pestaña más alta, también de las ocultas. En modo normal es lo
        que conviene (la cinta no cambia de alto al cambiar de pestaña), pero en compacto las ocultas
        guardan el tamaño de antes: entonces cuenta solo la visible (todas miden igual)."""
        current = self.currentWidget()
        if self.compact and current is not None:
            inner = current.widget() if hasattr(current, "widget") and current.widget() is not None else current
            size.setHeight(self.tabBar().sizeHint().height() + inner.sizeHint().height() + 2)
        return size

    def sizeHint(self) -> QSize:
        return self._height_for_current(super().sizeHint())

    def minimumSizeHint(self) -> QSize:
        h = self._height_for_current(super().minimumSizeHint()).height()
        return QSize(350, h)

    def _group(self, title: str, commands, wizards: dict) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(2)
        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        for cmd in commands:
            if cmd in wizards:          # asistente: texto traducido e icono del color de acento
                b = self._button(cmd, wizards[cmd], ACCENT)
            else:                       # comando de OpenSCAD: su nombre, en letra de código
                b = self._button(cmd, cmd)
                b.setProperty("command", True)
                if SPECS[cmd].level == "experimental":
                    b.setProperty("experimental", True)
            buttons.addWidget(b)
        lay.addLayout(buttons, 1)
        label = QLabel()
        label.setObjectName("ribbonGroupTitle")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(label)
        self._group_titles.append((label, title))
        return box

    def _button(self, command: str, icon_name: str, color: str = "#1B2230") -> QToolButton:
        b = QToolButton()
        b.setObjectName("ribbonButton")
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        b.setIcon(icon(icon_name, color))
        b.setIconSize(QSize(26, 26))
        b.setMinimumWidth(76)
        b.setFixedHeight(66)            # misma altura con una o dos líneas: los rótulos de grupo alineados
        b.clicked.connect(lambda _=False, c=command: self.commandTriggered.emit(c))
        self.buttons[command] = b
        return b

    def set_compact(self, on: bool) -> None:
        """Cinta mínima: solo iconos pequeños, sin rótulos de grupo ni ayuda, pestañas más bajas.
        El nombre de cada botón sigue en su tooltip."""
        on = bool(on)
        self.compact = on
        for b in self.buttons.values():
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly if on
                                 else Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setIconSize(QSize(20, 20) if on else QSize(26, 26))
            b.setMinimumWidth(32 if on else 76)
            b.setFixedHeight(32 if on else 66)
        for label, _title in self._group_titles:
            label.setVisible(not on)
        for tip in self._hints:
            tip.setVisible(not on)
        for page in self._pages:
            page.layout().setContentsMargins(*((6, 2, 6, 2) if on else (8, 6, 10, 4)))
            # las páginas que aún no se han mostrado guardan el tamaño de antes: se recalcula
        self._fit_current_page()
        self.setProperty("compact", on)
        self.style().unpolish(self)
        self.style().polish(self)
        self.tabBar().style().unpolish(self.tabBar())
        self.tabBar().style().polish(self.tabBar())
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        for idx, (_key, title, hint) in enumerate(CATEGORIES):
            self.setTabText(idx, tr(title))
            self._hints[idx].setText(tr(hint))
        for label, title in self._group_titles:
            label.setText(tr(title).upper() if title else "")
        for name, spec in SPECS.items():
            if name not in self.buttons:  # cube_edges y cylinder_edges no tienen botón
                continue
            self.buttons[name].setText(self.button_text(spec))
            self.buttons[name].setToolTip(self._tooltip(spec))
        for _tab, command, _icon, text, tip in self.EXTRA_BUTTONS:
            label = tr(text).replace(" ·", "")                          # sin la marca antigua «·»
            self.buttons[command].setText(label)
            # en la cinta compacta el botón no lleva texto: el nombre va en el tooltip
            name = f"<b>{html.escape(label.replace(chr(10), ' '))}</b><br>" if self.compact else ""
            self.buttons[command].setToolTip(name + html.escape(tr(tip)))

    @staticmethod
    def button_text(spec) -> str:
        """El botón lleva el nombre de OpenSCAD tal cual (cube, translate...), el mismo que se
        ve en el código; la descripción traducida queda en el tooltip."""
        # Los que tienen editor propio ya lo dicen en su ayuda; aquí solo se marca lo experimental.
        suffix = " (exp.)" if spec.level == "experimental" else ""
        return f"{spec.name}{suffix}"

    @staticmethod
    def _tooltip(spec) -> str:
        params = ", ".join(p.name for p in spec.params) or tr("sin parámetros")
        extra = {"editor": tr("Con editor propio (tabla, matriz o archivo)."),
                 "experimental": tr("Experimental: requiere --enable=roof.")}.get(spec.level, "")
        what = tr("Envuelve la selección.") if spec.container else tr("Crea la pieza.")
        extra_html = f"<br><i>{html.escape(extra)}</i>" if extra else ""
        code = make_node(spec.name).call() if spec.keyword else f"{spec.name}({params})"
        hint = f"<br>{html.escape(tr(spec.hint))}" if spec.keyword and spec.hint else ""
        return f"<b>{html.escape(tr(spec.label))}</b> — <code>{html.escape(code)}</code><br>{what}{hint}{extra_html}"


# --------------------------------------------------------------------------- árbol con arrastrar y soltar

# Colores del árbol: en el panel (fondo blanco) y sobre el visor 3D (transparente, fondo oscuro).
TREE_COLORS = {
    False: {"icon": "#3D4756", "raw": "#8A5A00", "muted": "#5A6474", "disabled": "#9AA3AF"},
    True: {"icon": "#DDE3EA", "raw": "#F2C46B", "muted": "#AEB7C3", "disabled": "#7D8794"},
}


def tree_colors(on_viewer: bool, light_viewer: bool = False) -> dict:
    """Colores del árbol: sobre el visor, los claros (o los oscuros si el fondo del visor es claro)
    tal cual; en el panel, los del tema."""
    if on_viewer:
        return TREE_COLORS[not light_viewer]
    return {k: c(v, text=k != "icon") for k, v in TREE_COLORS[False].items()}


class ModelTree(QTreeWidget):
    dropped = Signal(list, object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDropIndicatorShown(True)

    def dropEvent(self, event) -> None:
        pos = event.position().toPoint()  # PySide6 >= 6.5
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
        set_language(str(self.settings.value("language", "es", str) or "es"))
        self.theme = str(self.settings.value("theme", "dark", str) or "dark")
        set_theme(self.theme)
        app = QApplication.instance()
        if self.theme == "dark" and app is not None:
            app.setStyle("Fusion")          # el estilo nativo de Windows no sigue la paleta oscura
            app.setPalette(dark_palette())
        if app is not None:                  # ventanas aparte (tooltips, diálogos): estilo de aplicación
            folder = os.path.join(tempfile.gettempdir(), "scadgui_indicadores")
            app.setStyleSheet(tooltip_stylesheet() + indicator_stylesheet(folder))
        self.doc = Document()
        self.path = ""
        self.modified = False
        self.history = History()
        self.gen = generate(self.doc)
        self._syncing = False
        # Estado del arrastre con el gizmo de ejes
        self._dragging_gizmo = False
        self._gizmo_before: Optional[Document] = None
        self._gizmo_target_id: Optional[int] = None
        self._gizmo_active_node_id: Optional[int] = None
        self._gizmo_initial_v = [0.0, 0.0, 0.0]

        self.runner = OpenScadRunner(self)
        self.mesh_cache = meshcache.MeshCache()   # mallas ya calculadas: no se repite OpenSCAD
        self._mesh_key: Optional[str] = None      # huella de la malla pedida a OpenSCAD
        self.runner.exe = find_openscad(self.settings.value("openscad_path", "", str))
        self.runner.backend = self.settings.value("backend", "", str)

        self.setStyleSheet(stylesheet())
        self.setWindowIcon(icon("cube", "#2563EB"))
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            target_w = min(1360, max(800, int(avail.width() * 0.85)))
            target_h = min(820, max(600, int(avail.height() * 0.85)))
            self.resize(target_w, target_h)
        else:
            self.resize(1200, 750)
        self._action_defs: list[tuple[QAction, str, Optional[str]]] = []
        self._compact_saved = None    # (disposición, árbol sobre el visor) de antes del modo compacto
        self._was_maximized = False
        self._is_fullscreen = False
        self._build_actions()
        self._build_menus()
        self._build_toolbars()
        self._build_central()
        self._build_docks()
        self._connect()
        self.statusBar().showMessage(tr("Listo"))
        self.units = QLabel(tr("Unidades: mm"))
        self.units.setFont(mono_font(9))
        self.statusBar().addPermanentWidget(self.units)

        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
            if self.isFullScreen():
                self.showNormal()
            self._clamp_to_screen()
        QTimer.singleShot(0, lambda: self._startup(path))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.WindowStateChange:
            if not (self.isMaximized() or self.isFullScreen() or getattr(self, "_is_fullscreen", False)):
                QTimer.singleShot(0, self._clamp_to_screen)
        super().changeEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and getattr(self, "_is_fullscreen", False):
            self.set_fullscreen(False)
            event.accept()
            return
        super().keyPressEvent(event)

    def _clamp_to_screen(self) -> None:
        """Asegura que si la ventana no está maximizada, no exceda la pantalla disponible."""
        if self.isMaximized() or self.isFullScreen() or getattr(self, "_is_fullscreen", False):
            return
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        geo = self.geometry()
        w = min(geo.width(), avail.width())
        h = min(geo.height(), avail.height())
        x = max(avail.left(), min(geo.x(), avail.right() - w))
        y = max(avail.top(), min(geo.y(), avail.bottom() - h))
        self.setGeometry(x, y, w, h)

    # ------------------------------------------------------------- construcción
    def _act(self, text, slot, shortcut=None, icon_name=None, tip=None) -> QAction:
        a = QAction(icon(icon_name) if icon_name else QIcon(), tr(text), self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip:
            t = tr(tip)
            a.setToolTip(t)
            a.setStatusTip(t)
        a.triggered.connect(slot)
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
        # lambda: triggered(bool) pasaría el estado "checked" como ruta
        self.a_example = self._act("Ejemplo: rueda con eje giratorio", lambda: self.open_example(EXAMPLE_RUEDA))
        self.a_example_plate = self._act("Ejemplo: placa con agujeros", lambda: self.open_example(EXAMPLE_PLACA))
        self.a_prefs = self._act("Preferencias…", self.open_preferences, "Ctrl+,", None,
                                 "Configuración de OpenSCAD y preferencias de la aplicación")
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
        self.a_flange = self._act("Insertar brida normalizada…", self.open_flange_dialog, None, "pipe_flange",
                                  "Bridas ASME B16.5 y EN 1092-1 con las medidas de sus tablas")
        self.a_camshaft = self._act("Insertar árbol de levas…", self.open_camshaft_dialog, None, "cam_lobe",
                                    "Eje y lóbulos repartidos por cilindros, con sus desfases")
        self.a_transmission = self._act("Calculadora de transmisión…", self.open_transmission_dialog, None,
                                        "transmission", "Engranajes, o poleas y correa, para una relación, ya "
                                        "colocados")
        self.a_preview = self._act("Vista previa", lambda: self.render_view(False), "F5", "preview",
                                   "Vista previa rápida (resalta la selección)")
        self.a_render = self._act("Render", lambda: self.render_view(True), "F6", "render_action",
                                  "Render final: geometría exacta, sin resaltados")
        self.a_about = self._act("Acerca de", self.about)
        self.a_compact = self._act("Modo compacto", lambda on: self.set_compact(on), "Ctrl+Shift+F", None,
                                   "Cinta solo con iconos y sin paneles Modelo, Variables ni Consola: "
                                   "el árbol y las propiedades flotan sobre el visor")
        self.a_compact.setCheckable(True)
        self.a_compact.setIcon(icon("compact"))
        self.a_fullscreen = self._act("Pantalla completa", lambda on: self.set_fullscreen(on), "F11", "fullscreen")
        self.a_fullscreen.setCheckable(True)
        self.a_del.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        mb.setNativeMenuBar(False)
        m_file = mb.addMenu(tr("&Archivo"))
        for a in (self.a_new, self.a_open, self.a_example, self.a_example_plate, None, self.a_save, self.a_save_as,
                  self.a_export, self.a_drawing, None, self.a_prefs, None, self.a_quit):
            m_file.addSeparator() if a is None else m_file.addAction(a)
        m_edit = mb.addMenu(tr("&Editar"))
        for a in (self.a_undo, self.a_redo, None, self.a_dup, self.a_make_module, self.a_del, None, self.a_prefs):
            m_edit.addSeparator() if a is None else m_edit.addAction(a)
        self.view_menu = mb.addMenu(tr("&Ver"))
        m_design = mb.addMenu(tr("&Diseño"))
        m_design.addAction(self.a_make_module)
        m_design.addAction(self.a_bool_wizard)
        m_design.addAction(self.a_operation_helper)
        m_design.addAction(self.a_sketch)
        m_design.addAction(self.a_hardware)
        m_design.addAction(self.a_flange)
        m_design.addAction(self.a_transmission)
        m_design.addAction(self.a_camshaft)
        m_design.addAction(self.a_drawing)
        m_design.addSeparator()
        m_design.addAction(self.a_preview)
        m_design.addAction(self.a_render)
        ayuda_m = mb.addMenu(tr("A&yuda"))
        ayuda_m.addAction(self.a_operation_helper)
        ayuda_m.addAction(self.a_about)

        for m in (m_file, m_edit, self.view_menu, m_design, ayuda_m):
            m.setWindowFlags(m.windowFlags() | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Popup)
            m.aboutToShow.connect(m.raise_)

    def _build_toolbars(self) -> None:
        tb = QToolBar(tr("Principal"))
        self.main_toolbar = tb
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
        corner = QToolBar()
        corner.setObjectName("ribbonCorner")
        corner.setIconSize(QSize(16, 16))
        corner.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        for a in (self.a_new, self.a_open, self.a_save, None, self.a_undo, self.a_redo, None,
                  self.a_preview, self.a_render, self.a_export, None, self.a_fullscreen, self.a_compact):
            corner.addSeparator() if a is None else corner.addAction(a)
        corner.hide()                                # en el modo compacto sustituye a la barra principal
        self.ribbon.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        self.ribbon_corner = corner
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, rb)
        self.ribbon_bar = rb

    def _build_central(self) -> None:
        """Visor OpenGL si están pyqtgraph y PyOpenGL; si no, el visor de imágenes."""
        self.gl = False
        self._gl_error = ""
        self.ghosts: dict = {}
        self._drawing_job = None   # (stl temporal, archivo de la lámina, datos) mientras OpenSCAD calcula
        if self.settings.value("viewer", "gl", str) != "image":
            try:
                from .viewer3d import Viewer3D
                self.viewer = Viewer3D()
                self.gl = True
                self.viewer.gizmoStarted.connect(self.on_gizmo_started)
                self.viewer.gizmoMoved.connect(self.on_gizmo_moved)
                self.viewer.gizmoFinished.connect(self.on_gizmo_finished)
                self.viewer.edgeFinish.connect(self.finish_edges)
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
        self.a_dark = QAction(tr("Tema oscuro (requiere reiniciar)"), self)
        self.a_dark.setCheckable(True)
        self.a_dark.setChecked(self.theme == "dark")
        self.a_dark.toggled.connect(self._toggle_theme)
        self.a_tree_overlay = QAction(tr("Árbol sobre el visor 3D"), self)
        self.a_tree_overlay.setCheckable(True)
        self.a_tree_overlay.setEnabled(self.gl)
        self.a_tree_overlay.toggled.connect(self.set_tree_overlay)
        self.a_grid = QAction(tr("Rejilla"), self)
        self.a_grid.setCheckable(True)
        self.a_grid.setChecked(True)
        self.a_grid.setEnabled(self.gl)
        self.a_grid.toggled.connect(lambda on: self.viewer.set_grid(on) if self.gl else None)
        self.a_gizmo = QAction(tr("Flechas de arrastre (gizmo)"), self)
        self.a_gizmo.setCheckable(True)
        self.a_gizmo.setChecked(self.settings.value("gizmo_enabled", True, bool))
        self.a_gizmo.setEnabled(self.gl)
        self.a_gizmo.toggled.connect(self._toggle_gizmo)
        self.display_group = QActionGroup(self)        # Ver › Visualización (exclusivas)
        self.display_actions: dict[str, QAction] = {}
        for key, label in geo.DISPLAY_MODES:
            a = QAction(tr(label), self)
            a.setCheckable(True)
            a.setChecked(key == "shaded")
            a.setEnabled(self.gl)
            a.triggered.connect(lambda _=False, k=key: self.viewer.set_display_mode(k) if self.gl else None)
            self.display_group.addAction(a)
            self.display_actions[key] = a
        if self.gl:
            self.viewer.displayModeChanged.connect(self._display_mode_changed)
            self.viewer.gridToggled.connect(self._grid_changed)
            self.viewer.treeOverlayToggled.connect(self.a_tree_overlay.setChecked)
            self.viewer.ruler_btn.toggled.connect(lambda on: self.settings.setValue("ruler", on))

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
        self.tree_tools_box = tools
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
            b.setIcon(icon(name, tree_colors(False)["icon"], fixed=True))
            b.setProperty("icon_name", name)
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
        self.model_split = split
        self.model_layout = lay
        self.tree_box = None  # contenedor del árbol cuando está sobre el visor
        self.tree_on_viewer = False  # colores claros: el árbol está sobre el fondo oscuro del visor
        self._empty_message = False  # el visor muestra «Crea una pieza…» (documento vacío)
        self._docks_hidden_by_tree: list = []  # paneles que se ocultaron por no haber selección
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
        self.dock_model.raise_()
        self.vars_panel.variableAdded.connect(self.on_variable_added)
        self.vars_panel.variableChanged.connect(self.on_variable_changed)
        self.vars_panel.variableDeleted.connect(self.on_variable_deleted)

        self._fill_view_menu()

    def _fill_view_menu(self) -> None:
        """Menú Ver. Se rellena aquí (y no en _build_menus) porque sus acciones se crean con el visor
        y los paneles, y al cambiar de idioma el menú se rehace."""
        m = self.view_menu
        m.clear()
        for action, text in ((self.a_gl, "Visor OpenGL (requiere reiniciar)"),
                             (self.a_dark, "Tema oscuro (requiere reiniciar)"),
                             (self.a_tree_overlay, "Árbol sobre el visor 3D")):
            action.setText(tr(text))
            m.addAction(action)
        m.addAction(self.a_compact)
        m.addAction(self.a_fullscreen)
        m.addSeparator()
        self.a_grid.setText(tr("Rejilla") + "\tG")    # G con el ratón sobre el visor (no es atajo global)
        m.addAction(self.a_grid)
        self.a_gizmo.setText(tr("Flechas de arrastre (gizmo)"))
        m.addAction(self.a_gizmo)
        sub = m.addMenu(tr("Visualización"))
        sub.setWindowFlags(sub.windowFlags() | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Popup)
        sub.aboutToShow.connect(sub.raise_)
        for key, label in geo.DISPLAY_MODES:
            a = self.display_actions[key]
            a.setText(tr(label))
            sub.addAction(a)
        sub.addSeparator()
        hint = sub.addAction(tr("Z con el ratón sobre el visor: siguiente modo"))
        hint.setEnabled(False)
        m.addSeparator()
        for d in (self.dock_model, self.dock_vars, self.dock_code, self.dock_console):
            m.addAction(d.toggleViewAction())

    def _toggle_gizmo(self, on: bool) -> None:
        """Ver › Flechas de arrastre: la misma opción que en Preferencias."""
        self.settings.setValue("gizmo_enabled", bool(on))
        self._update_highlight()

    def _display_mode_changed(self, mode: str) -> None:
        if mode in self.display_actions:
            self.display_actions[mode].setChecked(True)
        self.settings.setValue("display_mode", mode)

    def _grid_changed(self, on: bool) -> None:
        self.a_grid.blockSignals(True)
        self.a_grid.setChecked(on)
        self.a_grid.blockSignals(False)
        self.settings.setValue("grid", on)

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
        self.props.fixRadii.connect(self.fix_radii)
        self.props.addMeshingGear.connect(self.add_meshing_gear)
        self.props.layoutCamshaftForPrint.connect(self.layout_camshaft_for_print)
        self.props.exportCamshaftParts.connect(self.export_camshaft_parts)
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
        self._esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._esc_shortcut.activated.connect(lambda: self.set_fullscreen(False) if getattr(self, "_is_fullscreen", False) else None)

    def _startup(self, path: str) -> None:
        if self.settings.value("tree_overlay", False, bool):
            self.set_tree_overlay(True)
        self.apply_settings()
        if self.gl:
            self.viewer.set_ruler(self.settings.value("ruler", True, bool))
            self.viewer.set_grid(self.settings.value("grid", True, bool))
            self.viewer.set_display_mode(self.settings.value("display_mode", "shaded", str))
        if self.settings.value("compact", False, bool):
            self.set_compact(True)
        version = self.runner.version()
        if self.runner.exe:
            self.runner.check_backend_support(version)
            self.log(tr("OpenSCAD encontrado: {exe} ({version})").format(
                exe=self.runner.exe, version=version or tr("versión desconocida")), "info")
            self.units.setText(f"OpenSCAD {version}  ·  {tr('Unidades: mm')}" if version else tr("Unidades: mm"))
        else:
            self.log(tr("No se encontró OpenSCAD. Instálalo desde openscad.org o elige el ejecutable en "
                        "Archivo › Preferencias…"), "warn")
        if self._gl_error:
            self.log(tr("Visor OpenGL no disponible ({error}). Se usa el visor de imágenes. "
                        "Instala lo necesario con:  python -m pip install pyqtgraph PyOpenGL numpy").format(
                error=self._gl_error), "warn")
        if path:
            self.load(path)
        else:
            self.set_document(self._new_document())  # en blanco; los ejemplos están en el menú Archivo

    # ------------------------------------------------------------- documento
    def set_document(self, doc: Document, path: str = "", keep_history: bool = False) -> None:
        self.runner.cancel_preview()       # el cálculo del documento anterior ya no sirve
        if self.gl:
            self.viewer.reset_scene()
        else:
            self.viewer.clear("")
        self.doc = doc
        self.path = path
        self.modified = False
        if not keep_history:
            self.history.clear()
        self.props.base_dir = os.path.dirname(path) if path else ""
        self.rebuild_tree([])
        self.refresh_code()
        self.update_title()
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
        colors = tree_colors(self.tree_on_viewer, self._light_viewer())
        item.setData(0, Qt.ItemDataRole.UserRole, node.id)
        item.setText(0, node.label)
        if isinstance(node, RawCode):
            item.setIcon(0, icon("comment" if node.is_comment else "lock", colors["raw"], fixed=True))
            item.setText(1, tr("comentario") if node.is_comment else tr("código"))
            item.setToolTip(0, node.text)
            f = item.font(0)
            f.setItalic(True)
            item.setFont(0, f)
            item.setForeground(0, QColor(colors["muted"]))
        else:
            item.setIcon(0, icon(node.kind, colors["icon"], fixed=True))
            cmd_text = f"{node.modifier}{node.kind}"
            extra_tip = ""

            # Clarificación didáctica del rol en operaciones booleanas
            if parent_node is not None and getattr(parent_node, "kind", "") == "difference":
                if child_index == 0:
                    cmd_text += f" [{tr('Base')} +]"
                    extra_tip = f"\n{tr('difference: Sólido BASE (al que se le resta)')}"
                else:
                    base_label = parent_node.children[0].label if parent_node.children else tr("Base")
                    cmd_text += f" [− {tr('Resta')}]"
                    extra_tip = f"\n{tr('difference: Sólido que se RESTA a')} '{base_label}'"
            elif parent_node is not None and getattr(parent_node, "kind", "") == "intersection":
                cmd_text += f" [∩ {tr('Interseca')}]"
                extra_tip = f"\n{tr('intersection: Sólido intersecado (volumen común)')}"
            elif parent_node is not None and getattr(parent_node, "kind", "") == "union":
                cmd_text += f" [∪ {tr('Unión')}]"
                extra_tip = f"\n{tr('union: Sólido fusionado en la unión')}"

            item.setText(1, cmd_text)
            item.setToolTip(0, node.call() + extra_tip)
            item.setFont(1, mono_font(9))
            if node.modifier == "*":
                item.setForeground(0, QColor(colors["disabled"]))
        item.setForeground(1, QColor(colors["muted"]))
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
        self._sync_model_panel()

    def _openscad_args(self) -> list:
        """Opciones para OpenSCAD: roof() (si se usa o está activado en Preferencias) y los
        parámetros extra que se escriban allí."""
        args = []
        if self.settings.value("enable_roof", False, bool) or any(
                getattr(n, "kind", "") == "roof" for n, _, _ in self.doc.walk()):
            args.append("--enable=roof")
        extra = str(self.settings.value("extra_flags", "", str) or "")
        try:
            args += [a.strip('"') for a in shlex.split(extra, posix=False)]
        except ValueError:                       # comillas sin cerrar: se ignoran los extra
            self.log(tr("Parámetros CLI extra no válidos: {flags}").format(flags=extra), "warn")
        return args

    def _new_document(self) -> Document:
        """Documento en blanco con el $fn por defecto de Preferencias (16 por defecto)."""
        val = self.settings.value("default_fn")
        fn = int(val) if val is not None else 16
        return Document(fn=fn if fn > 0 else None)

    def apply_settings(self) -> None:
        """Aplica las Preferencias que afectan a la ventana ya abierta."""
        self.apply_color_scheme()
        delay = int(self.settings.value("debounce_ms", 500) or 500)
        self.viewer.set_render_delay(delay)
        if self.gl:
            self.viewer.explode_factor = float(self.settings.value("explode_max_mult", 2.0) or 2.0)
            self.viewer.set_explosion(self.viewer._explosion)

    def _light_viewer(self) -> bool:
        return bool(getattr(self.viewer, "light_background", False))

    def apply_color_scheme(self) -> None:
        """Aplica el esquema de color de Preferencias a los dos visores."""
        scheme = colorschemes.get(self.settings.value("colorscheme", colorschemes.DEFAULT, str))
        self.runner.colorscheme = scheme.openscad_name
        if self.gl:
            self.viewer.set_color_scheme(scheme)
            self._update_ghosts()                  # los colores de las piezas sin color() cambian
            if self.tree_box is not None:          # el árbol sobre el visor cambia de colores
                for b in self.tree_tools:
                    b.setIcon(icon(b.property("icon_name"), tree_colors(True, self._light_viewer())["icon"],
                                   fixed=True))
                self.rebuild_tree(self.selected_ids())
        else:
            self.viewer.background = scheme.background
            self.viewer.update()

    def _sync_model_panel(self) -> None:
        """Con el árbol sobre el visor, las propiedades flotan a la derecha del visor y solo se ven
        con algo seleccionado. El visor no cambia de tamaño (antes se ocultaba el panel Modelo y
        el modelo se movía en pantalla con cada selección)."""
        if self.tree_box is not None:
            self.viewer.set_props_overlay_visible(bool(self.selected_ids()))

    def _move_props_to_viewer(self, on: bool) -> None:
        """Lleva el contenido del panel Modelo (propiedades y # % ! *) al visor, o lo devuelve.
        El panel Modelo y Variables, si es su pestaña vecina, se ocultan mientras tanto."""
        if on:
            for dock in [self.dock_model] + self.tabifiedDockWidgets(self.dock_model):
                if dock.isVisible():
                    dock.hide()
                    self._docks_hidden_by_tree.append(dock)
            self.viewer.show_props_overlay(self.model_panel)
        else:
            self.viewer.show_props_overlay(None)
            self.dock_model.setWidget(self.model_panel)
            hidden, self._docks_hidden_by_tree = self._docks_hidden_by_tree, []
            for dock in hidden:
                dock.show()
            self.dock_model.raise_()

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
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Popup)
        node = self.current_node()
        if node is not None and isinstance(node, RawCode):
            menu.addAction(tr("Editar en el código")).triggered.connect(lambda: self.edit_code_of(node.id))
            menu.addSeparator()

        # Opciones contextuales para operaciones booleanas
        if node is not None:
            _, parent = self.doc.parent_list(node.id)
            if parent is not None and getattr(parent, "kind", "") == "difference":
                if parent.children and parent.children[0].id != node.id:
                    menu.addAction(tr("Hacer sólido Base (al que se le resta)")).triggered.connect(
                        lambda: self.set_difference_base(parent.id, node.id)
                    )
                    menu.addSeparator()

            if getattr(node, "kind", "") in ("difference", "union", "intersection"):
                menu.addAction(icon(node.kind), tr("Asistente booleano…")).triggered.connect(
                    lambda: self.open_boolean_dialog(node.id)
                )
                menu.addSeparator()
            elif parent is not None and getattr(parent, "kind", "") in ("difference", "union", "intersection"):
                menu.addAction(icon(parent.kind), tr("Asistente booleano (del grupo)…")).triggered.connect(
                    lambda: self.open_boolean_dialog(parent.id)
                )
                menu.addSeparator()

        if node is not None and getattr(node, "kind", ""):
            menu.addAction(tr("Guía de esta operación…")).triggered.connect(
                lambda: self.open_operation_helper(node.kind)
            )
            menu.addSeparator()

        menu.addAction(tr("Nueva operación booleana…")).triggered.connect(
            lambda: self.open_boolean_dialog(node.id if node is not None else None)
        )
        wrap = menu.addMenu(tr("Envolver en…"))
        for kind in ("translate", "rotate", "scale", "mirror", "color", "union", "difference",
                     "intersection", "hull", "linear_extrude", "linear_array", "polar_array", "grid_array"):
            a = wrap.addAction(icon(kind), kind)
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
        from ..sketches import create_sketch_node
        from .sketch import SketchDialog
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
            self.statusBar().showMessage(tr("Perfil 2D creado: {name}").format(name=root.name), 4000)

    def open_hardware_dialog(self) -> None:
        from ..hardware import (create_bearing_node, create_bearing_seat_node, create_heat_set_node,
                                create_nut_node, create_oring_groove_node, create_profile_node,
                                create_ring_groove_node, create_screw_node, create_washer_node)
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

            builders = {
                "screw": lambda: create_screw_node(std, size, length, mode=mode, fit=fit, unique_fn=self.doc.unique_name),
                "nut": lambda: create_nut_node(std, size, mode=mode, fit=fit, unique_fn=self.doc.unique_name),
                "insert": lambda: create_heat_set_node(size, mode=mode, unique_fn=self.doc.unique_name),
                "washer": lambda: create_washer_node(size, unique_fn=self.doc.unique_name),
                "bearing": lambda: create_bearing_node(size, mode=mode, fit=fit, unique_fn=self.doc.unique_name),
                "profile": lambda: create_profile_node(size, length, unique_fn=self.doc.unique_name),
                "bearing_seat": lambda: create_bearing_seat_node(size, res["seat"], res["wall"],
                                                                 unique_fn=self.doc.unique_name),
                "ring_groove": lambda: create_ring_groove_node(std, size, unique_fn=self.doc.unique_name),
                "oring_groove": lambda: create_oring_groove_node(std, size, res["diameter"], res["seal"],
                                                                 unique_fn=self.doc.unique_name),
            }
            if cat not in builders:
                return
            try:
                node = builders[cat]()
            except ValueError as exc:  # métrica que no existe en esa norma
                QMessageBox.warning(self, tr("Componente estándar"), str(exc))
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
                    self.statusBar().showMessage(tr("Taladro de {size} restado en {name}").format(
                        size=size, name=target_node.name), 4000)
                    return

            target_id = sel[0] if len(sel) == 1 else None
            def change_add():
                target = self.doc.find(target_id) if target_id is not None else None
                if target is not None and target.is_container:
                    target.children.append(node)
                else:
                    self.doc.children.append(node)

            self.mutate(change_add, select=[node.id])
            self.statusBar().showMessage(tr("Componente añadido: {name}").format(name=node.name or node.label), 4000)

    def open_camshaft_dialog(self) -> None:
        from ..camshaft import create_camshaft
        from .camshaft_dialog import CamshaftDialog

        dlg = CamshaftDialog(parent=self)
        if not dlg.exec():
            return
        res = dlg.get_result()
        try:
            group = create_camshaft(res["shaft"], res["lobe"], dlg.items(),
                                    bearings=res.get("bearings"), ends=res.get("ends"),
                                    unique_fn=self.doc.unique_name)
        except ValueError as exc:   # orden de cilindros que no vale
            QMessageBox.warning(self, tr("Árbol de levas"), str(exc))
            return
        self.mutate(lambda: self.doc.children.append(group), select=[group.id])
        self.statusBar().showMessage(tr("Componente añadido: {name}").format(name=group.name), 4000)

    def layout_camshaft_for_print(self, node_id: int) -> None:
        from ..camshaft import layout_for_print
        node = self.doc.find_id(node_id)
        if node is None:
            return
        parent_list, parent_node = self.doc.parent_list(node_id)
        target = parent_node if parent_node and parent_node.kind == "group" else node
        print_group = layout_for_print(target, unique_fn=self.doc.unique_name)
        if not print_group.children:
            QMessageBox.information(self, tr("Impresión 3D"), tr("No se encontraron piezas del árbol de levas para disponer."))
            return
        self.mutate(lambda: self.doc.children.append(print_group), select=[print_group.id])
        self.statusBar().showMessage(tr("Piezas dispuestas para impresión 3D: {name}").format(name=print_group.name), 4000)

    def export_camshaft_parts(self, node_id: int) -> None:
        from ..camshaft import export_camshaft_parts
        node = self.doc.find_id(node_id)
        if node is None:
            return
        parent_list, parent_node = self.doc.parent_list(node_id)
        target = parent_node if parent_node and parent_node.kind == "group" else node
        folder = QFileDialog.getExistingDirectory(self, tr("Seleccionar carpeta para exportar piezas STL"))
        if not folder:
            return
        try:
            results = export_camshaft_parts(target, folder, exe=self.runner.exe)
            ok_count = sum(1 for _, _, ok in results if ok)
            total = len(results)
            self.statusBar().showMessage(tr("Exportadas {ok}/{total} piezas a {folder}").format(
                ok=ok_count, total=total, folder=folder), 5000)
            self.log(tr("Exportación de piezas completada: {ok}/{total} archivos STL en {folder}").format(
                ok=ok_count, total=total, folder=folder), "info")
            QMessageBox.information(self, tr("Exportar piezas"),
                                    tr("Se han exportado {ok} de {total} piezas en la carpeta:\n{folder}").format(
                                        ok=ok_count, total=total, folder=folder))
        except Exception as exc:
            QMessageBox.warning(self, tr("Exportar piezas"), str(exc))

    def open_transmission_dialog(self) -> None:
        from ..transmission import create_belt_drive, create_train
        from .transmission_dialog import TransmissionDialog

        dlg = TransmissionDialog(parent=self)
        if not dlg.exec():
            return
        res = dlg.get_result()
        if res["solution"] is None:
            return
        if res["drive"] == "gears":
            group = create_train(res["solution"], res["kind"], res["params"], res["stage_gap"], res["coaxial"],
                                 unique_fn=self.doc.unique_name)
        else:
            group = create_belt_drive(res["solution"], res["params"], res["belt"], unique_fn=self.doc.unique_name)
        self.mutate(lambda: self.doc.children.append(group), select=[group.id])
        self.statusBar().showMessage(tr("Componente añadido: {name}").format(name=group.name), 4000)

    def open_flange_dialog(self) -> None:
        from ..flanges import create_flange_node
        from .flange_dialog import FlangeDialog

        dlg = FlangeDialog(parent=self)
        if not dlg.exec():
            return
        res = dlg.get_result()
        try:
            node = create_flange_node(res["standard"], res["rating"], res["size"], res["type"], res["facing"],
                                      res["bore"] or None, unique_fn=self.doc.unique_name)
        except ValueError as exc:   # tamaño que la norma no tiene o agujero sin dar
            QMessageBox.warning(self, tr("Brida normalizada"), str(exc))
            return
        sel = self.selected_ids()
        target_id = sel[0] if len(sel) == 1 else None

        def change():
            target = self.doc.find(target_id) if target_id is not None else None
            if target is not None and target.is_container:
                target.children.append(node)
            else:
                self.doc.children.append(node)

        self.mutate(change, select=[node.id])
        self.statusBar().showMessage(tr("Componente añadido: {name}").format(name=node.name), 4000)

    def drawing_box(self, ids):
        """Caja (mínimo, máximo) de lo que va al plano: las piezas indicadas o, con None, todo.
        Para todo el modelo usa la malla de OpenSCAD si la caché la tiene al día (es la exacta,
        con las restas hechas); si no, y para una selección, la vista aproximada."""
        found = None
        if ids is None:
            code = generate(self.doc, header=False).text
            if meshcache.cacheable(code) and self.runner.exe:
                base = os.path.dirname(self.path) if self.path else ""
                key = meshcache.mesh_key(code, self._openscad_args(), self.runner.backend, self.runner.exe, base)
                cached = self.mesh_cache.get(key)
                if cached is not None and cached != meshcache.EMPTY and len(cached[0]):
                    found = geo.bbox(cached[0])
        if found is None:
            found = geo.model_box(self.doc, geo.build_ghosts(self.doc), ids)
        if found is None:
            return None
        lo, hi = found
        return tuple(float(v) for v in lo), tuple(float(v) for v in hi)

    DRAWING_KEYS = ("company", "checker", "material", "tolerance", "notes", "hidden", "dims")

    def open_drawing_dialog(self) -> None:
        from ..drawing import generate_technical_drawing_code, plan_sheet, scale_label
        from .drawing_dialog import DrawingDialog

        sel = self.selected_ids()
        def_author = self.settings.value("drawing_author", "Diseñador CAD", str)
        def_sheet = self.settings.value("drawing_sheet", "A4", str)
        defaults = {}
        for key in self.DRAWING_KEYS:
            value = self.settings.value(f"drawing_{key}", None)
            if value is not None:
                defaults[key] = value in (True, "true", "1") if key in ("hidden", "dims") else str(value)
        dlg = DrawingDialog(has_selection=bool(sel), default_author=def_author, default_sheet=def_sheet, parent=self,
                            defaults=defaults)
        if not dlg.exec():
            return
        cfg = dlg.get_config()
        # Lo que no cambia de un plano a otro se recuerda para el siguiente.
        self.settings.setValue("drawing_author", cfg["author"])
        for key in self.DRAWING_KEYS:
            value = cfg.get(key)
            self.settings.setValue(f"drawing_{key}", "\n".join(value) if key == "notes" else value)
        if cfg.get("use_selection") and sel:
            nodes = [self.doc.find(i) for i in sel if self.doc.find(i) is not None]
            target_code = "\n".join(generate(n, header=False).text.strip() for n in nodes)
            ids = [n.id for n in nodes]
        else:
            target_code = generate(self.doc, header=False).text
            ids = None
        sheet, views = cfg.get("sheet_size", "A4"), cfg.get("views")

        if cfg.get("action") == "insert":
            # En el modelo, como código OpenSCAD: siluetas con projection().
            box = self.drawing_box(ids)
            border = bool(cfg.get("include_border", True))
            scale, _, fits = plan_sheet(box, sheet, float(cfg.get("scale", 0.0)), views, border)
            drawing_code = generate_technical_drawing_code(
                target_code=target_code, title=cfg.get("title", ""), author=cfg.get("author", ""),
                sheet_size=sheet, scale=scale, views=views, include_border=border, box=box)
            if not fits:
                self._warn_drawing_scale(scale_label(scale))

            def change():
                self.doc.children.append(RawCode(drawing_code))
            self.mutate(change)
            self.statusBar().showMessage(tr("Plano técnico insertado en el modelo"), 4000)
            return

        if not self.runner.exe:
            self.configure_openscad()
            if not self.runner.exe:
                return
        base = os.path.splitext(self.path)[0] if self.path else os.path.join(
            self.settings.value("last_dir", "", str), "plano_tecnico")
        filters = "PDF (*.pdf);;SVG (*.svg);;DXF (*.dxf);;Todos (*)"
        path, chosen = QFileDialog.getSaveFileName(self, tr("Exportar plano técnico"), base + ".pdf", filters)
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".dxf" if "*.dxf" in chosen else ".svg" if "*.svg" in chosen else ".pdf"
        # La lámina se dibuja con la malla final de OpenSCAD: la de la caché si está al día y es todo
        # el modelo; si no, se le pide a OpenSCAD y se sigue en on_exported.
        tris = self._cached_mesh() if ids is None else None
        if tris is not None:
            self._write_drawing(tris, cfg, path)
            return
        stl = os.path.join(tempfile.mkdtemp(prefix="scadgui_plano_"), "pieza.stl")
        self._drawing_job = (stl, path, cfg)
        self.runner.extra_args = self._openscad_args()
        self.runner.export(target_code, os.path.dirname(self.path) if self.path else "", stl)
        self.statusBar().showMessage(tr("Calculando la pieza para el plano…"))

    def _cached_mesh(self):
        code = generate(self.doc, header=False).text
        if not (meshcache.cacheable(code) and self.runner.exe):
            return None
        base = os.path.dirname(self.path) if self.path else ""
        key = meshcache.mesh_key(code, self._openscad_args(), self.runner.backend, self.runner.exe, base)
        cached = self.mesh_cache.get(key)
        if cached is None or cached == meshcache.EMPTY or not len(cached[0]):
            return None
        return cached[0]

    def _warn_drawing_scale(self, label: str) -> None:
        QMessageBox.warning(self, tr("Generar plano técnico 2D"),
                            tr("Las vistas no caben en la hoja a escala {s}: elige una escala menor, "
                               "la automática o una hoja más grande.").format(s=label))

    def _write_drawing(self, tris, cfg: dict, path: str) -> bool:
        """Dibuja la lámina con las aristas de la malla y la guarda en SVG, DXF o PDF."""
        from .. import drawing_lines as dl
        from ..drawing import scale_label
        from ..drawing_sheet import SheetInfo, build_sheet, to_dxf, to_svg
        if tris is None or not len(tris):
            QMessageBox.warning(self, tr("Generar plano técnico 2D"),
                                tr("El plano necesita piezas 3D: lo seleccionado no tiene volumen."))
            return False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            views = cfg.get("views") or {}
            me = dl.mesh_edges(tris)
            lines = {k: dl.view_lines(me, tris, k, hidden=bool(cfg.get("hidden", True)) and k != "isometric")
                     for k in ("front", "top", "side", "isometric") if views.get(k, True)}
            lo, hi = geo.bbox(tris)
            box = (tuple(float(v) for v in lo), tuple(float(v) for v in hi))
            info = SheetInfo(title=cfg.get("title", ""), description=cfg.get("description", ""),
                             company=cfg.get("company", ""), number=cfg.get("number", ""),
                             revision=cfg.get("revision", ""), material=cfg.get("material", ""),
                             density=cfg.get("density"), author=cfg.get("author", ""),
                             checker=cfg.get("checker", ""), tolerance=cfg.get("tolerance", ""),
                             notes=list(cfg.get("notes") or []))
            sheet = build_sheet(lines, box, info, cfg.get("sheet_size", "A4"), float(cfg.get("scale", 0.0)),
                                views, bool(cfg.get("dims", True)), dl.mesh_volume(tris))
            ext = os.path.splitext(path)[1].lower()
            if ext == ".dxf":
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(to_dxf(sheet))
            elif ext == ".pdf":
                from ..pdfsheet import svg_to_pdf
                folder = tempfile.mkdtemp(prefix="scadgui_pdf_")
                svg = os.path.join(folder, "lamina.svg")
                with open(svg, "w", encoding="utf-8") as fh:
                    fh.write(to_svg(sheet, info.title))
                try:
                    svg_to_pdf(svg, path, sheet.w, sheet.h, info.title)
                finally:
                    shutil.rmtree(folder, ignore_errors=True)
            else:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(to_svg(sheet, info.title))
        except (OSError, ValueError, RuntimeError) as exc:
            self.log(tr("No se pudo crear el plano: {error}").format(error=exc), "error")
            return False
        finally:
            QApplication.restoreOverrideCursor()
        if not sheet.fits:
            self._warn_drawing_scale(scale_label(sheet.scale))
        self.log(tr("Exportado: {path}").format(path=path), "info")
        self.statusBar().showMessage(f"{tr('Exportado')}: {path}", 6000)
        return True

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
                self.statusBar().showMessage(tr("Operación booleana aplicada: {kind}()").format(kind=kind), 4000)

    def finish_edges(self, mode: str, value: float, edges: list) -> None:
        """Redondea, achaflana o deja vivas las aristas elegidas en el visor."""
        try:
            finish_edges(self.doc.snapshot(), edges, mode, value)  # primero se comprueba en una copia
        except ValueError as exc:
            QMessageBox.warning(self, tr("Aristas"), str(exc))
            return
        changed = {}
        self.mutate(lambda: changed.update(ids=finish_edges(self.doc, edges, mode, value)))
        ids = changed.get("ids", [])
        if ids:
            self.select_ids(ids)
        message = {"round": tr("Aristas redondeadas: {n}"), "chamfer": tr("Aristas achaflanadas: {n}"),
                   "none": tr("Aristas sin tratar: {n}")}[mode]
        self.statusBar().showMessage(message.format(n=len(edges)), 4000)

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
        if kind == "flange_wizard":
            self.open_flange_dialog()
            return
        if kind == "camshaft_wizard":
            self.open_camshaft_dialog()
            return
        if kind == "transmission_wizard":
            self.open_transmission_dialog()
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
                self.log(tr("{op}: normalmente se usa con 2 o más piezas seleccionadas "
                            "(Ctrl+clic en el árbol). Puedes meter más piezas dentro después.").format(
                    op=tr(spec.label)), "info")
        else:
            def change():
                created["node"] = self.doc.add(kind, target)
            if spec.category == "array":
                self.log(tr("La matriz está vacía: arrastra dentro, en el árbol, la pieza que quieres "
                            "repetir, o selecciónala antes de pulsar el botón."), "info")
        self.mutate(change, select=None)
        if "node" in created:
            self.select_ids([created["node"].id])
            self.statusBar().showMessage(tr("{piece} creado: {code}").format(
                piece=tr(spec.label), code=created["node"].call()), 4000)

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
                _module, call_node = self.doc.make_module(sel, mod_name, bindings)
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

    def add_meshing_gear(self, node_id: int, teeth: int = 0) -> None:
        """Panel del engranaje, la cremallera o el estriado › botón de la pareja: crea la pieza que encaja."""
        created = {}

        def change():
            created["n"] = self.doc.add_meshing_gear(node_id, teeth or None)
        self.mutate(change)
        if created.get("n") is not None:
            self.select_ids([created["n"].id])

    def fix_radii(self, node_id: int) -> None:
        self.mutate(lambda: self.doc.fix_radii(node_id) or False, rebuild_tree=False)
        self._refresh_item(node_id)
        self.on_selection()

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
            self.log(tr("No se pudo calcular la vista aproximada: {error}").format(error=exc), "warn")
        colors = geo.node_colors(self.doc, resolve=_qt_color)
        self.viewer.set_ghosts(self.ghosts, colors, hashed, background,
                               part_of=geo.assembly_parts(self.doc), subtracted=geo.subtracted_ids(self.doc))
        if self.gl:
            self.viewer.set_edge_targets(geo.pickable_edges(self.doc))
        self._update_highlight()

    def _update_highlight(self) -> None:
        sel = self.selected_ids()
        tris = geo.collect(self.doc, self.ghosts, sel)
        self.viewer.set_highlight(tris if len(tris) else None)
        if self.gl:
            gizmo_enabled = self.settings.value("gizmo_enabled", True, bool)
            if gizmo_enabled and len(sel) == 1 and len(tris) > 0:
                # Centro de la caja (la media de vértices se desplaza hacia donde hay más triángulos)
                # y ejes proporcionales al tamaño de la pieza.
                lo, hi = geo.bbox(tris)
                length = max(5.0, 0.75 * float(np.max(hi - lo)))
                self.viewer.set_gizmo((lo + hi) / 2, length)
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

        # Determinar el nodo translate a modificar (o envolver de inmediato si no tiene).
        # El translate del padre solo vale si la pieza es su único hijo: si no, movería también a sus hermanos.
        if node.kind == "translate" and "v" in node.params:
            self._gizmo_target_id = node.id
        else:
            _, parent = self.doc.parent_list(node.id)
            if parent is not None and parent.kind == "translate" and "v" in parent.params \
                    and len(parent.children) == 1:
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
        if not self._dragging_gizmo:
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

        # Solo se recalculan las mallas aproximadas; OpenSCAD se ejecuta al soltar
        if self.gl:
            self._update_ghosts()

        self.statusBar().showMessage(
            tr("Moviendo {name}: X={x} mm  Y={y} mm  Z={z} mm  (paso: {step} mm)").format(
                name=target.name or target.label, x=f"{new_v[0]:.2f}", y=f"{new_v[1]:.2f}",
                z=f"{new_v[2]:.2f}", step=snap),
            2000
        )

    def on_gizmo_finished(self) -> None:
        if not self._dragging_gizmo:
            return

        self._dragging_gizmo = False
        before, self._gizmo_before = self._gizmo_before, None
        target = self.doc.find(self._gizmo_target_id)
        if target is None or target.params.get("v") == self._gizmo_initial_v:
            # Clic en un eje sin arrastrar: se deshace el translate que se creó al pulsar.
            if before is not None:
                self.doc = before
                self.rebuild_tree([self._gizmo_active_node_id])
                self.refresh_code()
            return
        if before is not None:
            self.history.push(before)  # cada arrastre es un paso de deshacer

        self.modified = True
        self.update_title()
        self.refresh_code()
        self._refresh_item(self._gizmo_target_id)
        active_node = self.doc.find(self._gizmo_active_node_id)
        if active_node is not None:
            self.props.show_node(active_node, self.doc)
        self.vars_panel.refresh()

        self.render_view(False)
        self.statusBar().showMessage(tr("Posición fijada"), 3000)

    def on_variable_added(self, name: str, value: str, comment: str) -> None:
        self.mutate(lambda: self.doc.set_variable(name, value, comment), rebuild_tree=True)
        self.vars_panel.refresh()

    def on_variable_changed(self, name: str, value: str, comment: str) -> None:
        self.mutate(lambda: self.doc.set_variable(name, value, comment), rebuild_tree=True, key=("var", name))

    def on_variable_deleted(self, name: str) -> None:
        self.mutate(lambda: self.doc.delete_variable(name), rebuild_tree=True)
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
            self.statusBar().showMessage(tr("Editando el código: pulsa Aplicar (Ctrl+Enter) para "
                                            "actualizar el árbol, o Descartar (Esc)."))
        else:
            self.statusBar().clearMessage()

    def apply_code(self, text: str) -> None:
        try:
            new_doc = parse(text)
        except ParseError as exc:
            self.log(tr("No se pudo leer el código: {error}").format(error=exc), "error")
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
            self._show_empty_message()
            self.viewer.status.setText("")
            return
        if not self.runner.exe:
            self.viewer.clear(tr("No se encontró OpenSCAD.\nInstálalo desde openscad.org o indica dónde está."))
            self.viewer.show_setup_button(True)
            return
        self.viewer.show_setup_button(False)
        highlight = [] if full else [i for i in self.selected_ids() if isinstance(self.doc.find(i), Node)]
        code = generate(self.doc, highlight=highlight, header=False).text
        self.runner.extra_args = self._openscad_args()
        base = os.path.dirname(self.path) if self.path else ""
        self.runner.render_image(code, base, self.viewer.render_size(), self.viewer.camera, full_render=full)

    def _show_empty_message(self) -> None:
        self.viewer.clear(tr("Crea una pieza con los botones de arriba para verla aquí."))
        self._empty_message = True

    def _retranslate_view_message(self) -> None:
        """Vuelve a escribir en el idioma nuevo el aviso del visor (sin volver a renderizar)."""
        if not any(True for _ in self.doc.walk()):
            self._show_empty_message()
        elif not self.runner.exe:
            if self.gl:
                self.viewer.show_message(tr("Vista aproximada (sin operaciones booleanas).\n"
                                            "Instala OpenSCAD o indica dónde está para ver el resultado real."))
            else:
                self.viewer.clear(tr("No se encontró OpenSCAD.\nInstálalo desde openscad.org o indica dónde está."))

    def _render_mesh(self) -> None:
        """Visor OpenGL: pide a OpenSCAD la malla final del modelo."""
        if not any(True for _ in self.doc.walk()):
            self.runner.cancel_preview()
            self._show_empty_message()
            self.viewer.status.setText("")
            return
        if not self.runner.exe:
            self.viewer.set_mesh(None)
            self.viewer.show_message(tr("Vista aproximada (sin operaciones booleanas).\n"
                                        "Instala OpenSCAD o indica dónde está para ver el resultado real."))
            self.viewer.show_setup_button(True)
            return
        self.viewer.show_setup_button(False)
        if self._empty_message:                   # ya hay piezas: el aviso del documento vacío sobra
            self.viewer.show_message("")
            self._empty_message = False
        code = generate(self.doc, header=False).text
        self.runner.extra_args = self._openscad_args()
        base = os.path.dirname(self.path) if self.path else ""
        self._mesh_key = None
        if meshcache.cacheable(code):
            key = meshcache.mesh_key(code, self.runner.extra_args, self.runner.backend, self.runner.exe, base)
            cached = self.mesh_cache.get(key)
            if cached is not None:
                self.runner.cancel_preview()      # un cálculo anterior ya no debe llegar al visor
                if cached == meshcache.EMPTY:
                    self.on_mesh_empty()
                else:
                    self._show_mesh(*cached, tr("en caché"))
                return
            self._mesh_key = key
        self.runner.export_mesh(code, base)

    def on_mesh(self, path: str, seconds: float) -> None:
        try:
            tris, face_colors = geo.load_mesh(path)
        except (OSError, ValueError, IndexError) as exc:
            self.log(tr("No se pudo leer la malla: {error}").format(error=exc), "error")
            return
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        if self._mesh_key is not None:
            self.mesh_cache.put(self._mesh_key, (tris, face_colors))
            self._mesh_key = None
        self._show_mesh(tris, face_colors, f"{seconds:.1f} s")

    def _show_mesh(self, tris, face_colors, timing: str) -> None:
        self.viewer.set_mesh(tris, face_colors)
        self.viewer.status.setText(f"{tr('Listo')} · {timing} · {len(tris):,} {tr('triángulos')}".replace(",", "."))

    def on_mesh_empty(self) -> None:
        if self._mesh_key is not None:
            self.mesh_cache.put(self._mesh_key, meshcache.EMPTY)
            self._mesh_key = None
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

    def set_compact(self, on: bool) -> None:
        """Modo compacto: cinta mínima, sin barra principal (sus botones van junto a las pestañas)
        y sin los paneles Modelo, Variables y Consola; con el visor OpenGL, el árbol y las
        propiedades flotan sobre él. Al salir, todo vuelve a como estaba."""
        on = bool(on)
        if on == (self._compact_saved is not None):
            return
        if on:
            self._compact_saved = (self.saveState(), self.tree_box is not None)
            self.set_tree_overlay(True)              # oculta el panel Modelo y lleva sus piezas al visor
            for dock in (self.dock_model, self.dock_vars, self.dock_console):
                dock.hide()
            self.main_toolbar.hide()
        else:
            state, tree_was_on = self._compact_saved
            self._compact_saved = None
            self.set_tree_overlay(tree_was_on)
            self.restoreState(state)
        self.ribbon.set_compact(on)
        self.ribbon_corner.setVisible(on)
        self.a_compact.blockSignals(True)
        self.a_compact.setChecked(on)
        self.a_compact.blockSignals(False)
        self.settings.setValue("compact", on)

    def set_fullscreen(self, on: bool) -> None:
        on = bool(on)
        if getattr(self, "_is_fullscreen", False) == on:
            return
        self._is_fullscreen = on
        if on:
            self._was_maximized = self.isMaximized()
            if not self._was_maximized:
                self._saved_geometry = self.saveGeometry()
            # En Windows DWM, showFullScreen() puede ocultar los menús desplegables
            # (QMenu) por detrás de la ventana por la exclusividad de pantalla completa.
            # El modo sin bordes cubre toda la pantalla y mantiene los menús siempre visibles.
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            screen = self.screen() or QGuiApplication.primaryScreen()
            if screen is not None:
                self.setGeometry(screen.geometry())
            self.show()
        else:
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
            if getattr(self, "_was_maximized", False):
                self.showMaximized()
            else:
                self.showNormal()
                if hasattr(self, "_saved_geometry"):
                    self.restoreGeometry(self._saved_geometry)
                self._clamp_to_screen()
        self.a_fullscreen.blockSignals(True)
        self.a_fullscreen.setChecked(on)
        self.a_fullscreen.blockSignals(False)

    def set_tree_overlay(self, on: bool) -> None:
        """Mueve el árbol (con su barra de herramientas) encima del visor 3D, o lo devuelve al panel.

        Las propiedades y los modificadores # % ! * se quedan en el panel Modelo.
        """
        on = bool(on) and self.gl
        if on == (self.tree_box is not None):
            return
        if on:
            box = QWidget()
            box_lay = QVBoxLayout(box)
            box_lay.setContentsMargins(0, 0, 0, 0)
            box_lay.setSpacing(0)
            box_lay.addWidget(self.tree_tools_box)
            box_lay.addWidget(self.tree, 1)
            self.tree_box = box
            self.viewer.show_tree_overlay(box)
            self._move_props_to_viewer(True)
        else:
            self.model_layout.insertWidget(1, self.tree_tools_box)
            self.model_split.insertWidget(0, self.tree)
            self.tree_tools_box.show()
            self.tree.show()
            self.viewer.show_tree_overlay(None)
            self.tree_box.deleteLater()
            self.tree_box = None
            self._move_props_to_viewer(False)        # las propiedades vuelven al panel Modelo
        self.tree_on_viewer = on
        for b in self.tree_tools:
            b.setIcon(icon(b.property("icon_name"), tree_colors(on, self._light_viewer())["icon"], fixed=True))
        self.rebuild_tree(self.selected_ids())
        self.a_tree_overlay.blockSignals(True)
        self.a_tree_overlay.setChecked(on)
        self.a_tree_overlay.blockSignals(False)
        self.settings.setValue("tree_overlay", on)

    def _toggle_gl(self, on: bool) -> None:
        self.settings.setValue("viewer", "gl" if on else "image")
        self._offer_restart(tr("Visor 3D"), tr("El cambio de visor se aplica al reiniciar la aplicación."))

    def _toggle_theme(self, dark: bool) -> None:
        self.settings.setValue("theme", "dark" if dark else "light")
        self._offer_restart(tr("Tema"), tr("El cambio de tema se aplica al reiniciar la aplicación."))

    def _offer_restart(self, title: str, text: str) -> None:
        """Ofrece reiniciar ya (guardando antes si hace falta) y vuelve a abrir el mismo archivo."""
        box = QMessageBox(QMessageBox.Icon.Information, title, text, parent=self)
        now = box.addButton(tr("Reiniciar ahora"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Más tarde"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is now and self.maybe_save():
            self.restart()

    def restart(self) -> None:
        """Cierra la aplicación y la abre de nuevo con el archivo actual."""
        files = [self.path] if self.path else []
        if getattr(sys, "frozen", False):            # ejecutable empaquetado (.exe)
            program, args = sys.executable, files
        else:
            program, args = sys.executable, [os.path.abspath(sys.argv[0])] + files
        if QProcess.startDetached(program, args):
            self.modified = False                    # ya se guardó (o se descartó) en maybe_save
            QApplication.instance().quit()

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
            self.set_document(self._new_document())

    def open_example(self, path: str) -> None:
        """Abre un ejemplo como documento sin guardar (no se sobrescribe el archivo del ejemplo)."""
        if not self.maybe_save():
            return
        if not os.path.isfile(path):
            self.set_document(self._new_document())
            return
        with open(path, encoding="utf-8") as fh:
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
            if self.doc.header_lang is None:        # archivo nuevo: la cabecera en el idioma de hoy
                self.doc.header_lang = get_language()
            with open(self.path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(generate(self.doc, header_lang=self.doc.header_lang).text)
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
        self.runner.extra_args = self._openscad_args()
        self.runner.export(code, os.path.dirname(self.path) if self.path else "", path)

    def on_exported(self, path: str, ok: bool) -> None:
        job = self._drawing_job
        if job is not None and path == job[0]:
            # La malla que pidió el plano técnico: se dibuja la lámina con ella.
            self._drawing_job = None
            stl, out, cfg = job
            tris = geo.load_stl(stl) if ok and os.path.isfile(stl) else None
            shutil.rmtree(os.path.dirname(stl), ignore_errors=True)
            if tris is None:
                self.log(tr("OpenSCAD no pudo calcular la pieza para el plano. Mira los mensajes de arriba."),
                         "error")
                self.viewer.status.setText(tr("Error al exportar"))
            else:
                self._write_drawing(tris, cfg, out)
            self.schedule_preview()
            return
        if ok:
            self.log(tr("Exportado: {path}").format(path=path), "info")
            self.statusBar().showMessage(f"{tr('Exportado')}: {path}", 6000)
        else:
            self.log(tr("Falló la exportación a {path}. Mira los mensajes de OpenSCAD arriba "
                        "(¿formato 2D con piezas 3D o al revés?).").format(path=path), "error")
        self.viewer.status.setText(tr("Exportado") if ok else tr("Error al exportar"))
        self.schedule_preview()

    def open_preferences(self) -> None:
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
                self.a_gizmo.blockSignals(True)       # Preferencias y Ver › Flechas, siempre iguales
                self.a_gizmo.setChecked(self.viewer.gizmo_enabled)
                self.a_gizmo.blockSignals(False)
                self.viewer.snap_step = float(self.settings.value("gizmo_snap", 1.0) or 1.0)
                self._update_highlight()

            self.apply_settings()
            self.render_view(False)
            self.statusBar().showMessage(tr("Preferencias guardadas"), 4000)
            self.log(f"{tr('Preferencias guardadas')}. OpenSCAD: {exe or tr('no configurado')}", "info")

            if new_lang != old_lang:
                self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Actualiza dinámicamente los textos de la ventana principal al cambiar de idioma."""
        for a, text, tip in self._action_defs:
            a.setText(tr(text))
            if tip:
                t = tr(tip)
                a.setToolTip(t)
                a.setStatusTip(t)

        self.menuBar().clear()
        self._build_menus()
        self._fill_view_menu()
        self._retranslate_view_message()

        self.ribbon.retranslate_ui()
        self.viewer.retranslate_ui()
        self.dock_model.setWindowTitle(tr("Modelo"))
        self.dock_code.setWindowTitle(tr("Código"))
        self.code.retranslate_ui()
        if not self.code.editing:     # la cabecera del código ("// Generado con…") va en el idioma nuevo
            self.refresh_code()

        self.dock_console.setWindowTitle(tr("Consola"))
        self.dock_vars.setWindowTitle(tr("Variables"))
        self.tree.setHeaderLabels([tr("Nombre"), tr("Comando")])
        self.engine.setItemText(0, tr("Automático"))
        self.engine.setItemText(1, tr("Manifold (rápido)"))
        self.engine.setItemText(2, tr("CGAL (clásico)"))
        version = self.runner.version()
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
            if getattr(self, "_is_fullscreen", False):
                self.set_fullscreen(False)
            self.settings.setValue("geometry", self.saveGeometry())
            self.runner.cancel()
            event.accept()
        else:
            event.ignore()

