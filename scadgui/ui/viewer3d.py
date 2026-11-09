"""Visor 3D real con OpenGL (pyqtgraph): giro fluido, selección con clic y medición.

La malla final la calcula OpenSCAD (se exporta a STL al cambiar el modelo).
El resaltado de la selección usa las mallas aproximadas de ``geometry.py``,
así que seleccionar no necesita volver a ejecutar OpenSCAD.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from OpenGL import GL
from PySide6.QtCore import QPoint, QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton, QScrollArea, QSlider, QTextEdit, QVBoxLayout,
                               QWidget)

from .. import geometry as geo
from ..i18n import tr

CAMERAS = {  # elevación, azimut (la cámara mira hacia el centro desde esa dirección)
    "iso": (30.0, -55.0),
    "front": (0.0, -90.0),   # desde -Y, como la vista frontal de Blender
    "back": (0.0, 90.0),
    "right": (0.0, 0.0),
    "left": (0.0, 180.0),
    "top": (90.0, -90.0),
    "bottom": (-90.0, -90.0),
}
VIEWS = {  # botones de la barra → cámara
    "Isométrica": "iso",
    "Frontal": "front",
    "Superior": "top",
    "Derecha": "right",
}
# Teclas como en Blender (teclado numérico o fila de números, con la vista 3D activa):
# tecla → (acción, acción con Ctrl)
VIEW_KEYS = {
    "1": ("front", "back"),
    "3": ("right", "left"),
    "7": ("top", "bottom"),
    "0": ("iso", "iso"),
    "9": ("opposite", "opposite"),
    "5": ("projection", "projection"),
    "8": ("orbit_up", "orbit_up"),
    "2": ("orbit_down", "orbit_down"),
    "4": ("orbit_left", "orbit_left"),
    "6": ("orbit_right", "orbit_right"),
    ".": ("frame_selected", "frame_selected"),
    "R": ("ruler", "ruler"),
    "G": ("grid", "grid"),
    "Z": ("display_next", "display_next"),   # modo de visualización (Ctrl+Z es Deshacer)
    "S": ("smooth", "smooth"),               # sombreado suave Shade Smooth
    "s": ("smooth", "smooth"),
    "home": ("frame_all", "frame_all"),
}
SHORTCUT_OF = {"Isométrica": "0", "Frontal": "1", "Superior": "7", "Derecha": "3"}
# Nombre de cada cámara en la etiqueta del visor; si la cámara no está en ninguna, "Libre".
N_ = str  # texto que se traduce después con tr() (lo recoge test_i18n)
CAMERA_NAMES = {"iso": N_("Isométrica"), "front": N_("Frontal"), "back": N_("Trasera"), "right": N_("Derecha"),
                "left": N_("Izquierda"), "top": N_("Superior"), "bottom": N_("Inferior")}
# Colores de los ejes X, Y, Z (regla e indicador de orientación).
AXIS_COLORS = ("#E5645A", "#6CCB7A", "#5B9BFF")
ORBIT_STEP = 15.0      # grados por pulsación, como Blender
TREE_OVERLAY_WIDTH = 330
PROPS_OVERLAY_WIDTH = 340   # propiedades flotando a la derecha (con el árbol sobre el visor)
ORTHO_FOV = 1.0        # la vista ortográfica se imita con un ángulo de cámara casi nulo
PERSPECTIVE_FOV = 45.0

# Dibujar encima de la pieza (como el modificador # de OpenSCAD)
SEE_THROUGH = {
    GL.GL_DEPTH_TEST: False,
    GL.GL_BLEND: True,
    GL.GL_CULL_FACE: False,
    "glBlendFunc": (GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA),
}
# El gizmo se dibuja siempre encima de las piezas. Sus conos son cerrados y con las caras hacia
# fuera: sin prueba de profundidad, basta con no pintar las caras traseras para que se vean bien.
# Caras opacas un poco «empujadas» hacia el fondo: las líneas de la malla y los contornos, que están
# a la misma profundidad, se ven enteras en lugar de a trozos.
MODEL_SOLID = {
    GL.GL_DEPTH_TEST: True,
    GL.GL_BLEND: False,
    GL.GL_CULL_FACE: False,
    GL.GL_POLYGON_OFFSET_FILL: True,
    "glPolygonOffset": (1.0, 1.0),
}
ON_TOP_SOLID = {
    GL.GL_DEPTH_TEST: False,
    GL.GL_BLEND: False,
    GL.GL_CULL_FACE: True,
}

EDGE_COLOR = (0.10, 0.12, 0.16, 0.85)
EDGE_ON_DARK = (0.82, 0.86, 0.92, 0.95)     # contornos de «Sin líneas ocultas» sobre fondo oscuro
WIRE_ON_DARK = (0.78, 0.84, 0.95, 0.55)     # aristas de la vista alámbrica
WIRE_ON_LIGHT = (0.12, 0.15, 0.22, 0.55)
WIRE_OVER_FACES = (0.05, 0.07, 0.10, 0.32)  # malla sobre las caras sombreadas
SELECT_COLOR = (1.0, 0.55, 0.14, 0.38)
SELECT_EDGE = (1.0, 0.62, 0.25, 1.0)
HASH_COLOR = (1.0, 0.35, 0.55, 0.30)      # piezas con #
BACKGROUND_COLOR = (0.75, 0.78, 0.82, 0.18)  # piezas con %
MEASURE_COLOR = (0.35, 0.85, 1.0, 1.0)
EDGE_HOVER_COLOR = (1.0, 0.85, 0.2, 1.0)    # arista bajo el ratón en el modo aristas
EDGE_PICKED_COLOR = (1.0, 0.45, 0.1, 1.0)   # aristas elegidas
EDGE_PICK_PIXELS = 8                        # distancia máxima al ratón para elegir una arista
GIZMO_COLORS = ((1.0, 0.2, 0.2, 1.0), (0.2, 0.9, 0.2, 1.0), (0.2, 0.5, 1.0, 1.0))   # X, Y, Z
GIZMO_HEAD_LENGTH = 0.2     # largo de la punta de flecha, en fracción del eje
GIZMO_HEAD_RADIUS = 0.06    # radio de su base
GIZMO_PICK_PIXELS = 7                       # y para agarrar un eje del gizmo


def _mesh_item(color, options, depth=0):
    """Malla sin shader: la iluminación se calcula en geometry.shade() y llega como color por cara.

    Así se ve igual en cualquier versión de pyqtgraph y ninguna cara queda negra.
    """
    item = gl.GLMeshItem(meshdata=gl.MeshData(), smooth=False, shader=None, color=color,
                         glOptions=options)
    item.setDepthValue(depth)
    item.setVisible(False)
    item.base_color = color
    return item


def _line_item(color, width, options="opaque", depth=0):
    item = gl.GLLinePlotItem(pos=np.zeros((2, 3)), mode="lines", color=color, width=width,
                             antialias=True, glOptions=options)
    item.setDepthValue(depth)
    item.setVisible(False)
    return item


def _set_mesh(item, tris, face_colors=None) -> None:
    """Carga triángulos con su color por cara o por vértice (ya iluminado). Sin colores, usa el del elemento."""
    if tris is None or len(tris) == 0:
        item.setVisible(False)
        return
    if face_colors is None:
        base = np.tile(np.array(item.base_color, dtype=np.float64), (len(tris), 1))
        face_colors = geo.shade(geo.face_normals(tris), base)
        vcolors = np.repeat(np.asarray(face_colors, dtype=np.float32)[:, None, :], 3, axis=1)
    else:
        c_arr = np.asarray(face_colors, dtype=np.float32)
        if c_arr.ndim == 2:
            vcolors = np.repeat(c_arr[:, None, :], 3, axis=1)
        elif c_arr.ndim == 3:
            vcolors = c_arr
        else:
            vcolors = np.repeat(c_arr.reshape(-1, 4)[:, None, :], 3, axis=1)
    item.setMeshData(meshdata=gl.MeshData(vertexes=np.ascontiguousarray(tris, dtype=np.float32),
                                          vertexColors=np.ascontiguousarray(vcolors)))
    item.setVisible(True)


def _set_lines(item, segments) -> None:
    if segments is None or len(segments) == 0:
        item.setVisible(False)
        return
    item.setData(pos=np.ascontiguousarray(segments.reshape(-1, 3), dtype=np.float32))
    item.setVisible(True)


def _rgba(hex_color: str, alpha: float = 1.0):
    c = QColor(hex_color)
    return (c.redF(), c.greenF(), c.blueF(), alpha)


class _AxisTriad(QWidget):
    """Indicador de orientación de los ejes (abajo a la izquierda), como el de OpenSCAD o Blender."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(74, 74)
        self.elev, self.azim = 30.0, -55.0

    def set_angles(self, elev: float, azim: float) -> None:
        self.elev, self.azim = elev, azim
        self.update()

    def paintEvent(self, _ev):
        e, a = math.radians(self.elev), math.radians(self.azim)
        right = np.array([-math.sin(a), math.cos(a), 0.0])
        up = np.array([-math.sin(e) * math.cos(a), -math.sin(e) * math.sin(a), math.cos(e)])
        toward = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        center, length = QPointF(37, 37), 24.0
        font = QFont(p.font())
        font.setPointSizeF(7.5)
        font.setBold(True)
        p.setFont(font)
        # De atrás hacia delante, para que el eje que apunta a la cámara quede encima.
        for axis in sorted(range(3), key=lambda i: toward[i]):
            v = np.eye(3)[axis]
            tip = center + QPointF(float(right @ v) * length, -float(up @ v) * length)
            label = center + QPointF(float(right @ v) * (length + 9), -float(up @ v) * (length + 9))
            p.setPen(QPen(QColor(AXIS_COLORS[axis]), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(center, tip)
            p.drawText(label + QPointF(-3, 4), "XYZ"[axis])
        p.end()


class _GLView(gl.GLViewWidget):
    clicked = Signal(float, float, bool)   # x, y, Ctrl pulsado
    hovered = Signal(float, float)
    viewKey = Signal(str, bool)            # tecla de VIEW_KEYS, Ctrl pulsado
    gizmoStarted = Signal()
    gizmoMoved = Signal(float, float, float)  # dx, dy, dz totales acumulados desde el inicio del clic
    gizmoFinished = Signal()
    cameraChanged = Signal()               # giro de la cámara (teclas, botones o ratón)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._press = None
        self.gizmo_origin: Optional[np.ndarray] = None
        self.gizmo_len: float = 25.0
        self._active_axis: Optional[str] = None
        self._drag_start_s: float = 0.0
        self._drag_origin: Optional[np.ndarray] = None
        self.setMouseTracking(True)  # para resaltar la arista bajo el ratón sin pulsar
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def setCameraPosition(self, *args, **kwargs):
        super().setCameraPosition(*args, **kwargs)
        self.cameraChanged.emit()

    def orbit(self, *args, **kwargs):          # lo llama pyqtgraph al girar con el ratón
        super().orbit(*args, **kwargs)
        self.cameraChanged.emit()

    def wheelEvent(self, ev):                  # zoom: la regla cambia de paso
        super().wheelEvent(ev)
        self.cameraChanged.emit()

    def enterEvent(self, ev):
        """Como en Blender, las teclas de vista valen con el ratón encima, salvo si se está
        escribiendo en el código o en un campo (no se les quita el foco)."""
        focused = QApplication.focusWidget()
        if not isinstance(focused, (QPlainTextEdit, QTextEdit, QLineEdit, QAbstractSpinBox)):
            self.setFocus()
        super().enterEvent(ev)

    def keyPressEvent(self, ev):
        key = ev.key()
        name = "home" if key == Qt.Key.Key_Home else (chr(key) if 0x20 <= key < 0x7F else "")
        if name in VIEW_KEYS:
            self.viewKey.emit(name, bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier))
            ev.accept()
            return
        super().keyPressEvent(ev)

    def mousePressEvent(self, ev):
        self._press = ev.position()
        if ev.button() == Qt.MouseButton.LeftButton and self.gizmo_origin is not None:
            pos = ev.position()
            cam, d = self.ray(pos.x(), pos.y())
            axes = [
                ("X", np.array([1.0, 0.0, 0.0])),
                ("Y", np.array([0.0, 1.0, 0.0])),
                ("Z", np.array([0.0, 0.0, 1.0])),
            ]

            best_axis = None
            best_dist = 1e9
            best_s = 0.0

            for name, u in axes:
                w0 = self.gizmo_origin - cam
                b = float(np.dot(u, d))
                denom = 1.0 - b * b
                if abs(denom) > 1e-6:
                    e = float(np.dot(w0, d))
                    d_dot = float(np.dot(w0, u))
                    s = (b * e - d_dot) / denom
                    s_clamped = max(0.0, min(self.gizmo_len, s))
                    t = max(0.0, float(np.dot(self.gizmo_origin + s_clamped * u - cam, d)))
                    pt_ray = cam + t * d
                    pt_seg = self.gizmo_origin + s_clamped * u
                    dist = float(np.linalg.norm(pt_ray - pt_seg))
                    # Tolerancia de unos píxeles en pantalla (a la distancia de ese punto):
                    # una tolerancia en mm se comía los clics alrededor de la pieza.
                    hit_threshold = GIZMO_PICK_PIXELS * self.pixel_angle() * max(t, 1e-6)
                    if dist < hit_threshold and dist < best_dist:
                        best_dist = dist
                        best_axis = name
                        best_s = s

            if best_axis is not None:
                self._active_axis = best_axis
                self._drag_start_s = best_s
                # El gizmo se mueve con la pieza mientras se arrastra: el desplazamiento se mide
                # siempre desde donde estaba al pulsar, o la pieza oscilaría.
                self._drag_origin = self.gizmo_origin.copy()
                self.gizmoStarted.emit()
                return

        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._active_axis is not None and self._drag_origin is not None:
            pos = ev.position()
            cam, d = self.ray(pos.x(), pos.y())
            u = np.array([1.0, 0.0, 0.0] if self._active_axis == "X" else
                         [0.0, 1.0, 0.0] if self._active_axis == "Y" else
                         [0.0, 0.0, 1.0])
            w0 = self._drag_origin - cam
            b = float(np.dot(u, d))
            denom = 1.0 - b * b
            if abs(denom) > 1e-6:
                e = float(np.dot(w0, d))
                d_dot = float(np.dot(w0, u))
                s = (b * e - d_dot) / denom
                total_s = s - self._drag_start_s
                dx = total_s if self._active_axis == "X" else 0.0
                dy = total_s if self._active_axis == "Y" else 0.0
                dz = total_s if self._active_axis == "Z" else 0.0
                self.gizmoMoved.emit(dx, dy, dz)
            return
        if ev.buttons() == Qt.MouseButton.NoButton:
            self.hovered.emit(ev.position().x(), ev.position().y())
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._active_axis is not None:
            self._active_axis = None
            self._drag_origin = None
            press, self._press = self._press, None
            self.gizmoFinished.emit()
            # Pulsar un eje sin arrastrar es un clic normal (seleccionar o, en el vacío, deseleccionar).
            if press is not None:
                d = ev.position() - press
                if abs(d.x()) + abs(d.y()) < 5:
                    ctrl = bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier)
                    self.clicked.emit(ev.position().x(), ev.position().y(), ctrl)
            return
        super().mouseReleaseEvent(ev)
        if self._press is None or ev.button() != Qt.MouseButton.LeftButton:
            return
        d = ev.position() - self._press
        self._press = None
        if abs(d.x()) + abs(d.y()) < 5:
            ctrl = bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier)
            self.clicked.emit(ev.position().x(), ev.position().y(), ctrl)

    def pixel_angle(self) -> float:
        """Ángulo (radianes) que abarca un píxel en el centro de la vista."""
        return 2 * math.tan(math.radians(self.opts["fov"]) / 2) / max(self.width(), 1)

    def ray(self, x: float, y: float):
        """Origen y dirección del rayo que sale de la cámara por el píxel (x, y)."""
        o = self.opts
        c = o["center"]
        center = np.array([c.x(), c.y(), c.z()], dtype=float)
        dist = float(o["distance"])
        elev, azim = math.radians(o["elevation"]), math.radians(o["azimuth"])
        cam = center + dist * np.array([math.cos(elev) * math.cos(azim),
                                        math.cos(elev) * math.sin(azim), math.sin(elev)])
        forward = center - cam
        forward /= np.linalg.norm(forward)
        right = np.cross(forward, [0.0, 0.0, 1.0])
        if np.linalg.norm(right) < 1e-9:  # mirando justo desde arriba
            right = np.array([-math.sin(azim), math.cos(azim), 0.0])
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        w, h = max(self.width(), 1), max(self.height(), 1)
        tx = math.tan(math.radians(o["fov"]) / 2)
        ty = tx * h / w
        nx, ny = 2 * x / w - 1, 1 - 2 * y / h
        direction = forward + nx * tx * right + ny * ty * up
        return cam, direction / np.linalg.norm(direction)


