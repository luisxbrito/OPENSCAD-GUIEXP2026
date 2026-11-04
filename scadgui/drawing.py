"""Generador de planos técnicos 2D (vistas ortogonales, isométrica, marco y cajetín)."""

from __future__ import annotations

import datetime
import math
from typing import Optional

from .i18n import tr
from .model import format_string


SHEET_SIZES = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
}

# Giro que lleva cada vista al plano XY antes de projection(). Se aplica de derecha a izquierda,
# como en OpenSCAD. Sistema europeo (ISO E): la planta va debajo del alzado y el perfil
# izquierdo a la derecha del alzado.
VIEW_TRANSFORMS = {
    "front": "rotate([-90, 0, 0])",                         # mirando hacia +Y: X a la derecha, Z arriba
    "top": "",                                              # desde arriba: X a la derecha, Y arriba
    "side": "rotate([-90, 0, 0]) rotate([0, 0, 90])",       # perfil izquierdo (desde -X): -Y a la derecha, Z arriba
    "isometric": "rotate([-54.7356, 0, 0]) rotate([0, 0, -45])",  # desde (+X, -Y, +Z), Z hacia arriba
}
# Los mismos giros, como pares (eje, grados) en el orden en que se aplican al punto.
_VIEW_TURNS = {
    "front": (("x", -90),),
    "top": (),
    "side": (("z", 90), ("x", -90)),
    "isometric": (("z", -45), ("x", -54.7356)),
}

# Escalas normalizadas (ISO 5455), de mayor a menor. La automática coge la mayor que cabe.
STANDARD_SCALES = (10.0, 5.0, 2.0, 1.0, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01)

FRAME = 10.0          # margen de la hoja hasta el recuadro
INNER = 5.0           # aire mínimo entre el recuadro y las vistas, y entre vistas
LABEL_GAP = 3.0       # del borde de la vista a la línea base del rótulo... más su altura
LABEL_SIZE = 3.5
LABEL_BAND = LABEL_GAP + LABEL_SIZE + 1.5   # alto que se reserva bajo cada vista para su rótulo
TITLE_W, TITLE_H = 110.0, 36.0              # cajetín, en la esquina inferior derecha del recuadro
DEFAULT_BOX = ((-25.0, -25.0, -25.0), (25.0, 25.0, 25.0))

Box = tuple[tuple[float, float, float], tuple[float, float, float]]


def _turn(p, axis: str, deg: float):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    x, y, z = p
    if axis == "x":
        return x, c * y - s * z, s * y + c * z
    return c * x - s * y, s * x + c * y, z


def view_extent(box: Box, key: str) -> tuple[float, float, float, float]:
    """Rectángulo (x0, y0, x1, y1) que ocupa la vista en la hoja a escala 1, antes de colocarla.
    Se calcula con las 8 esquinas de la caja: es exacto en las vistas ortogonales y, en la
    isométrica, un rectángulo que la contiene seguro."""
    (ax, ay, az), (bx, by, bz) = box
    pts = []
    for p in ((x, y, z) for x in (ax, bx) for y in (ay, by) for z in (az, bz)):
        for axis, deg in _VIEW_TURNS[key]:
            p = _turn(p, axis, deg)
        pts.append(p)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def scale_label(scale: float) -> str:
    return f"{scale:g}:1" if scale >= 1.0 else f"1:{1.0 / scale:g}"


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def view_labels() -> dict[str, str]:
    return {"front": tr("Alzado").upper(), "top": tr("Planta").upper(),
            "side": tr("Perfil izquierdo").upper(), "isometric": tr("Isométrica").upper()}


def label_width(text: str) -> float:
    """Ancho aproximado del rótulo (Liberation Sans en mayúsculas ronda 0.7 veces la altura por letra)."""
    return 0.72 * LABEL_SIZE * len(text)


