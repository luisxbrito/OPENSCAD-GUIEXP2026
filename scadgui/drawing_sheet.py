"""Lámina técnica completa dibujada desde la malla: marco ISO 5457, cajetín ISO 7200, notas, cotas
generales y las vistas con sus líneas visibles y ocultas. Sale en SVG (milímetros) o DXF. Sin Qt.

El PDF se hace desde el SVG con ``pdfsheet.svg_to_pdf``.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field
from typing import Optional

from .drawing import LABEL_GAP, LABEL_SIZE, SHEET_SIZES, SheetFormat, plan_views, scale_label, view_labels
from .i18n import get_language, tr

# Grosores ISO 128 (serie 0.25 / 0.5) y discontinuos en milímetros.
STYLES = {
    "thick": dict(width=0.5),
    "thin": dict(width=0.25),
    "hidden": dict(width=0.25, dash=(3.0, 1.5)),
    "center": dict(width=0.25, dash=(8.0, 1.5, 1.0, 1.5)),
    "frame": dict(width=0.7),
    "symbol": dict(width=0.35),
}
MARGINS = (20.0, 10.0, 10.0, 10.0)   # ISO 5457: 20 mm a la izquierda para encuadernar
ZONE = 50.0                          # largo aproximado de cada zona de referencia
BLOCK_W, ROW_H = 180.0, 9.0          # cajetín ISO 7200: 180 mm de ancho, 5 filas
BLOCK_H = 5 * ROW_H
NOTE_SIZE, NOTE_STEP = 2.5, 4.2
DIM_OFFSET = 8.0                     # de la vista a la línea de cota
DIM_PAD = DIM_OFFSET + 3.5           # sitio que se reserva para una cota
DIM_TEXT = 3.0
ARROW_L, ARROW_W = 2.5, 0.6

# Materiales habituales y su densidad en g/cm³ (para la masa del cajetín).
N_ = str   # marca un texto que se traduce después con tr() (lo recoge test_i18n)
MATERIALS = (
    ("PLA", 1.24), ("PETG", 1.27), ("ABS", 1.04), ("ASA", 1.07), (N_("Nailon PA12"), 1.01),
    (N_("Acero S235"), 7.85), (N_("Acero inoxidable AISI 304"), 7.93), (N_("Aluminio 6061"), 2.70),
    (N_("Latón"), 8.50), (N_("Bronce"), 8.80),
)


@dataclass
class SheetInfo:
    """Datos del cajetín y de las notas."""
    title: str = ""
    description: str = ""
    company: str = ""
    number: str = ""
    revision: str = "A"
    material: str = ""
    density: Optional[float] = None   # g/cm³; sin ella no se da la masa
    author: str = ""
    checker: str = ""
    date: str = ""
    tolerance: str = "ISO 2768-m"
    notes: list = field(default_factory=list)


@dataclass
class Sheet:
    w: float
    h: float
    lines: list = field(default_factory=list)   # (puntos [(x, y), ...], estilo)
    texts: list = field(default_factory=list)   # (x, y, texto, tamaño, alineación, giro en grados)
    fills: list = field(default_factory=list)   # polígonos rellenos (puntas de flecha)
    scale: float = 1.0
    fits: bool = True

    def line(self, pts, style="thin"):
        self.lines.append(([tuple(map(float, p)) for p in pts], style))

    def rect(self, x, y, w, h, style="thin"):
        self.line([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], style)

    def text(self, x, y, s, size=3.5, align="start", angle=0.0):
        self.texts.append((float(x), float(y), str(s), float(size), align, float(angle)))


def text_width(s: str, size: float) -> float:
    return 0.6 * size * len(s)


def fit_size(s: str, size: float, room: float) -> float:
    """Tamaño de letra que deja el texto dentro de ``room`` mm (sin pasar de ``size``)."""
    return min(size, room / max(0.6 * len(s), 1e-9)) if s else size


def number(v: float, decimals: int = 2) -> str:
    """Número para el plano: sin ceros de más y con la coma decimal salvo en inglés."""
    s = f"{v:.{decimals}f}".rstrip("0").rstrip(".")
    return s if get_language() == "en" else s.replace(".", ",")


def sheet_format(views: dict, dims: bool, notes: int) -> SheetFormat:
    pads = []
    if dims:
        if views.get("front", True):
            pads.append(("front", (0.0, DIM_PAD, DIM_PAD, 0.0)))     # ancho abajo, alto a la derecha
        if views.get("top", True):
            pads.append(("top", (0.0, 0.0, DIM_PAD, 0.0)))           # fondo a la derecha
    title_h = BLOCK_H + (NOTE_STEP * (notes + 1) + 2 if notes else 0)
    return SheetFormat(frame=MARGINS, title=(BLOCK_W, title_h), pads=tuple(pads))


def circles(polylines: list, min_points: int = 12, tol: float = 0.02) -> list:
    """Circunferencias de una vista ortogonal (taladros, ejes, bordes redondos): polilíneas cerradas
    cuyos puntos están todos a la misma distancia de su centro. Devuelve [((x, y), radio)], sin
    repetir las concéntricas del mismo radio."""
    found = []
    for line in polylines:
        if len(line) < min_points or math.dist(line[0], line[-1]) > 1e-6:
            continue
        pts = line[:-1]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        radii = [math.dist(p, (cx, cy)) for p in pts]
        r = sum(radii) / len(radii)
        if r > 0 and max(abs(d - r) for d in radii) <= tol * r:
            if not any(math.dist(c, (cx, cy)) < 1e-3 * max(r, 1) and abs(rr - r) < 1e-3 * r for c, rr in found):
                found.append(((cx, cy), r))
    # Solo un eje por centro: el de la circunferencia mayor.
    best: dict = {}
    for c, r in found:
        key = (round(c[0], 3), round(c[1], 3))
        best[key] = max(best.get(key, (c, 0.0)), (c, r), key=lambda v: v[1])
    return list(best.values())


def _extents(lines: dict) -> dict:
    out = {}
    for key, (vis, hid) in lines.items():
        pts = [p for line in vis + hid for p in line]
        if pts:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            out[key] = (min(xs), min(ys), max(xs), max(ys))
    return out


# --------------------------------------------------------------------------- partes de la lámina

def _frame(sh: Sheet) -> None:
    w, h = sh.w, sh.h
    l, b, r, t = MARGINS
    sh.rect(0, 0, w, h, "thin")                                # borde de corte de la hoja
    sh.rect(l, b, w - l - r, h - b - t, "frame")               # recuadro
    # Zonas de referencia: números arriba y abajo, letras a los lados (A arriba), en una franja
    # de 5 mm por fuera del recuadro.
    s = 5.0
    sh.rect(l - s, b - s, w - l - r + 2 * s, h - b - t + 2 * s, "thin")
    nx = max(2, round((w - l - r) / ZONE / 2) * 2)
    ny = max(2, round((h - b - t) / ZONE / 2) * 2)
    for i in range(nx + 1):
        x = l + (w - l - r) * i / nx
        sh.line([(x, b - s), (x, b)])
        sh.line([(x, h - t), (x, h - t + s)])
        if i < nx:
            xm = x + (w - l - r) / nx / 2
            sh.text(xm, b - s + 1.3, str(i + 1), 2.5, "middle")
            sh.text(xm, h - t + 1.3, str(i + 1), 2.5, "middle")
    for j in range(ny + 1):
        y = b + (h - b - t) * j / ny
        sh.line([(l - s, y), (l, y)])
        sh.line([(w - r, y), (w - r + s, y)])
        if j < ny:
            ym = y + (h - b - t) / ny / 2 - 1.2
            letter = chr(ord("A") + ny - 1 - j)
            sh.text(l - s / 2, ym, letter, 2.5, "middle")
            sh.text(w - r + s / 2, ym, letter, 2.5, "middle")
    # Marcas de centrado en el centro de cada lado, del borde de la hoja al recuadro.
    sh.line([(w / 2, 0), (w / 2, b)], "frame")
    sh.line([(w / 2, h), (w / 2, h - t)], "frame")
    sh.line([(0, h / 2), (l, h / 2)], "frame")
    sh.line([(w, h / 2), (w - r, h / 2)], "frame")


def _projection_symbol(sh: Sheet, cx: float, cy: float) -> None:
    """Símbolo del método de primer diedro (europeo, ISO 5456-2): el cono truncado visto de frente
    a la izquierda y, a su derecha, visto desde la izquierda."""
    d1, d2, length = 4.0, 8.0, 8.0
    x0 = cx - 11
    sh.line([(x0, cy - d1 / 2), (x0 + length, cy - d2 / 2), (x0 + length, cy + d2 / 2), (x0, cy + d1 / 2),
             (x0, cy - d1 / 2)], "symbol")
    xc = cx + 7
    for d in (d2, d1):
        n = 48
        sh.line([(xc + d / 2 * math.cos(2 * math.pi * i / n), cy + d / 2 * math.sin(2 * math.pi * i / n))
                 for i in range(n + 1)], "symbol")
    sh.line([(x0 - 2, cy), (xc + d2 / 2 + 2, cy)], "center")
    sh.line([(xc, cy - d2 / 2 - 2), (xc, cy + d2 / 2 + 2)], "center")


def _cell(sh: Sheet, x, y, w, h, label, value, size=3.0):
    sh.rect(x, y, w, h)
    sh.text(x + 1.2, y + h - 2.4, label, 1.8)
    if value:
        sh.text(x + 1.5, y + 1.8, value, fit_size(value, size, w - 3))


def _title_block(sh: Sheet, info: SheetInfo, sheet_size: str, box, volume: Optional[float]) -> None:
    w = sh.w
    x0, y0 = w - MARGINS[2] - BLOCK_W, MARGINS[1]
    sh.rect(x0, y0, BLOCK_W, BLOCK_H, "frame")
    r = ROW_H
    _cell(sh, x0, y0 + 4 * r, 110, r, tr("Empresa"), info.company)
    _cell(sh, x0 + 110, y0 + 4 * r, 70, r, tr("Nº de plano"), info.number, 3.5)
    # Título (dos filas) con la descripción debajo
    sh.rect(x0, y0 + 2 * r, 110, 2 * r)
    sh.text(x0 + 1.2, y0 + 4 * r - 2.4, tr("Título"), 1.8)
    title = info.title or tr("Plano técnico")
    sh.text(x0 + 2, y0 + 2 * r + (6.0 if info.description else 4.0), title, fit_size(title, 5.0, 106))
    if info.description:
        sh.text(x0 + 2, y0 + 2 * r + 1.6, info.description, fit_size(info.description, 2.5, 106))
    _cell(sh, x0 + 110, y0 + 3 * r, 30, r, tr("Escala"), scale_label(sh.scale), 3.5)
    _cell(sh, x0 + 110, y0 + 2 * r, 30, r, tr("Formato"), sheet_size, 3.5)
    sh.rect(x0 + 140, y0 + 2 * r, 40, 2 * r)
    sh.text(x0 + 141.2, y0 + 4 * r - 2.4, tr("Proyección"), 1.8)
    _projection_symbol(sh, x0 + 160, y0 + 2 * r + 7.0)
    # Material, masa y medidas generales
    _cell(sh, x0, y0 + r, 55, r, tr("Material"), info.material)
    mass = ""
    if volume is not None:
        cm3 = volume / 1000.0
        mass = f"{number(cm3, 1)} cm³"
        if info.density:
            mass = f"{number(cm3 * info.density / 1000.0, 3)} kg  ·  " + mass
    _cell(sh, x0 + 55, y0 + r, 55, r, tr("Masa") if info.density else tr("Volumen"), mass)
    (ax, ay, az), (bx, by, bz) = box
    sizes = f"{number(bx - ax)} × {number(by - ay)} × {number(bz - az)} mm"
    _cell(sh, x0 + 110, y0 + r, 70, r, tr("Medidas generales (X × Y × Z)"), sizes)
    # Personas, fecha, tolerancias, hoja y revisión
    _cell(sh, x0, y0, 40, r, tr("Dibujado"), info.author, 2.8)
    _cell(sh, x0 + 40, y0, 40, r, tr("Revisado"), info.checker, 2.8)
    _cell(sh, x0 + 80, y0, 30, r, tr("Fecha"), info.date or datetime.date.today().isoformat(), 2.8)
    _cell(sh, x0 + 110, y0, 40, r, tr("Tolerancias generales"), info.tolerance, 2.8)
    _cell(sh, x0 + 150, y0, 15, r, tr("Hoja"), "1/1", 2.8)
    _cell(sh, x0 + 165, y0, 15, r, tr("Rev."), info.revision, 2.8)
    # Notas encima del cajetín
    notes = [n for n in info.notes if n.strip()]
    if notes:
        y = y0 + BLOCK_H + 2 + NOTE_STEP * len(notes)
        sh.text(x0, y, tr("NOTAS:"), 2.8)
        for i, n in enumerate(notes):
            s = f"{i + 1}. {n.strip()}"
            sh.text(x0 + 2, y - NOTE_STEP * (i + 1), s, fit_size(s, NOTE_SIZE, BLOCK_W - 2))


def _arrow(sh: Sheet, tip, direction) -> None:
    dx, dy = direction
    nx, ny = -dy, dx
    bx, by = tip[0] - dx * ARROW_L, tip[1] - dy * ARROW_L
    sh.fills.append([tip, (bx + nx * ARROW_W, by + ny * ARROW_W), (bx - nx * ARROW_W, by - ny * ARROW_W)])


def _dim_h(sh: Sheet, x0, x1, y_from, y_dim, value) -> None:
    """Cota horizontal entre x0 y x1, con la línea en y_dim (por debajo de y_from)."""
    sign = -1 if y_dim < y_from else 1
    for x in (x0, x1):
        sh.line([(x, y_from + sign * 1.0), (x, y_dim + sign * 2.0)])
    sh.line([(x0, y_dim), (x1, y_dim)])
    _arrow(sh, (x0, y_dim), (-1, 0))
    _arrow(sh, (x1, y_dim), (1, 0))
    sh.text((x0 + x1) / 2, y_dim + 1.0, value, DIM_TEXT, "middle")


def _dim_v(sh: Sheet, y0, y1, x_from, x_dim, value) -> None:
    """Cota vertical entre y0 e y1, con la línea en x_dim (a la derecha de x_from). El texto va
    girado y se lee desde la derecha, como pide la norma."""
    for y in (y0, y1):
        sh.line([(x_from + 1.0, y), (x_dim + 2.0, y)])
    sh.line([(x_dim, y0), (x_dim, y1)])
    _arrow(sh, (x_dim, y0), (0, -1))
    _arrow(sh, (x_dim, y1), (0, 1))
    sh.text(x_dim - 1.0, (y0 + y1) / 2, value, DIM_TEXT, "middle", 90.0)


# --------------------------------------------------------------------------- lámina

def build_sheet(lines: dict, box, info: SheetInfo, sheet_size: str = "A4", scale: float = 0.0,
                views: Optional[dict] = None, dims: bool = True, volume: Optional[float] = None) -> Sheet:
    """Monta la lámina. ``lines`` da, por vista, (visibles, ocultas) en coordenadas de la vista a
    escala 1, como las devuelve ``drawing_lines.view_lines``."""
    views = views or {k: True for k in ("front", "top", "side", "isometric")}
    views = {k: bool(views.get(k, True)) and k in lines for k in ("front", "top", "side", "isometric")}
    notes = [n for n in info.notes if n.strip()]
    fmt = sheet_format(views, dims, len(notes))
    ext = _extents(lines)
    scale, place, fits, scales = plan_views(box, sheet_size, scale, views, True, fmt, ext)
    w, h = SHEET_SIZES.get(sheet_size, SHEET_SIZES["A4"])
    sh = Sheet(w, h, scale=scale, fits=fits)
    _frame(sh)
    _title_block(sh, info, sheet_size, box, volume)
    labels = view_labels()
    for key, (cx, cy, _) in place.items():
        e = ext.get(key)
        if e is None:
            continue
        mx, my = (e[0] + e[2]) / 2, (e[1] + e[3]) / 2
        k = scales[key]

        def put(p, k=k, cx=cx, cy=cy, mx=mx, my=my):
            return cx + (p[0] - mx) * k, cy + (p[1] - my) * k
        vis, hid = lines[key]
        for line in hid:
            sh.line([put(p) for p in line], "hidden")
        for line in vis:
            sh.line([put(p) for p in line], "thick")
        if key != "isometric":
            for (x, y), radius in circles(vis + hid):
                c = put((x, y))
                arm = radius * k + 2.0                   # el eje sobresale 2 mm de la circunferencia
                sh.line([(c[0] - arm, c[1]), (c[0] + arm, c[1])], "center")
                sh.line([(c[0], c[1] - arm), (c[0], c[1] + arm)], "center")
        left, bottom = put((e[0], e[1]))
        right, top = put((e[2], e[3]))
        pb = fmt.pad(key)[1]
        label = labels[key] if k == scale else f"{labels[key]} ({scale_label(k)})"
        sh.text(cx, bottom - pb - LABEL_GAP - LABEL_SIZE, label, LABEL_SIZE, "middle")
        if dims and key == "front":
            (ax, ay, az), (bx, by, bz) = box
            _dim_h(sh, left, right, bottom, bottom - DIM_OFFSET, number(bx - ax))
            _dim_v(sh, bottom, top, right, right + DIM_OFFSET, number(bz - az))
        if dims and key == "top":
            (ax, ay, az), (bx, by, bz) = box
            _dim_v(sh, bottom, top, right, right + DIM_OFFSET, number(by - ay))
    return sh


# --------------------------------------------------------------------------- salidas

def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def to_svg(sh: Sheet, title: str = "") -> str:
    """SVG en milímetros. La Y va invertida (viewBox desde -alto), igual que los de OpenSCAD."""
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{sh.w:g}mm" height="{sh.h:g}mm" '
           f'viewBox="0 {-sh.h:g} {sh.w:g} {sh.h:g}">',
           f"<title>{_esc(title or 'OpenSCAD GUI Mejorada')}</title>",
           f'<rect x="0" y="{-sh.h:g}" width="{sh.w:g}" height="{sh.h:g}" fill="white"/>']
    by_style: dict = {}
    for pts, style in sh.lines:
        by_style.setdefault(style, []).append(pts)
    for style in ("thin", "hidden", "center", "symbol", "thick", "frame"):
        if style not in by_style:
            continue
        st = STYLES[style]
        dash = f' stroke-dasharray="{",".join(f"{d:g}" for d in st["dash"])}"' if "dash" in st else ""
        d = " ".join("M " + " L ".join(f"{x:.3f},{-y:.3f}" for x, y in pts) for pts in by_style[style])
        out.append(f'<path d="{d}" fill="none" stroke="black" stroke-width="{st["width"]}" '
                   f'stroke-linecap="round" stroke-linejoin="round"{dash}/>')
    if sh.fills:
        d = " ".join("M " + " L ".join(f"{x:.3f},{-y:.3f}" for x, y in pts) + " Z" for pts in sh.fills)
        out.append(f'<path d="{d}" fill="black" stroke="none"/>')
    anchor = {"start": "start", "middle": "middle", "end": "end"}
    for x, y, s, size, align, angle in sh.texts:
        rot = f' transform="rotate({-angle:g} {x:.3f} {-y:.3f})"' if angle else ""
        out.append(f'<text x="{x:.3f}" y="{-y:.3f}" font-family="Liberation Sans, Arial, Helvetica, sans-serif" '
                   f'font-size="{size:.2f}" text-anchor="{anchor[align]}" fill="black"{rot}>{_esc(s)}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


_DXF_LAYERS = {"thick": ("VISIBLES", 7, "CONTINUOUS"), "hidden": ("OCULTAS", 8, "DASHED"),
               "thin": ("FINAS", 7, "CONTINUOUS"), "center": ("EJES", 1, "CENTER"),
               "frame": ("MARCO", 7, "CONTINUOUS"), "symbol": ("MARCO", 7, "CONTINUOUS"),
               "text": ("TEXTOS", 7, "CONTINUOUS")}


def to_dxf(sh: Sheet) -> str:
    """DXF R12 en milímetros: líneas por capa (visibles, ocultas con discontinuo, finas, ejes,
    marco), textos y puntas de flecha rellenas."""
    o: list = []

    def g(code, value):
        o.append(f"{code}\n{value}")
    g(0, "SECTION"); g(2, "HEADER"); g(9, "$ACADVER"); g(1, "AC1009")
    g(9, "$INSUNITS"); g(70, 4); g(9, "$EXTMIN"); g(10, 0); g(20, 0); g(9, "$EXTMAX"); g(10, sh.w); g(20, sh.h)
    g(0, "ENDSEC")
    g(0, "SECTION"); g(2, "TABLES")
    g(0, "TABLE"); g(2, "LTYPE"); g(70, 3)
    for name, desc, pattern in (("CONTINUOUS", "Solid", ()), ("DASHED", "__ __ __", (3.0, -1.5)),
                                ("CENTER", "____ . ____", (8.0, -1.5, 1.0, -1.5))):
        g(0, "LTYPE"); g(2, name); g(70, 0); g(3, desc); g(72, 65); g(73, len(pattern))
        g(40, f"{sum(abs(p) for p in pattern):g}")
        for p in pattern:
            g(49, f"{p:g}")
    g(0, "ENDTAB")
    layers = list(dict.fromkeys(_DXF_LAYERS.values()))
    g(0, "TABLE"); g(2, "LAYER"); g(70, len(layers))
    for name, color, ltype in layers:
        g(0, "LAYER"); g(2, name); g(70, 0); g(62, color); g(6, ltype)
    g(0, "ENDTAB")
    g(0, "ENDSEC")
    g(0, "SECTION"); g(2, "ENTITIES")
    for pts, style in sh.lines:
        layer = _DXF_LAYERS[style][0]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            g(0, "LINE"); g(8, layer); g(10, f"{x0:.4f}"); g(20, f"{y0:.4f}"); g(30, 0)
            g(11, f"{x1:.4f}"); g(21, f"{y1:.4f}"); g(31, 0)
    for pts in sh.fills:
        a, b, c = pts[:3]
        g(0, "SOLID"); g(8, _DXF_LAYERS["thin"][0])
        for k, (x, y) in zip((10, 11, 12, 13), (a, b, c, c)):
            g(k, f"{x:.4f}"); g(k + 10, f"{y:.4f}"); g(k + 20, 0)
    for x, y, s, size, align, angle in sh.texts:
        g(0, "TEXT"); g(8, _DXF_LAYERS["text"][0]); g(10, f"{x:.4f}"); g(20, f"{y:.4f}"); g(30, 0)
        g(40, f"{size:.3f}"); g(1, s)
        if angle:
            g(50, f"{angle:g}")
        if align != "start":
            g(72, 1 if align == "middle" else 2)
            g(11, f"{x:.4f}"); g(21, f"{y:.4f}"); g(31, 0)
    g(0, "ENDSEC")
    g(0, "EOF")
    return "\n".join(o) + "\n"
