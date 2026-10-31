"""Iconos dibujados a partir de los trazos SVG del catálogo."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ..catalog import ICONS


@lru_cache(maxsize=256)
def icon(name: str, color: str = "#1B2230", size: int = 48, width: float = 1.6) -> QIcon:
    path = ICONS.get(name, ICONS["raw"])
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">'
           f'<path d="{path}"/></svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pix)