def _layout(box: Box, w: float, h: float, scale: float, keys: list[str], border: bool):
    """Coloca las vistas a una escala dada. Devuelve ({vista: (cx, cy, rect)}, cabe).
    cx, cy es dónde cae el centro de la vista en la hoja y rect lo que ocupa con su rótulo, que
    puede ser más ancho que la vista."""
    ext = {k: view_extent(box, k) for k in keys}
    labels = view_labels()
    size = {k: (max((e[2] - e[0]) * scale, label_width(labels[k])), (e[3] - e[1]) * scale) for k, e in ext.items()}
    x0, y0, x1, y1 = FRAME + INNER, FRAME + INNER, w - FRAME - INNER, h - FRAME - INNER

    cols = [[k for k in ("front", "top") if k in keys], [k for k in ("side", "isometric") if k in keys]]
    rows = [[k for k in ("front", "side") if k in keys], [k for k in ("top", "isometric") if k in keys]]
    col_w = [max((size[k][0] for k in c), default=0.0) for c in cols]
    row_h = [max((size[k][1] + LABEL_BAND for k in r), default=0.0) for r in rows]
    used_c = [c for c, cw in zip(range(2), col_w) if cw > 0]
    used_r = [r for r, rh in zip(range(2), row_h) if rh > 0]

    # El aire que sobra se reparte a partes iguales: márgenes y separación entre vistas.
    gap_x = (x1 - x0 - sum(col_w)) / (len(used_c) + 1)
    gap_y = (y1 - y0 - sum(row_h)) / (len(used_r) + 1)
    fits = gap_x >= 0 and gap_y >= 0
    centers_x, x = {}, x0
    for c in used_c:
        x += gap_x
        centers_x[c] = x + col_w[c] / 2
        x += col_w[c]
    tops, y = {}, y1
    for r in used_r:
        y -= gap_y
        tops[r] = y
        y -= row_h[r]
    # Dentro de una fila, todas las vistas comparten el centro vertical (alzado y perfil quedan a
    # la misma altura); dentro de una columna, el horizontal (alzado y planta, alineados).
    place = {}
    for k in keys:
        c = 0 if k in cols[0] else 1
        r = 0 if k in rows[0] else 1
        sw, sh = size[k]
        cx, cy = centers_x[c], tops[r] - (row_h[r] - LABEL_BAND) / 2
        place[k] = [cx, cy, (cx - sw / 2, cy - sh / 2 - LABEL_BAND, cx + sw / 2, cy + sh / 2)]

    if border:
        # El cajetín ocupa la esquina inferior derecha: una vista de la fila de abajo que lo
        # pisaría se sube lo justo, sin tocar la de encima. Si no hay sitio, a esa escala no cabe.
        title = (w - FRAME - TITLE_W - INNER, 0.0, w, FRAME + TITLE_H + INNER)
        for k in rows[1]:
            cx, cy, rect = place[k]
            if not _overlap(rect, title):
                continue
            lift = title[3] - rect[1]
            rect = (rect[0], rect[1] + lift, rect[2], rect[3] + lift)
            above = [place[o][2] for o in rows[0] if (o in cols[0]) == (k in cols[0])]
            if rect[3] > y1 or any(rect[3] + INNER > a[1] for a in above):
                fits = False
            place[k] = [cx, cy + lift, rect]
    rects = [p[2] for p in place.values()]
    if any(_overlap(a, b) for i, a in enumerate(rects) for b in rects[i + 1:]):
        fits = False
    return {k: (p[0], p[1], p[2]) for k, p in place.items()}, fits


def plan_sheet(box: Optional[Box], sheet_size: str = "A4", scale: float = 0.0,
               views: Optional[dict[str, bool]] = None, include_border: bool = True):
    """Escala y posición de cada vista. Con scale = 0 elige la mayor escala normalizada con la que
    todo cabe. Devuelve (escala, {vista: (cx, cy, rect)}, cabe)."""
    box = box or DEFAULT_BOX
    if views is None:
        views = {"top": True, "front": True, "side": True, "isometric": True}
    keys = [k for k in ("front", "top", "side", "isometric") if views.get(k, True)]
    w, h = SHEET_SIZES.get(sheet_size, SHEET_SIZES["A4"])
    if scale and scale > 0:
        place, fits = _layout(box, w, h, scale, keys, include_border)
        return scale, place, fits
    for s in STANDARD_SCALES:
        place, fits = _layout(box, w, h, s, keys, include_border)
        if fits:
            return s, place, True
    return s, place, False


