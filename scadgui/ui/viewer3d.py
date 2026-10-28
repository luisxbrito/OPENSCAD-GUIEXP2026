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
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from .. import geometry as geo
from ..i18n import tr

VIEWS = {  # elevación, azimut
    "Isométrica": (30.0, -55.0),
    "Frontal": (0.0, -90.0),
    "Superior": (90.0, -90.0),
    "Derecha": (0.0, 0.0),
}

# Dibujar encima de la pieza (como el modificador # de OpenSCAD)
SEE_THROUGH = {
    GL.GL_DEPTH_TEST: False,
    GL.GL_BLEND: True,
    GL.GL_CULL_FACE: False,
    "glBlendFunc": (GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA),
}

EDGE_COLOR = (0.10, 0.12, 0.16, 0.85)
SELECT_COLOR = (1.0, 0.55, 0.14, 0.38)
SELECT_EDGE = (1.0, 0.62, 0.25, 1.0)
HASH_COLOR = (1.0, 0.35, 0.55, 0.30)      # piezas con #
BACKGROUND_COLOR = (0.75, 0.78, 0.82, 0.18)  # piezas con %
MEASURE_COLOR = (0.35, 0.85, 1.0, 1.0)


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
    """Carga triángulos con su color por cara (ya iluminado). Sin colores, usa el del elemento."""
    if tris is None or len(tris) == 0:
        item.setVisible(False)
        return
    if face_colors is None:
        base = np.tile(np.array(item.base_color, dtype=np.float64), (len(tris), 1))
        face_colors = geo.shade(geo.face_normals(tris), base)
    vcolors = np.repeat(np.asarray(face_colors, dtype=np.float32)[:, None, :], 3, axis=1)
    item.setMeshData(meshdata=gl.MeshData(vertexes=np.ascontiguousarray(tris, dtype=np.float32),
                                          vertexColors=np.ascontiguousarray(vcolors)))
    item.setVisible(True)


def _set_lines(item, segments) -> None:
    if segments is None or len(segments) == 0:
        item.setVisible(False)
        return
    item.setData(pos=np.ascontiguousarray(segments.reshape(-1, 3), dtype=np.float32))
    item.setVisible(True)


