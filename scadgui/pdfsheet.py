"""PDF de la lámina técnica a escala real y del tamaño de la hoja.

OpenSCAD 2021.01 saca los PDF siempre en un A4 vertical, con regla y cuadrícula, así que una
lámina apaisada sale cortada. Aquí OpenSCAD exporta la lámina a SVG (en milímetros) y Qt la pasa a
un PDF con una página exactamente del tamaño de la hoja y sin márgenes.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QByteArray, QMarginsF, QRectF, QSizeF
from PySide6.QtGui import QGuiApplication, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtSvg import QSvgRenderer

LINE_MM = 0.25      # grosor del trazo: las vistas, el marco y los textos van en contorno, como en un plano
RESOLUTION = 1200   # puntos por pulgada del PDF (es vectorial; solo fija la rejilla de coordenadas)


def line_drawing(svg: str, line: float = LINE_MM) -> str:
    """El SVG de OpenSCAD con trazo negro fino y sin relleno gris."""
    return re.sub(r'stroke="[^"]*" fill="[^"]*" stroke-width="[^"]*"',
                  f'stroke="black" fill="none" stroke-width="{line}" stroke-linejoin="round"', svg)


def view_box(svg: str) -> tuple[float, float, float, float]:
    m = re.search(r'viewBox="([-\d.eE]+) ([-\d.eE]+) ([-\d.eE]+) ([-\d.eE]+)"', svg)
    if not m:
        raise ValueError("SVG sin viewBox")
    return tuple(float(v) for v in m.groups())


def svg_to_pdf(svg_path: str, pdf_path: str, sheet_w: float, sheet_h: float, title: str = "") -> None:
    """Pasa el SVG de OpenSCAD a un PDF de sheet_w × sheet_h mm. El SVG está en milímetros con la Y
    invertida (viewBox = x, -y máx, ancho, alto), así que cada cosa cae en su sitio de la hoja aunque
    el dibujo no ocupe la hoja entera (sin marco)."""
    if QGuiApplication.instance() is None:
        raise RuntimeError("svg_to_pdf necesita una QGuiApplication")
    with open(svg_path, encoding="utf-8") as fh:
        svg = fh.read()
    vx, vy, vw, vh = view_box(svg)
    renderer = QSvgRenderer(QByteArray(line_drawing(svg).encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("OpenSCAD dio un SVG que no se puede leer")
    writer = QPdfWriter(pdf_path)
    writer.setResolution(RESOLUTION)
    writer.setTitle(title)
    writer.setCreator("OpenSCAD GUI Mejorada")
    portrait = sheet_w <= sheet_h
    size = QPageSize(QSizeF(min(sheet_w, sheet_h), max(sheet_w, sheet_h)), QPageSize.Unit.Millimeter, "",
                     QPageSize.SizeMatchPolicy.ExactMatch)
    writer.setPageLayout(QPageLayout(size, QPageLayout.Orientation.Portrait if portrait
                                     else QPageLayout.Orientation.Landscape, QMarginsF(0, 0, 0, 0)))
    px = RESOLUTION / 25.4                       # puntos por milímetro
    painter = QPainter(writer)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(vx * px, (sheet_h + vy) * px, vw * px, vh * px))
    finally:
        painter.end()