def generate_technical_drawing_code(
    target_code: str,
    title: str = "",
    author: str = "",
    sheet_size: str = "A4",
    scale: float = 0.0,
    views: Optional[dict[str, bool]] = None,
    include_border: bool = True,
    box: Optional[Box] = None,
) -> str:
    """Genera código OpenSCAD para una lámina técnica 2D completa.

    ``box`` es la caja del modelo (mínimo y máximo en X, Y, Z): con ella cada vista se centra en
    su sitio y la escala automática (scale = 0) se ajusta a la hoja. Los rótulos de la lámina
    (vistas, cajetín) salen en el idioma de la interfaz.
    """
    if views is None:
        views = {"top": True, "front": True, "side": True, "isometric": True}
    box = box or DEFAULT_BOX
    scale, place, _ = plan_sheet(box, sheet_size, scale, views, include_border)

    w, h = SHEET_SIZES.get(sheet_size, SHEET_SIZES["A4"])
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    clean_title = " ".join(title.split()) or tr("Plano técnico")
    clean_author = " ".join(author.split()) or "OpenSCAD GUI"
    author_line = f"{tr('Diseñador:')} {clean_author}"
    scale_line = f"{tr('Escala:')} {scale_label(scale)}  ·  {sheet_size}  ·  {date_str}"

    # include/use no pueden ir dentro de un módulo: se dejan arriba del todo.
    head, body = [], []
    for line in target_code.strip().splitlines():
        stripped = line.lstrip()
        (head if stripped.startswith(("include ", "include<", "use ", "use<")) else body).append(line)

    lines = ["// " + tr("Lámina de dibujo técnico generada con OpenSCAD GUI Mejorada"), *head, "$fn = 48;", "",
             "module __modelo_base__() {"]
    lines += ["  " + line if line.strip() else "" for line in body]
    lines += ["}", ""]

    if include_border:
        tx = w - FRAME - TITLE_W
        lines.extend([
            f"// --- {tr('Marco exterior y margen')} ---",
            "difference() {",                                      # borde de la hoja, fino
            f"  square([{w}, {h}]);",
            f"  translate([0.2, 0.2]) square([{w - 0.4}, {h - 0.4}]);",
            "}",
            "difference() {",                                      # recuadro a 10 mm
            f"  translate([{FRAME}, {FRAME}]) square([{w - 2 * FRAME}, {h - 2 * FRAME}]);",
            f"  translate([{FRAME + 0.5}, {FRAME + 0.5}]) square([{w - 2 * FRAME - 1}, {h - 2 * FRAME - 1}]);",
            "}",
            "",
            f"// --- {tr('Cajetín técnico')} ---",
            f"translate([{tx}, {FRAME}]) {{",
            "  difference() {",
            f"    square([{TITLE_W}, {TITLE_H}]);",
            f"    translate([0.5, 0.5]) square([{TITLE_W - 1}, {TITLE_H - 1}]);",
            "  }",
            f"  translate([6, 24]) text({format_string(clean_title)}, size = 4.5);",
            f"  translate([6, 15]) text({format_string(author_line)}, size = 3);",
            f"  translate([6, 6]) text({format_string(scale_line)}, size = 2.8);",
            "}",
            "",
        ])

    labels = view_labels()

    def num(v: float) -> str:
        return f"{round(v, 3):g}"

    lines.append(f"// --- {tr('Proyecciones 2D (sistema europeo)')} ---")
    for key in ("front", "top", "side", "isometric"):
        if key not in place:
            continue
        cx, cy, _ = place[key]
        ex = view_extent(box, key)
        mx, my = (ex[0] + ex[2]) / 2 * scale, (ex[1] + ex[3]) / 2 * scale
        rot = VIEW_TRANSFORMS[key]
        model = f"{rot} __modelo_base__()" if rot else "__modelo_base__()"
        # El grupo lleva el centro de la vista a su sitio; el rótulo va centrado debajo.
        lines += [
            f"translate([{num(cx - mx)}, {num(cy - my)}]) {{",
            f"  scale([{scale}, {scale}, 1]) projection(cut = false) {model};",
            f"  translate([{num(mx)}, {num(ex[1] * scale - LABEL_GAP - LABEL_SIZE)}]) "
            f'text({format_string(labels[key])}, size = {LABEL_SIZE}, halign = "center");',
            "}",
        ]

    return "\n".join(lines) + "\n"
