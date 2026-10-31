"""Vista 3D: muestra la imagen que genera OpenSCAD y deja girar, acercar y desplazar."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
                               QWidget)

from ..i18n import tr
from ..runner import VIEWS, Camera


class _Canvas(QWidget):
    cameraChanged = Signal()       # al soltar el ratón tras girar
    zoomChanged = Signal()

    def __init__(self, viewport: "Viewport"):
        super().__init__(viewport)
        self.vp = viewport
        self.setMouseTracking(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 260)
        self._drag = None
        self._mode = ""

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#262B33"))
        vp = self.vp
        if vp.pixmap is not None and not vp.pixmap.isNull():
            pm = vp.pixmap
            # la imagen se renderiza a (tamaño × zoom_render); se muestra a (tamaño × zoom)
            scale = vp.zoom / max(vp.render_zoom, 0.01)
            w = pm.width() / pm.devicePixelRatio() * scale
            h = pm.height() / pm.devicePixelRatio() * scale
            x = (self.width() - w) / 2 + vp.pan.x()
            y = (self.height() - h) / 2 + vp.pan.y()
            p.drawPixmap(QRectF(x, y, w, h), pm, QRectF(pm.rect()))
        else:
            p.setPen(QColor("#9AA6B6"))
            f = QFont(self.font())
            f.setPointSize(11)
            p.setFont(f)
            p.drawText(self.rect().adjusted(24, 24, -24, -24),
                       int(Qt.AlignmentFlag.AlignCenter.value) | int(Qt.TextFlag.TextWordWrap.value), vp.message)
        if self._mode == "rotate":
            p.setPen(QColor("#F5A55A"))
            p.drawText(QPointF(14, self.height() - 14),
                       f"{tr('Girando…')} rx {vp.camera.rx:.0f}°  rz {vp.camera.rz:.0f}°  ({tr('suelta para actualizar')})")
        p.end()

    def mousePressEvent(self, e):
        self._drag = e.position()
        if e.button() == Qt.MouseButton.LeftButton:
            self._mode = "rotate"
        elif e.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self._mode = "pan"

    def mouseMoveEvent(self, e):
        if self._drag is None:
            return
        d = e.position() - self._drag
        self._drag = e.position()
        cam = self.vp.camera
        if self._mode == "rotate":
            cam.rz = (cam.rz - d.x() * 0.5) % 360
            cam.rx = max(0.0, min(180.0, cam.rx - d.y() * 0.5))
        elif self._mode == "pan":
            self.vp.pan += d
        self.update()

    def mouseReleaseEvent(self, e):
        mode = self._mode
        self._drag = None
        self._mode = ""
        self.update()
        if mode == "rotate":
            self.cameraChanged.emit()

    def wheelEvent(self, e):
        steps = e.angleDelta().y() / 120.0
        vp = self.vp
        vp.zoom = max(0.3, min(6.0, vp.zoom * (1.15 ** steps)))
        self.update()
        self.zoomChanged.emit()

    def mouseDoubleClickEvent(self, e):
        self.vp.fit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.vp.request_render()


class Viewport(QWidget):
    renderRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("viewport")
        self.camera = Camera()
        self.pixmap: QPixmap | None = None
        self.zoom = 1.0
        self.render_zoom = 1.0
        self.pan = QPointF(0, 0)
        self.message = "Crea una pieza con los botones de arriba para verla aquí."

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QWidget()
        bar.setObjectName("viewBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)
        title = QLabel(tr("Vista previa"))
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
        row.addStretch(1)
        self.auto = QCheckBox(tr("Actualizar sola"))
        self.auto.setObjectName("viewCheck")
        self.auto.setChecked(True)
        row.addWidget(self.auto)
        self.status = QLabel("")
        self.status.setObjectName("viewStatus")
        row.addWidget(self.status)
        layout.addWidget(bar)

        self.canvas = _Canvas(self)
        layout.addWidget(self.canvas, 1)

        self.selection = QLabel("", self.canvas)
        self.selection.setObjectName("selectionBadge")
        self.selection.move(12, 12)
        self.selection.hide()

        self.setup = QPushButton(tr("Elegir openscad…"), self.canvas)
        self.setup.setObjectName("primary")
        self.setup.hide()

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(350)
        self._render_timer.timeout.connect(self.renderRequested.emit)
        self.canvas.cameraChanged.connect(self.request_render)
        self.canvas.zoomChanged.connect(self._zoom_changed)

    # ----- api
    def render_size(self) -> tuple[int, int]:
        ratio = self.devicePixelRatioF()
        z = max(1.0, min(self.zoom, 2.5))
        self._pending_zoom = z
        return int(self.canvas.width() * z * ratio), int(self.canvas.height() * z * ratio)

    def set_image(self, path: str) -> None:
        pm = QPixmap(path)
        if pm.isNull():
            return
        pm.setDevicePixelRatio(self.devicePixelRatioF())
        self.pixmap = pm
        self.render_zoom = getattr(self, "_pending_zoom", 1.0)
        self.canvas.update()

    def clear(self, message: str) -> None:
        self.pixmap = None
        self.message = message
        self.canvas.update()

    def show_setup_button(self, visible: bool) -> None:
        self.setup.setVisible(visible)
        if visible:
            self.setup.adjustSize()
            self.setup.move((self.canvas.width() - self.setup.width()) // 2, self.canvas.height() // 2 + 40)

    def set_selection_text(self, text: str) -> None:
        self.selection.setText(text)
        self.selection.adjustSize()
        self.selection.setVisible(bool(text))

    def set_view(self, name: str) -> None:
        c = VIEWS[name]
        self.camera = Camera(c.rx, c.ry, c.rz)
        self.fit(render=False)
        self.request_render(now=True)

    def fit(self, render: bool = True) -> None:
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.canvas.update()
        if render:
            self.request_render(now=True)

    def request_render(self, now: bool = False) -> None:
        if now:
            self._render_timer.stop()
            self.renderRequested.emit()
        else:
            self._render_timer.start()

    def _zoom_changed(self) -> None:
        # vuelve a pedir la imagen con más resolución si el zoom creció mucho
        if self.zoom > self.render_zoom * 1.3 and self.render_zoom < 2.5:
            self._render_timer.start(500)