class Viewer3D(QWidget):
    renderRequested = Signal()
    picked = Signal(int, bool)        # id (o -1 si es el vacío), Ctrl
    measured = Signal(str)
    gizmoStarted = Signal()
    gizmoMoved = Signal(float, float, float)
    gizmoFinished = Signal()
    edgeFinish = Signal(str, float, list)  # "round" | "chamfer" | "none", valor, [(id, clave)]
    gridToggled = Signal(bool)             # rejilla del suelo mostrada u ocultada (tecla G)
    smoothToggled = Signal(bool)           # sombreado suave Shade Smooth (tecla S / Shift+S)
    treeOverlayToggled = Signal(bool)      # el usuario pide (o quita) el árbol sobre el visor
    displayModeChanged = Signal(str)       # modo de visualización (clave de geo.DISPLAY_MODES)
    barPositionChanged = Signal(str)       # posición de la barra ("top" | "bottom")

    def minimumSizeHint(self) -> QSize:
        return QSize(280, 200)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("viewport")
        self.real: Optional[np.ndarray] = None
        self.ghosts: dict = {}
        self._picker: Optional[geo.Picker] = None
        self._fitted = False
        self.measuring = False
        self._points: list = []
        self.edge_mode = False
        self._edge_targets: list = []     # (id, clave, polilínea) de geo.pickable_edges
        self.selected_edges: list = []    # [(id, clave)]
        self._hover_edge: Optional[int] = None
        self._occluders = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.main_layout = layout
        self._bar_position = "top"

        bar = QWidget()
        bar.setObjectName("viewBar")
        bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        bar.customContextMenuRequested.connect(self._bar_context_menu)
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)
        self.title = QLabel(tr("Vista 3D"))
        self.title.setObjectName("viewTitle")
        row.addWidget(self.title)

        self.pos_btn = QPushButton("▼")
        self.pos_btn.setObjectName("viewButton")
        self.pos_btn.setFixedSize(24, 24)
        self.pos_btn.setToolTip(tr("Mover barra abajo"))
        self.pos_btn.clicked.connect(self.toggle_bar_position)
        row.addWidget(self.pos_btn)
        self.view_buttons: dict[str, QPushButton] = {}
        for name in VIEWS:
            b = QPushButton(tr(name))
            b.setObjectName("viewButton")
            b.setCheckable(True)             # marcado: la vista en la que está la cámara
            self.view_buttons[VIEWS[name]] = b
            b.setToolTip(tr("Tecla {key} (teclado numérico o fila de números)").format(key=SHORTCUT_OF[name]))
            b.clicked.connect(lambda _=False, n=name: self.set_view(n))
            row.addWidget(b)
        self.fit_btn = QPushButton(tr("Ajustar"))
        self.fit_btn.setObjectName("viewButton")
        self.fit_btn.setToolTip(tr("Tecla Inicio: todo · Tecla . (punto): la selección"))
        self.fit_btn.clicked.connect(lambda: self.fit())   # clicked pasa un bool que fit() tomaría por la caja
        row.addWidget(self.fit_btn)
        self.measure_btn = QPushButton(tr("Medir"))
        self.measure_btn.setObjectName("viewButton")
        self.measure_btn.setCheckable(True)
        self.measure_btn.toggled.connect(self.set_measuring)
        row.addWidget(self.measure_btn)
        self.edge_btn = QPushButton(tr("Elegir aristas"))
        self.edge_btn.setObjectName("viewButton")
        self.edge_btn.setCheckable(True)
        self.edge_btn.setToolTip(tr("Elige aristas de cube y cylinder para redondearlas o achaflanarlas"))
        self.edge_btn.toggled.connect(self.set_edge_mode)
        row.addWidget(self.edge_btn)
        self.tree_btn = QPushButton(tr("Árbol"))
        self.tree_btn.setObjectName("viewButton")
        self.tree_btn.setCheckable(True)
        self.tree_btn.setToolTip(tr("Muestra el árbol del modelo encima del visor, como en Fusion"))
        self.tree_btn.toggled.connect(self.treeOverlayToggled)
        row.addWidget(self.tree_btn)
        self.ruler_btn = QPushButton(tr("Regla"))
        self.ruler_btn.setObjectName("viewButton")
        self.ruler_btn.setCheckable(True)
        self.ruler_btn.setToolTip(tr("Regla graduada en los ejes, como la de OpenSCAD (tecla R)"))
        self.ruler_btn.toggled.connect(self.set_ruler)
        row.addWidget(self.ruler_btn)
        self.edges_check = QCheckBox(tr("Aristas"))
        self.edges_check.setObjectName("viewCheck")
        self.edges_check.setChecked(True)
        self.edges_check.toggled.connect(lambda _on: self._show_model())
        row.addWidget(self.edges_check)
        self.smooth_shading = True
        self.smooth_check = QCheckBox(tr("Suavizado"))
        self.smooth_check.setObjectName("viewCheck")
        self.smooth_check.setChecked(True)
        self.smooth_check.setToolTip(tr("Sombreado suave de caras curvas estilo Shade Smooth (tecla S o Shift+S)"))
        self.smooth_check.toggled.connect(self.set_smooth_shading)
        row.addWidget(self.smooth_check)
        self.display_mode = "shaded"
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("viewCombo")
        for key, label in geo.DISPLAY_MODES:
            self.mode_combo.addItem(tr(label), key)
        self.mode_combo.setToolTip(tr("Modo de visualización de la malla (tecla Z: el siguiente)"))
        self.mode_combo.currentIndexChanged.connect(
            lambda i: self.set_display_mode(self.mode_combo.itemData(i)))
        row.addWidget(self.mode_combo)
        self.explosion_label = QLabel(tr("Explosión:"))
        row.addWidget(self.explosion_label)
        self.explosion_slider = QSlider(Qt.Orientation.Horizontal)
        self.explosion_slider.setRange(0, 100)
        self.explosion_slider.setValue(0)
        self.explosion_slider.setFixedWidth(80)
        self.explosion_slider.setToolTip(tr("Separa las piezas para visualización explosionada"))
        self.explosion_slider.valueChanged.connect(self.set_explosion)
        row.addWidget(self.explosion_slider)
        row.addStretch(1)
        self.auto = QCheckBox(tr("Actualizar sola"))
        self.auto.setObjectName("viewCheck")
        self.auto.setChecked(True)
        row.addWidget(self.auto)
        self.status = QLabel("")
        self.status.setObjectName("viewStatus")
        row.addWidget(self.status)

        bar_scroll = QScrollArea()
        bar_scroll.setObjectName("viewBarScroll")
        bar_scroll.setWidgetResizable(True)
        bar_scroll.setWidget(bar)
        bar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        bar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        bar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        bar_scroll.setFixedHeight(38)
        self.bar_scroll = bar_scroll
        layout.addWidget(bar_scroll)

        self.view = _GLView()
        self.view.setBackgroundColor(pg.mkColor("#262B33"))
        self.light_background = False            # lo cambia set_color_scheme()
        self.explode_factor = 2.0                # Preferencias › Factor máx. vista explosionada
        self.view.opts["fov"] = PERSPECTIVE_FOV
        self.view.setCameraPosition(distance=120, elevation=30, azimuth=-55)
        self.view.cameraChanged.connect(self._update_view_name)
        self.view.cameraChanged.connect(self._update_ruler)
        layout.addWidget(self.view, 1)

        self.grid = gl.GLGridItem()
        self.grid.setSize(200, 200)
        self.grid.setSpacing(10, 10)
        self.grid.setColor((255, 255, 255, 28))
        self.view.addItem(self.grid)
        self.axes = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [20, 0, 0], [0, 0, 0], [0, 20, 0], [0, 0, 0], [0, 0, 20]], dtype=np.float32),
            color=np.array([[0.9, 0.33, 0.29, 1]] * 2 + [[0.25, 0.73, 0.31, 1]] * 2 + [[0.35, 0.65, 1, 1]] * 2,
                           dtype=np.float32),
            mode="lines", width=2, antialias=True)
        self.view.addItem(self.axes)
        # Regla: por eje, el lado positivo (continuo) y el negativo (punteado y más tenue).
        self.ruler_on = False
        self._ruler_key = None
        self.ruler_pos = [_line_item(_rgba(c), 1.5) for c in AXIS_COLORS]
        self.ruler_neg = [_line_item(_rgba(c, 0.55), 1.0, "translucent") for c in AXIS_COLORS]
        self.ruler_labels: list = []           # GLTextItem reutilizados (no existen en pyqtgraph antiguo)
        self._label_points: list = []
        self._ray_index = None                   # geo.RayIndex de la malla mostrada
        # Los textos de pyqtgraph se pintan encima de todo: los que quedan detrás de la pieza se
        # ocultan (como las marcas, que sí respetan la profundidad). Se mira al parar de girar.
        self._label_timer = QTimer(self)
        self._label_timer.setSingleShot(True)
        self._label_timer.setInterval(120)
        self._label_timer.timeout.connect(self._hide_covered_labels)
        self.view.cameraChanged.connect(self._label_timer.start)
        for item in self.ruler_pos + self.ruler_neg:
            self.view.addItem(item)

        self.model = _mesh_item(geo.DEFAULT_COLOR, MODEL_SOLID, 0)
        self.approx = _mesh_item(geo.DEFAULT_COLOR, MODEL_SOLID, 0)
        self.wire = _line_item(WIRE_ON_DARK, 1.0, "translucent", 1)   # vista alámbrica / con malla
        self._wire_cache = (None, None)   # (triángulos, sus aristas): no se recalculan al girar
        self.colors: dict = {}
        self._face_colors = None  # colores que trae el .off de OpenSCAD
        self._owner = None        # pieza (id de nodo) de cada cara de la malla real
        self._model_cols = None   # color iluminado de cada cara de la malla real
        self.part_of: dict = {}
        self.subtracted: set = set()
        self._explosion = 0
        self._display_real = None
        self._display_ghosts: dict = {}
        self.edges = _line_item(EDGE_COLOR, 1.2, "translucent", 1)
        self.background = _mesh_item(BACKGROUND_COLOR, SEE_THROUGH, 5)
        self.hashed = _mesh_item(HASH_COLOR, SEE_THROUGH, 6)
        self.highlight = _mesh_item(SELECT_COLOR, SEE_THROUGH, 10)
        self.highlight_edges = _line_item(SELECT_EDGE, 2.0, SEE_THROUGH, 11)
        self.measure_line = _line_item(MEASURE_COLOR, 2.5, SEE_THROUGH, 20)
        self.measure_dots = gl.GLScatterPlotItem(pos=np.zeros((1, 3)), size=9, color=MEASURE_COLOR,
                                                 pxMode=True, glOptions=SEE_THROUGH)
        self.measure_dots.setDepthValue(21)
        self.measure_dots.setVisible(False)
        self.edge_picked_lines = _line_item(EDGE_PICKED_COLOR, 4.0, SEE_THROUGH, 24)
        self.edge_hover_line = _line_item(EDGE_HOVER_COLOR, 3.0, SEE_THROUGH, 25)

        self.gizmo_lines = gl.GLLinePlotItem(
            pos=np.zeros((6, 3), dtype=np.float32),
            color=np.array([[1.0, 0.2, 0.2, 1.0]] * 2 +
                           [[0.2, 0.9, 0.2, 1.0]] * 2 +
                           [[0.2, 0.5, 1.0, 1.0]] * 2, dtype=np.float32),
            mode="lines", width=3.5, antialias=True, glOptions=SEE_THROUGH)
        self.gizmo_lines.setDepthValue(30)
        self.gizmo_lines.setVisible(False)

        self.gizmo_tips = _mesh_item((1.0, 1.0, 1.0, 1.0), ON_TOP_SOLID, 31)   # puntas de flecha (conos)

        for item in (self.model, self.approx, self.wire, self.edges, self.background, self.hashed, self.highlight,
                     self.highlight_edges, self.measure_line, self.measure_dots,
                     self.edge_picked_lines, self.edge_hover_line, self.gizmo_lines, self.gizmo_tips):
            self.view.addItem(item)

        self.message = QLabel("", self.view)
        self.message.setObjectName("viewMessage")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        self.view_name = QLabel("", self.view)   # como en Blender: «Frontal · Ortográfica»
        self.view_name.setObjectName("viewName")
        self.selection = QLabel("", self.view)
        self.selection.setObjectName("selectionBadge")
        self.selection.move(12, 12)
        self.selection.hide()
        self.measure_label = QLabel("", self.view)
        self.measure_label.setObjectName("measureBadge")
        self.measure_label.hide()
        self.setup = QPushButton(tr("Elegir openscad…"), self.view)
        self.setup.setObjectName("primary")
        self.setup.hide()
        self.hint = QLabel(tr("Arrastrar: girar · Rueda: zoom · Botón central o Ctrl+arrastrar: mover · "
                              "Clic: seleccionar · Ctrl+clic: añadir") + "\n"
                           + tr("1 frontal · 3 derecha · 7 superior (Ctrl: la opuesta) · 0 isométrica · "
                                "9 dar la vuelta · 2 4 6 8 girar · 5 perspectiva/ortográfica · . encuadrar")
                           + " · " + tr("R regla") + " · " + tr("G rejilla"),
                           self.view)
        self.triad = _AxisTriad(self.view)
        self.hint.setObjectName("viewHint")
        self._build_edge_panel()
        self._build_tree_overlay()
        self.props_overlay = QFrame(self.view)   # propiedades de la selección, a la derecha
        self.props_overlay.setObjectName("propsOverlay")
        self.props_overlay_layout = QVBoxLayout(self.props_overlay)
        self.props_overlay_layout.setContentsMargins(1, 1, 1, 1)
        self.props_overlay.hide()

        self.view.clicked.connect(self._on_click)
        self.view.hovered.connect(self._on_hover)
        self.view.viewKey.connect(self.key_command)
        self.orthographic = False
        self._highlight_tris = None
        self.view.gizmoStarted.connect(self.gizmoStarted)
        self.view.gizmoMoved.connect(self.gizmoMoved)
        self.view.gizmoFinished.connect(self.gizmoFinished)
        self._update_view_name()
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(450)
        self._render_timer.timeout.connect(self.renderRequested.emit)

    # ------------------------------------------------------------- disposición
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._place_overlays)

    def _place_overlays(self):
        w, h = self.view.width(), self.view.height()
        self.message.setGeometry(40, h // 2 - 60, max(100, w - 80), 80)
        self.hint.adjustSize()
        self.hint.move(12, h - self.hint.height() - 10)
        self.triad.move(6, h - self.hint.height() - 14 - self.triad.height())
        self.view_name.adjustSize()
        self.view_name.move(max(12, w - self.view_name.width() - 14), 12)
        self.measure_label.adjustSize()
        self.measure_label.move(max(12, w - self.measure_label.width() - 12), 18 + self.view_name.height())
        self.setup.adjustSize()
        self.setup.move((w - self.setup.width()) // 2, h // 2 + 30)
        self.edge_panel.adjustSize()
        self.edge_panel.move(max(12, w - self.edge_panel.width() - 12),
                             max(12, h - self.edge_panel.height() - 12))
        # Propiedades flotando a la derecha, debajo del nombre de la vista (y de la medida).
        if self.props_overlay.isVisible():
            top = 18 + self.view_name.height()
            if self.measure_label.isVisible():
                top += self.measure_label.height() + 6
            bottom = h - 12 - (self.edge_panel.height() + 8 if self.edge_panel.isVisible() else 0)
            self.props_overlay.setGeometry(max(12, w - PROPS_OVERLAY_WIDTH - 12), top,
                                           PROPS_OVERLAY_WIDTH, max(120, bottom - top))
        # Árbol flotante arriba a la izquierda; la etiqueta de la selección pasa a su derecha.
        if self.tree_overlay.isVisible():
            collapsed = not self.tree_overlay_body.isVisible()
            height = self.tree_overlay_head.sizeHint().height() + 8 if collapsed else max(160, int(h * 0.62))
            self.tree_overlay.setGeometry(12, 12, TREE_OVERLAY_WIDTH, min(height, max(60, h - 24)))
            self.selection.move(12 + TREE_OVERLAY_WIDTH + 10, 12)
        else:
            self.selection.move(12, 12)

    # ------------------------------------------------------------- API usada por la ventana
    def request_render(self, now: bool = False) -> None:
        if now:
            self._render_timer.stop()
            self.renderRequested.emit()
        else:
            self._render_timer.start()

    def set_selection_text(self, text: str) -> None:
        self.selection.setText(text)
        self.selection.adjustSize()
        self.selection.setVisible(bool(text))

    def clear(self, message: str) -> None:
        self.ghosts = {}
        self.set_mesh(None)
        self.show_message(message)

    def reset_scene(self) -> None:
        """Documento nuevo: quita todo lo del anterior (malla calculada, selección, gizmo, medición,
        aristas elegidas) y vuelve a encuadrar cuando llegue el modelo nuevo."""
        self.real = None
        self._face_colors = None
        self._fitted = False
        self.set_highlight(None)
        self.set_gizmo(None)
        self.set_measuring(self.measuring)          # borra los puntos medidos
        self.selected_edges = []
        self._hover_edge = None
        self._draw_edges()
        self._paint_model()

    def show_message(self, message: str) -> None:
        self.message.setText(message)
        self.message.setVisible(bool(message))
        self._place_overlays()

    def show_setup_button(self, visible: bool) -> None:
        self.setup.setVisible(visible)
        self._place_overlays()

    def set_mesh(self, tris: Optional[np.ndarray], face_colors=None) -> None:
        """Malla final calculada por OpenSCAD (con sus colores por cara, si los trae)."""
        self.real = tris if tris is not None and len(tris) else None
        self._face_colors = face_colors if self.real is not None else None
        self._paint_model()
        if self.real is not None:
            self.show_message("")
            if not self._fitted:
                self.fit()
                self._fitted = True
            self._resize_grid()

    def _paint_model(self) -> None:
        """Calcula a qué pieza pertenece cada cara de la malla real y su color, y la muestra."""
        if self.real is None:
            self._owner, self._model_cols = None, None
        else:
            self._owner = geo.assign_faces(self.real, self.ghosts) if self.ghosts else None
            if self._face_colors is not None:
                self._model_cols = geo.colored(self.real, None, self.colors, self._face_colors, smooth=self.smooth_shading)
            else:
                self._model_cols = geo.colored(self.real, self._owner, self.colors, smooth=self.smooth_shading)
        self._show_model()

    def set_smooth_shading(self, on: bool) -> None:
        on = bool(on)
        if on == self.smooth_shading:
            return
        self.smooth_shading = on
        if self.smooth_check.isChecked() != on:
            self.smooth_check.blockSignals(True)
            self.smooth_check.setChecked(on)
            self.smooth_check.blockSignals(False)
        self._paint_model()
        self.view.update()
        self.smoothToggled.emit(on)

    def set_ghosts(self, ghosts: dict, colors=None, hashed=None, background=None,
                   part_of: Optional[dict] = None, subtracted: Optional[set] = None) -> None:
        """Mallas aproximadas por pieza (para colorear y seleccionar) y las de los modificadores # y %.

        ``part_of`` dice a qué pieza del montaje pertenece cada nodo y ``subtracted`` qué nodos se
        restan; los dos se usan en la vista explosionada.
        """
        self.ghosts = ghosts
        self.colors = colors or {}
        self.part_of = part_of or {}
        self.subtracted = subtracted or set()
        _set_mesh(self.hashed, hashed)
        _set_mesh(self.background, background)
        self._paint_model()  # el reparto de caras y los colores dependen de las mallas aproximadas
        if self.real is None and not self._fitted and ghosts:
            self.fit()

    def set_explosion(self, percent: int) -> None:
        self._explosion = percent
        self._show_model()
        if self.edge_mode:
            self._hover_edge = None
            self._draw_edges()

    def _show_model(self) -> None:
        """Dibuja la malla real (o la aproximada si no hay) aplicando la explosión actual."""
        amount = self._explosion / 100.0 * 0.3 * self.explode_factor   # 2 (por defecto): 0.6
        ghosts = self.ghosts
        if self.real is not None:
            tris = self.real
            if amount > 0 and self._owner is not None:
                parts = np.array([self.part_of.get(int(o), -1) for o in self._owner])
                offsets = geo.explosion_offsets(tris, parts, amount)
                tris = geo.apply_offsets(tris, parts, offsets)
                ghosts = self._move_ghosts(offsets)
            self._draw_styled(self.model, tris, self._model_cols, outline=True)
            self.approx.setVisible(False)
        else:
            self.model.setVisible(False)
            self.edges.setVisible(False)
            self.wire.setVisible(False)
            visible = {k: v for k, v in self.ghosts.items() if k not in self.subtracted} if amount > 0 else self.ghosts
            if visible:
                tris, cols = geo.ghost_colors(visible, self.colors, smooth=self.smooth_shading)
                if amount > 0:
                    parts = np.concatenate([np.full(len(t), self.part_of.get(k, -1)) for k, t in visible.items()])
                    offsets = geo.explosion_offsets(tris, parts, amount)
                    tris = geo.apply_offsets(tris, parts, offsets)
                    ghosts = self._move_ghosts(offsets)
                self._draw_styled(self.approx, tris, cols, outline=False)
            else:
                self.approx.setVisible(False)
        self._display_ghosts = ghosts
        self._display_real = tris if self.real is not None else None
        self._picker = None
        self._occluders = None
        self._ray_index = None
        if hasattr(self, "_label_timer"):
            self._label_timer.start()

    def _move_ghosts(self, offsets: dict) -> dict:
        """Aplica a las mallas aproximadas el mismo desplazamiento que a su pieza (para seleccionar)."""
        return {k: (t + offsets[self.part_of[k]] if self.part_of.get(k) in offsets else t)
                for k, t in self.ghosts.items()}

    # ------------------------------------------------------------- modos de visualización
    def set_display_mode(self, mode: str) -> None:
        """Sombreado, con malla, alámbrica, rayos X o sin líneas ocultas (geo.DISPLAY_MODES)."""
        keys = [k for k, _ in geo.DISPLAY_MODES]
        if mode not in keys:
            mode = "shaded"
        changed = mode != self.display_mode
        self.display_mode = mode
        if self.mode_combo.currentIndex() != keys.index(mode):
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(keys.index(mode))
            self.mode_combo.blockSignals(False)
        self._show_model()
        self.view.update()
        if changed:
            self.displayModeChanged.emit(mode)

    def _wire_of(self, tris: np.ndarray) -> np.ndarray:
        cached, segs = self._wire_cache
        if cached is not tris:
            segs = geo.mesh_edges(tris)
            self._wire_cache = (tris, segs)
        return segs

    def _draw_styled(self, item, tris: np.ndarray, cols, outline: bool) -> None:
        """Dibuja una malla según el modo de visualización. ``outline``: también los contornos
        (la malla real; la aproximada no los lleva)."""
        style = geo.display_style(self.display_mode)
        if not style["faces"]:
            item.setVisible(False)
        else:
            if style["flat"]:
                r, g, b = self.view.opts["bgcolor"][:3]          # del color del fondo: solo se ven las líneas
                cols = np.tile(np.array([r, g, b, 1.0]), (len(tris), 1))
            elif style["xray"]:
                if cols is None:
                    base = np.tile(np.array(item.base_color, dtype=np.float64), (len(tris), 1))
                    cols = geo.shade(geo.face_normals(tris), base)
                cols = geo.xray_colors(cols)
            item.setGLOptions(SEE_THROUGH if style["xray"] else MODEL_SOLID)
            _set_mesh(item, tris, cols)
        if style["wire"]:
            on_faces = style["faces"]
            color = WIRE_OVER_FACES if on_faces else (WIRE_ON_LIGHT if self.light_background else WIRE_ON_DARK)
            self.wire.setData(color=color)
            _set_lines(self.wire, self._wire_of(tris))
        else:
            self.wire.setVisible(False)
        if outline:
            if style["outline"] or (self.edges_check.isChecked() and style["faces"]):
                dark = style["flat"] and not self.light_background
                self.edges.setData(color=EDGE_ON_DARK if dark else EDGE_COLOR)
                _set_lines(self.edges, geo.feature_edges(tris))
            else:
                self.edges.setVisible(False)

    def set_highlight(self, tris: Optional[np.ndarray]) -> None:
        self._highlight_tris = tris if tris is not None and len(tris) else None
        _set_mesh(self.highlight, tris)
        _set_lines(self.highlight_edges, geo.feature_edges(tris) if tris is not None and len(tris) else None)

    def set_gizmo(self, center: Optional[np.ndarray], length: float = 25.0) -> None:
        if center is None:
            self.view.gizmo_origin = None
            self.gizmo_lines.setVisible(False)
            self.gizmo_tips.setVisible(False)
            return

        c = np.asarray(center, dtype=np.float32)
        L = float(length)
        self.view.gizmo_origin = np.asarray(center, dtype=float)
        self.view.gizmo_len = L

        # Cada eje: una línea hasta la base de la punta y un cono (la flecha) que acaba en c + L.
        head = L * GIZMO_HEAD_LENGTH
        axes = np.eye(3, dtype=np.float32)
        lines_pos = np.array([p for e in axes for p in (c, c + e * (L - head))], dtype=np.float32)
        self.gizmo_lines.setData(pos=lines_pos)
        self.gizmo_lines.setVisible(True)

        cones, colors = [], []
        for e, color in zip(axes, GIZMO_COLORS):
            cone = geo.arrow_cone(c + e * L, e, head, L * GIZMO_HEAD_RADIUS)
            cones.append(cone)
            colors.append(np.tile(color, (len(cone), 1)))
        tris = np.concatenate(cones)
        _set_mesh(self.gizmo_tips, tris, geo.shade(geo.face_normals(tris), np.concatenate(colors)))

    # ------------------------------------------------------------- cámara
    def _scene_box(self):
        if self.real is not None:
            return geo.bbox(self.real)
        if self.ghosts:
            return geo.bbox(np.concatenate(list(self.ghosts.values())))
        return None

    def fit(self, box=None) -> None:
        """Encuadra la caja indicada o, sin ella, todo el modelo."""
        box = box if box is not None and not isinstance(box, bool) else self._scene_box()
        if box is None:
            return
        lo, hi = box
        center = (lo + hi) / 2
        size = float(np.linalg.norm(hi - lo)) or 10.0
        dist = size / 2 / math.tan(math.radians(self.view.opts["fov"]) / 2) * 1.25
        self.view.setCameraPosition(pos=pg.Vector(*center), distance=dist)

    def set_view(self, name: str) -> None:
        """Vista de un botón de la barra (por su texto en español)."""
        self.set_camera(VIEWS[name])

    def set_camera(self, key: str) -> None:
        elev, azim = CAMERAS[key]
        self.view.setCameraPosition(elevation=elev, azimuth=azim)
        self.fit()

    def key_command(self, key: str, ctrl: bool = False) -> None:
        """Atajos de vista al estilo de Blender (ver VIEW_KEYS)."""
        action = VIEW_KEYS[key][1 if ctrl else 0]
        o = self.view.opts
        if action in CAMERAS:
            self.set_camera(action)
        elif action == "opposite":  # la misma dirección, desde el otro lado
            self.view.setCameraPosition(elevation=-o["elevation"], azimuth=(o["azimuth"] + 180.0) % 360.0)
        elif action.startswith("orbit_"):
            d_elev = {"orbit_up": ORBIT_STEP, "orbit_down": -ORBIT_STEP}.get(action, 0.0)
            d_azim = {"orbit_left": -ORBIT_STEP, "orbit_right": ORBIT_STEP}.get(action, 0.0)
            self.view.setCameraPosition(elevation=max(-90.0, min(90.0, o["elevation"] + d_elev)),
                                        azimuth=(o["azimuth"] + d_azim) % 360.0)
        elif action == "projection":
            self.set_orthographic(not self.orthographic)
        elif action == "frame_selected":
            self.fit(geo.bbox(self._highlight_tris) if self._highlight_tris is not None else None)
        elif action == "frame_all":
            self.fit()
        elif action == "ruler":
            self.ruler_btn.toggle()
        elif action == "grid":
            self.set_grid(not self.grid.visible())
        elif action == "display_next":
            self.set_display_mode(geo.next_display_mode(self.display_mode))
        elif action == "smooth":
            self.set_smooth_shading(not self.smooth_shading)

    # ------------------------------------------------------------- rejilla
    def set_render_delay(self, ms: int) -> None:
        """Espera tras el último cambio antes de pedir la malla a OpenSCAD (Preferencias)."""
        self._render_timer.setInterval(max(50, int(ms)))

    def set_color_scheme(self, scheme) -> None:
        """Esquema de color (Preferencias): fondo, color de las piezas sin color() y, si el fondo es
        claro, textos y rejilla oscuros para que se sigan viendo."""
        from .style import VIEWER_ON_LIGHT_STYLES
        self.color_scheme = scheme
        self.light_background = scheme.light
        self.view.setBackgroundColor(pg.mkColor(scheme.background))
        geo.set_default_color(scheme.rgba("face"))
        for item in (self.model, self.approx):
            item.base_color = geo.DEFAULT_COLOR
        self.grid.setColor((0, 0, 0, 45) if scheme.light else (255, 255, 255, 28))
        self.view.setStyleSheet(VIEWER_ON_LIGHT_STYLES if scheme.light else "")
        self._paint_model()
        self.view.update()

    def set_grid(self, on: bool) -> None:
        """Muestra u oculta la rejilla del suelo (menú Ver › Rejilla o tecla G)."""
        on = bool(on)
        if on != self.grid.visible():
            self.grid.setVisible(on)
            self.gridToggled.emit(on)

    # ------------------------------------------------------------- regla
    def set_ruler(self, on: bool) -> None:
        """Muestra la regla graduada de los ejes (sustituye a los ejes cortos del origen)."""
        self.ruler_on = bool(on)
        if self.ruler_btn.isChecked() != self.ruler_on:
            self.ruler_btn.setChecked(self.ruler_on)
        self.axes.setVisible(not self.ruler_on)
        self._ruler_key = None
        self._update_ruler()

    def _update_ruler(self) -> None:
        """Rehace la regla si el zoom pide otro paso (los números siempre «redondos»)."""
        if not hasattr(self, "ruler_pos"):
            return
        if not self.ruler_on:
            for item in self.ruler_pos + self.ruler_neg + self.ruler_labels:
                item.setVisible(False)
            return
        o = self.view.opts
        span = 2 * o["distance"] * math.tan(math.radians(o["fov"]) / 2)   # ancho visible, en mm
        data = geo.ruler(span)
        key = (data["major"], data["extent"])
        if key == self._ruler_key:
            return
        self._ruler_key = key
        for axis in range(3):
            _set_lines(self.ruler_pos[axis], data["pos"][axis])
            _set_lines(self.ruler_neg[axis], data["neg"][axis])
        if not hasattr(gl, "GLTextItem"):
            return
        while len(self.ruler_labels) < len(data["labels"]):
            item = gl.GLTextItem()
            self.view.addItem(item)
            self.ruler_labels.append(item)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSizeF(8)
        for item, (axis, point, text, negative) in zip(self.ruler_labels, data["labels"]):
            color = QColor(AXIS_COLORS[axis])
            color.setAlphaF(0.6 if negative else 0.95)
            item.setData(pos=np.asarray(point, dtype=np.float32), text=text, color=color, font=font)
            item.setVisible(True)
        for item in self.ruler_labels[len(data["labels"]):]:
            item.setVisible(False)
        self._label_points = [np.asarray(point, dtype=np.float64) for _a, point, _t, _n in data["labels"]]
        self._hide_covered_labels()

    def _hide_covered_labels(self) -> None:
        """Oculta los números de la regla que la pieza tapa desde la cámara actual."""
        if not self.ruler_on or not self._label_points:
            return
        if self._ray_index is None:               # se rehace solo cuando cambia la malla
            picker = self._get_picker()
            self._ray_index = geo.RayIndex(picker.real if picker.real is not None else picker.ghost_tris)
        cam = self.view.cameraPosition()
        origin = np.array([cam.x(), cam.y(), cam.z()], dtype=np.float64)
        for item, point in zip(self.ruler_labels, self._label_points):
            item.setVisible(not self._ray_index.blocked(origin, point))

    def ruler_texts(self) -> list:
        """Números visibles de la regla (para las pruebas)."""
        return [item.text for item in self.ruler_labels if item.visible()]

    def current_camera(self) -> str:
        """Cámara de CAMERAS en la que está la vista, o "" si se ha girado a mano."""
        elev, azim = self.view.opts["elevation"], self.view.opts["azimuth"]
        for key, (e, a) in CAMERAS.items():
            if abs(elev - e) < 0.5 and abs((azim - a + 180.0) % 360.0 - 180.0) < 0.5:
                return key
        return ""

    def retranslate_ui(self) -> None:
        """Vuelve a escribir los textos de la barra del visor en el idioma activo."""
        self.title.setText(tr("Vista 3D"))
        for name, cam in VIEWS.items():
            b = self.view_buttons[cam]
            b.setText(tr(name))
            b.setToolTip(tr("Tecla {key} (teclado numérico o fila de números)").format(key=SHORTCUT_OF[name]))
        self.fit_btn.setText(tr("Ajustar"))
        self.fit_btn.setToolTip(tr("Tecla Inicio: todo · Tecla . (punto): la selección"))
        self.measure_btn.setText(tr("Medir"))
        self.edge_btn.setText(tr("Elegir aristas"))
        self.edge_btn.setToolTip(tr("Elige aristas de cube y cylinder para redondearlas o achaflanarlas"))
        self.tree_btn.setText(tr("Árbol"))
        self.tree_btn.setToolTip(tr("Muestra el árbol del modelo encima del visor, como en Fusion"))
        self.ruler_btn.setText(tr("Regla"))
        self.ruler_btn.setToolTip(tr("Regla graduada en los ejes, como la de OpenSCAD (tecla R)"))
        self.edges_check.setText(tr("Aristas"))
        for i, (_, label) in enumerate(geo.DISPLAY_MODES):
            self.mode_combo.setItemText(i, tr(label))
        self.mode_combo.setToolTip(tr("Modo de visualización de la malla (tecla Z: el siguiente)"))
        self.explosion_label.setText(tr("Explosión:"))
        self.explosion_slider.setToolTip(tr("Separa las piezas para visualización explosionada"))
        self.auto.setText(tr("Actualizar sola"))
        if hasattr(self, "pos_btn"):
            self.pos_btn.setToolTip(tr("Mover barra arriba") if getattr(self, "_bar_position", "top") == "bottom" else tr("Mover barra abajo"))
        self._update_view_name()

    def toggle_bar_position(self) -> None:
        """Conmuta la barra de herramientas entre la parte superior e inferior del visor."""
        new_pos = "top" if getattr(self, "_bar_position", "top") == "bottom" else "bottom"
        self.set_bar_position(new_pos)

    def set_bar_position(self, pos: str) -> None:
        """Coloca la barra de herramientas arriba ('top') o abajo ('bottom') del visor."""
        pos = "bottom" if pos == "bottom" else "top"
        self._bar_position = pos
        self.main_layout.removeWidget(self.bar_scroll)
        self.main_layout.removeWidget(self.view)
        if pos == "bottom":
            self.main_layout.addWidget(self.view, 1)
            self.main_layout.addWidget(self.bar_scroll, 0)
            if hasattr(self, "pos_btn"):
                self.pos_btn.setText("▲")
                self.pos_btn.setToolTip(tr("Mover barra arriba"))
        else:
            self.main_layout.addWidget(self.bar_scroll, 0)
            self.main_layout.addWidget(self.view, 1)
            if hasattr(self, "pos_btn"):
                self.pos_btn.setText("▼")
                self.pos_btn.setToolTip(tr("Mover barra abajo"))
        self.barPositionChanged.emit(pos)
        QTimer.singleShot(0, self._place_overlays)

    def _bar_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        is_bottom = getattr(self, "_bar_position", "top") == "bottom"
        act = menu.addAction(tr("Mover barra arriba") if is_bottom else tr("Mover barra abajo"))
        act.triggered.connect(self.toggle_bar_position)
        menu.exec(self.bar_scroll.widget().mapToGlobal(pos))

    def _update_view_name(self) -> None:
        """Marca el botón de la vista actual y escribe su nombre en el visor."""
        if not hasattr(self, "tree_overlay"):     # aún construyendo el visor
            return
        key = self.current_camera()
        self.triad.set_angles(self.view.opts["elevation"], self.view.opts["azimuth"])
        for cam, b in self.view_buttons.items():
            b.setChecked(cam == key)
        name = tr(CAMERA_NAMES[key]) if key else tr("Libre")
        self.view_name.setText(f"{name} · {tr('Ortográfica') if self.orthographic else tr('Perspectiva')}")
        self._place_overlays()

    def set_orthographic(self, on: bool) -> None:
        """Proyección ortográfica imitada: ángulo de cámara casi nulo y la cámara más lejos, de modo
        que el modelo se ve del mismo tamaño. La selección con clic sigue funcionando igual."""
        if on == self.orthographic:
            return
        old, new = (PERSPECTIVE_FOV, ORTHO_FOV) if on else (ORTHO_FOV, PERSPECTIVE_FOV)
        scale = math.tan(math.radians(old) / 2) / math.tan(math.radians(new) / 2)
        self.view.opts["fov"] = new
        self.view.setCameraPosition(distance=self.view.opts["distance"] * scale)
        self.orthographic = on
        self.status.setText(tr("Ortográfica") if on else tr("Perspectiva"))
        self._update_view_name()

    def _resize_grid(self) -> None:
        box = self._scene_box()
        if box is None:
            return
        lo, hi = box
        span = float(max(hi[0] - lo[0], hi[1] - lo[1], 10.0))
        step = 10 ** math.floor(math.log10(span / 2)) if span > 20 else 1
        size = math.ceil(span * 2 / step) * step
        self.grid.setSpacing(step, step)
        self.grid.setSize(size, size)
        self.grid.resetTransform()
        self.grid.translate(round((lo[0] + hi[0]) / 2 / step) * step, round((lo[1] + hi[1]) / 2 / step) * step,
                            min(0.0, float(lo[2])))

    # ------------------------------------------------------------- selección y medición
    def _get_picker(self) -> geo.Picker:
        if self._picker is None:
            self._picker = geo.Picker(self._display_real, self._display_ghosts)
        return self._picker

    def _on_click(self, x: float, y: float, ctrl: bool) -> None:
        if self.edge_mode:
            self._click_edge(x, y, ctrl)
            return
        origin, direction = self.view.ray(x, y)
        nid, hit = self._get_picker().pick(origin, direction)
        if self.measuring:
            if hit is not None:
                self._add_measure_point(hit)
            return
        self.picked.emit(-1 if nid is None else nid, ctrl)

    # ------------------------------------------------------------- árbol sobre el visor
    def _build_tree_overlay(self) -> None:
        panel = QFrame(self.view)
        panel.setObjectName("treeOverlay")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(6, 4, 6, 6)
        lay.setSpacing(2)
        head = QWidget()
        row = QHBoxLayout(head)
        row.setContentsMargins(4, 0, 0, 0)
        title = QLabel(tr("MODELO"))
        title.setObjectName("sectionTitle")
        row.addWidget(title)
        row.addStretch(1)
        self.tree_overlay_fold = QPushButton("▾")
        self.tree_overlay_fold.setObjectName("overlayButton")
        self.tree_overlay_fold.setToolTip(tr("Plegar / desplegar"))
        self.tree_overlay_fold.clicked.connect(self._fold_tree_overlay)
        row.addWidget(self.tree_overlay_fold)
        close = QPushButton("×")
        close.setObjectName("overlayButton")
        close.setToolTip(tr("Devolver el árbol al panel Modelo"))
        close.clicked.connect(lambda: self.tree_btn.setChecked(False))
        row.addWidget(close)
        lay.addWidget(head)
        body = QWidget()
        self.tree_overlay_layout = QVBoxLayout(body)
        self.tree_overlay_layout.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(body, 1)
        panel.hide()
        self.tree_overlay = panel
        self.tree_overlay_head = head
        self.tree_overlay_body = body

    def show_props_overlay(self, content: Optional[QWidget]) -> None:
        """Pone (o quita, con None) el panel de propiedades flotando a la derecha del visor."""
        for _ in range(int(self.props_overlay_layout.count())):   # vaciar (count() fijo antes)
            self.props_overlay_layout.takeAt(0)
        if content is None:
            self.props_overlay.hide()
        else:
            self.props_overlay_layout.addWidget(content)
            content.show()

    def set_props_overlay_visible(self, on: bool) -> None:
        self.props_overlay.setVisible(bool(on) and int(self.props_overlay_layout.count()) > 0)
        self._place_overlays()

    def show_tree_overlay(self, content: Optional[QWidget]) -> None:
        """Pone ``content`` (el árbol de la ventana) en el panel flotante; con None lo esconde.

        El widget no se copia: la ventana lo cambia de sitio, así que selección, arrastrar y
        soltar y el menú contextual siguen siendo los mismos.
        """
        if content is not None:
            self.tree_overlay_layout.addWidget(content)
            self.tree_overlay_body.setVisible(True)
            self.tree_overlay_fold.setText("▾")
        self.tree_overlay.setVisible(content is not None)
        self.tree_btn.blockSignals(True)
        self.tree_btn.setChecked(content is not None)
        self.tree_btn.blockSignals(False)
        self._place_overlays()

    def _fold_tree_overlay(self) -> None:
        unfold = not self.tree_overlay_body.isVisible()
        self.tree_overlay_body.setVisible(unfold)
        self.tree_overlay_fold.setText("▾" if unfold else "▸")
        self._place_overlays()

    # ------------------------------------------------------------- aristas
    def _build_edge_panel(self) -> None:
        panel = QFrame(self.view)
        panel.setObjectName("edgePanel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)
        self.edge_info = QLabel("")
        self.edge_info.setObjectName("edgeInfo")
        lay.addWidget(self.edge_info)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Radio / distancia (mm):")))
        self.edge_value = QDoubleSpinBox()
        self.edge_value.setRange(0.01, 10000)
        self.edge_value.setDecimals(2)
        self.edge_value.setSingleStep(0.5)
        self.edge_value.setValue(2.0)
        row.addWidget(self.edge_value)
        lay.addLayout(row)
        buttons = QHBoxLayout()
        for text, mode in (("Redondear", "round"), ("Chaflán", "chamfer"), ("Quitar", "none")):
            b = QPushButton(tr(text))
            b.setObjectName("viewButton")
            b.clicked.connect(lambda _=False, m=mode: self._finish_edges(m))
            buttons.addWidget(b)
        lay.addLayout(buttons)
        panel.hide()
        self.edge_panel = panel

    def set_edge_targets(self, edges: list) -> None:
        """Aristas elegibles del modelo actual (de geo.pickable_edges). Se conservan las elegidas que sigan."""
        self._edge_targets = edges
        present = {(e[0], e[1]) for e in edges}
        self.selected_edges = [e for e in self.selected_edges if e in present]
        self._hover_edge = None
        self._draw_edges()

    def set_edge_mode(self, on: bool) -> None:
        self.edge_mode = on
        if on and self.measure_btn.isChecked():
            self.measure_btn.setChecked(False)
        if not on:
            self.selected_edges = []
            self._hover_edge = None
        self.edge_panel.setVisible(on)
        self._draw_edges()

    def _edge_occluders(self):
        if self._occluders is None:
            if self._display_real is not None:
                self._occluders = self._display_real
            elif self._display_ghosts:
                self._occluders = np.concatenate(list(self._display_ghosts.values()))
        return self._occluders

    def _edge_at(self, x: float, y: float) -> Optional[int]:
        if not self._edge_targets or self._explosion:
            return None
        origin, direction = self.view.ray(x, y)
        return geo.pick_edge(self._edge_targets, origin, direction,
                             EDGE_PICK_PIXELS * self.view.pixel_angle(), self._edge_occluders())

    def _on_hover(self, x: float, y: float) -> None:
        if not self.edge_mode:
            return
        idx = self._edge_at(x, y)
        if idx != self._hover_edge:
            self._hover_edge = idx
            self._draw_edges()

    def _click_edge(self, x: float, y: float, ctrl: bool) -> None:
        idx = self._edge_at(x, y)
        if idx is None:
            if not ctrl:
                self.selected_edges = []
        else:
            key = (self._edge_targets[idx][0], self._edge_targets[idx][1])
            if ctrl:
                if key in self.selected_edges:
                    self.selected_edges.remove(key)
                else:
                    self.selected_edges.append(key)
            else:
                self.selected_edges = [] if self.selected_edges == [key] else [key]
        self._draw_edges()

    @staticmethod
    def _segments(polylines: list) -> Optional[np.ndarray]:
        segs = [np.stack([pl[:-1], pl[1:]], axis=1) for pl in polylines if len(pl) > 1]
        return np.concatenate(segs) if segs else None

    def _draw_edges(self) -> None:
        on = self.edge_mode
        chosen = set(self.selected_edges)
        picked = [e[2] for e in self._edge_targets if (e[0], e[1]) in chosen] if on else []
        _set_lines(self.edge_picked_lines, self._segments(picked))
        hover = [self._edge_targets[self._hover_edge][2]] if on and self._hover_edge is not None else []
        _set_lines(self.edge_hover_line, self._segments(hover))
        n = len(self.selected_edges)
        if self._explosion:
            text = tr("Pon la explosión a 0 para elegir aristas.")
        elif n:
            text = tr("{n} aristas elegidas · Ctrl+clic: añadir o quitar").format(n=n)
        else:
            text = tr("Haz clic en una arista de un cube o un cylinder")
        self.edge_info.setText(text)
        self._place_overlays()

    def _finish_edges(self, mode: str) -> None:
        if self.selected_edges:
            self.edgeFinish.emit(mode, float(self.edge_value.value()), list(self.selected_edges))

    def set_measuring(self, on: bool) -> None:
        if on and self.edge_btn.isChecked():
            self.edge_btn.setChecked(False)
        self.measuring = on
        self._points = []
        self.measure_line.setVisible(False)
        self.measure_dots.setVisible(False)
        self.measure_label.setVisible(on)
        self.measure_label.setText(tr("Medir: haz clic en dos puntos del modelo") if on else "")
        self._place_overlays()

    def _add_measure_point(self, p) -> None:
        if len(self._points) >= 2:
            self._points = []
        self._points.append(np.asarray(p, dtype=float))
        pts = np.array(self._points)
        self.measure_dots.setData(pos=pts.astype(np.float32))
        self.measure_dots.setVisible(True)
        if len(self._points) == 2:
            a, b = self._points
            d = b - a
            _set_lines(self.measure_line, np.array([[a, b]]))
            text = (f"{tr('Distancia')} {np.linalg.norm(d):.3f} mm   "
                    f"ΔX {d[0]:.3f}  ΔY {d[1]:.3f}  ΔZ {d[2]:.3f}")
            self.measure_label.setText(text)
            self.measured.emit(text)
        else:
            self.measure_line.setVisible(False)
            x, y, z = self._points[0]
            self.measure_label.setText(tr("Punto 1: ({x}, {y}, {z}) — haz clic en el segundo").format(
                x=f"{x:.2f}", y=f"{y:.2f}", z=f"{z:.2f}"))
        self._place_overlays()