class _GLView(gl.GLViewWidget):
    clicked = Signal(float, float, bool)   # x, y, Ctrl pulsado
    hovered = Signal(float, float)
    gizmoStarted = Signal()
    gizmoMoved = Signal(float, float, float)  # dx, dy, dz totales acumulados desde el inicio del clic
    gizmoFinished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._press = None
        self.gizmo_origin: Optional[np.ndarray] = None
        self.gizmo_len: float = 25.0
        self._active_axis: Optional[str] = None
        self._drag_start_s: float = 0.0
        self._prev_s: float = 0.0

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
            cam_dist = float(np.linalg.norm(self.gizmo_origin - cam))
            hit_threshold = max(3.0, cam_dist * 0.04)

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
                    if dist < hit_threshold and dist < best_dist:
                        best_dist = dist
                        best_axis = name
                        best_s = s

            if best_axis is not None:
                self._active_axis = best_axis
                self._drag_start_s = best_s
                self._prev_s = best_s
                self.gizmoStarted.emit()
                return

        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._active_axis is not None and self.gizmo_origin is not None:
            pos = ev.position()
            cam, d = self.ray(pos.x(), pos.y())
            u = np.array([1.0, 0.0, 0.0] if self._active_axis == "X" else
                         [0.0, 1.0, 0.0] if self._active_axis == "Y" else
                         [0.0, 0.0, 1.0])
            w0 = self.gizmo_origin - cam
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
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._active_axis is not None:
            self._active_axis = None
            self._press = None
            self.gizmoFinished.emit()
            return
        super().mouseReleaseEvent(ev)
        if self._press is None or ev.button() != Qt.MouseButton.LeftButton:
            return
        d = ev.position() - self._press
        self._press = None
        if abs(d.x()) + abs(d.y()) < 5:
            ctrl = bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier)
            self.clicked.emit(ev.position().x(), ev.position().y(), ctrl)

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("viewport")
        self.real: Optional[np.ndarray] = None
        self.ghosts: dict = {}
        self._picker: Optional[geo.Picker] = None
        self._fitted = False
        self.measuring = False
        self._points: list = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QWidget()
        bar.setObjectName("viewBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)
        title = QLabel(tr("Vista 3D"))
        title.setObjectName("viewTitle")
        row.addWidget(title)
        for name in VIEWS:
            b = QPushButton(tr(name))
            b.setObjectName("viewButton")
            b.clicked.connect(lambda _=False, n=name: self.set_view(n))
            row.addWidget(b)
        fit = QPushButton(tr("Ajustar"))
        fit.setObjectName("viewButton")
        fit.clicked.connect(self.fit)
        row.addWidget(fit)
        self.measure_btn = QPushButton(tr("Medir"))
        self.measure_btn.setObjectName("viewButton")
        self.measure_btn.setCheckable(True)
        self.measure_btn.toggled.connect(self.set_measuring)
        row.addWidget(self.measure_btn)
        self.edges_check = QCheckBox(tr("Aristas"))
        self.edges_check.setObjectName("viewCheck")
        self.edges_check.setChecked(True)
        self.edges_check.toggled.connect(lambda on: self.edges.setVisible(on and self.real is not None))
        row.addWidget(self.edges_check)
        row.addWidget(QLabel(tr("Explosión:")))
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
        layout.addWidget(bar)

        self.view = _GLView()
        self.view.setBackgroundColor(pg.mkColor("#262B33"))
        self.view.opts["fov"] = 45
        self.view.setCameraPosition(distance=120, elevation=30, azimuth=-55)
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

        self.model = _mesh_item(geo.DEFAULT_COLOR, "opaque", 0)
        self.approx = _mesh_item(geo.DEFAULT_COLOR, "opaque", 0)
        self.colors: dict = {}
        self._face_colors = None  # colores que trae el .off de OpenSCAD
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

        self.gizmo_lines = gl.GLLinePlotItem(
            pos=np.zeros((6, 3), dtype=np.float32),
            color=np.array([[1.0, 0.2, 0.2, 1.0]] * 2 +
                           [[0.2, 0.9, 0.2, 1.0]] * 2 +
                           [[0.2, 0.5, 1.0, 1.0]] * 2, dtype=np.float32),
            mode="lines", width=3.5, antialias=True, glOptions="opaque")
        self.gizmo_lines.setDepthValue(30)
        self.gizmo_lines.setVisible(False)

        self.gizmo_tips = gl.GLScatterPlotItem(
            pos=np.zeros((3, 3), dtype=np.float32),
            color=np.array([[1.0, 0.2, 0.2, 1.0],
                           [0.2, 0.9, 0.2, 1.0],
                           [0.2, 0.5, 1.0, 1.0]], dtype=np.float32),
            size=10, pxMode=True, glOptions="opaque")
        self.gizmo_tips.setDepthValue(31)
        self.gizmo_tips.setVisible(False)

        for item in (self.model, self.approx, self.edges, self.background, self.hashed, self.highlight,
                     self.highlight_edges, self.measure_line, self.measure_dots,
                     self.gizmo_lines, self.gizmo_tips):
            self.view.addItem(item)

        self.message = QLabel("", self.view)
        self.message.setObjectName("viewMessage")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
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
                              "Clic: seleccionar · Ctrl+clic: añadir"), self.view)
        self.hint.setObjectName("viewHint")

        self.view.clicked.connect(self._on_click)
        self.view.gizmoStarted.connect(self.gizmoStarted)
        self.view.gizmoMoved.connect(self.gizmoMoved)
        self.view.gizmoFinished.connect(self.gizmoFinished)
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
        self.measure_label.adjustSize()
        self.measure_label.move(max(12, w - self.measure_label.width() - 12), 12)
        self.setup.adjustSize()
        self.setup.move((w - self.setup.width()) // 2, h // 2 + 30)

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
            _set_lines(self.edges, geo.feature_edges(self.real))
            self.edges.setVisible(self.edges_check.isChecked())
            self.show_message("")
            if not self._fitted:
                self.fit()
                self._fitted = True
            self._resize_grid()
        else:
            self.edges.setVisible(False)
        self.approx.setVisible(self.real is None and bool(self.ghosts))
        self._picker = None

    def _paint_model(self) -> None:
        """Colorea la malla real: colores de OpenSCAD o, si no vienen, el color() de cada pieza."""
        if self.real is None:
            self.model.setVisible(False)
            return
        if self._face_colors is not None:
            cols = geo.colored(self.real, None, self.colors, self._face_colors)
        else:
            owner = geo.assign_faces(self.real, self.ghosts) if self.ghosts else None
            cols = geo.colored(self.real, owner, self.colors)
        _set_mesh(self.model, self.real, cols)

    def set_ghosts(self, ghosts: dict, colors=None, hashed=None, background=None) -> None:
        """Mallas aproximadas por pieza (para colorear y seleccionar) y las de los modificadores # y %."""
        self.ghosts = ghosts
        self.colors = colors or {}
        self._picker = None
        if ghosts:
            tris, cols = geo.ghost_colors(ghosts, self.colors)
            _set_mesh(self.approx, tris, cols)
        self.approx.setVisible(self.real is None and bool(ghosts))
        if self.real is not None and self._face_colors is None:
            self._paint_model()  # p. ej. cambió un color()
        _set_mesh(self.hashed, hashed)
        _set_mesh(self.background, background)
        if self.real is None and not self._fitted and ghosts:
            self.fit()

    def set_highlight(self, tris: Optional[np.ndarray]) -> None:
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

        lines_pos = np.array([
            c, c + [L, 0.0, 0.0],
            c, c + [0.0, L, 0.0],
            c, c + [0.0, 0.0, L],
        ], dtype=np.float32)
        self.gizmo_lines.setData(pos=lines_pos)
        self.gizmo_lines.setVisible(True)

        tips_pos = np.array([
            c + [L, 0.0, 0.0],
            c + [0.0, L, 0.0],
            c + [0.0, 0.0, L],
        ], dtype=np.float32)
        self.gizmo_tips.setData(pos=tips_pos)
        self.gizmo_tips.setVisible(True)

    def set_explosion(self, percent: int) -> None:
        if percent == 0:
            if self.real is not None:
                self.model.setVisible(True)
                self.approx.setVisible(False)
            else:
                self.approx.setVisible(bool(self.ghosts))
                if self.ghosts:
                    tris, cols = geo.ghost_colors(self.ghosts, self.colors)
                    _set_mesh(self.approx, tris, cols)
            return

        if not self.ghosts:
            return

        all_pts = np.concatenate([t.reshape(-1, 3) for t in self.ghosts.values() if len(t)])
        if len(all_pts) == 0:
            return
        c_global = all_pts.mean(axis=0)

        exploded_ghosts = {}
        for nid, tris in self.ghosts.items():
            if len(tris) == 0:
                exploded_ghosts[nid] = tris
                continue
            c_piece = tris.reshape(-1, 3).mean(axis=0)
            vec = c_piece - c_global
            norm = float(np.linalg.norm(vec))
            if norm < 1e-4:
                vec = np.array([0.0, 0.0, 1.0])
            else:
                vec = vec / norm
            offset = vec * (percent * 0.5)
            exploded_ghosts[nid] = tris + offset

        tris, cols = geo.ghost_colors(exploded_ghosts, self.colors)
        _set_mesh(self.approx, tris, cols)
        self.model.setVisible(False)
        self.approx.setVisible(True)

    # ------------------------------------------------------------- cámara
    def _scene_box(self):
        if self.real is not None:
            return geo.bbox(self.real)
        if self.ghosts:
            return geo.bbox(np.concatenate(list(self.ghosts.values())))
        return None

    def fit(self) -> None:
        box = self._scene_box()
        if box is None:
            return
        lo, hi = box
        center = (lo + hi) / 2
        size = float(np.linalg.norm(hi - lo)) or 10.0
        dist = size / 2 / math.tan(math.radians(self.view.opts["fov"]) / 2) * 1.25
        self.view.setCameraPosition(pos=pg.Vector(*center), distance=dist)

    def set_view(self, name: str) -> None:
        elev, azim = VIEWS[name]
        self.view.setCameraPosition(elevation=elev, azimuth=azim)
        self.fit()

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
            self._picker = geo.Picker(self.real, self.ghosts)
        return self._picker

    def _on_click(self, x: float, y: float, ctrl: bool) -> None:
        origin, direction = self.view.ray(x, y)
        nid, hit = self._get_picker().pick(origin, direction)
        if self.measuring:
            if hit is not None:
                self._add_measure_point(hit)
            return
        self.picked.emit(-1 if nid is None else nid, ctrl)

    def set_measuring(self, on: bool) -> None:
        self.measuring = on
        self._points = []
        self.measure_line.setVisible(False)
        self.measure_dots.setVisible(False)
        self.measure_label.setVisible(on)
        self.measure_label.setText("Medir: haz clic en dos puntos del modelo" if on else "")
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
            text = (f"Distancia {np.linalg.norm(d):.3f} mm   "
                    f"ΔX {d[0]:.3f}  ΔY {d[1]:.3f}  ΔZ {d[2]:.3f}")
            self.measure_label.setText(text)
            self.measured.emit(text)
        else:
            self.measure_line.setVisible(False)
            x, y, z = self._points[0]
            self.measure_label.setText(f"Punto 1: ({x:.2f}, {y:.2f}, {z:.2f}) — haz clic en el segundo")
        self._place_overlays()
