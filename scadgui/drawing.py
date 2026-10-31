"""Generador de planos técnicos 2D (vistas ortogonales, isométrica, marco y cajetín)."""

from __future__ import annotations

import datetime
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


def generate_technical_drawing_code(
    target_code: str,
    title: str = "",
    author: str = "",
    sheet_size: str = "A4",
    scale: float = 1.0,
    views: Optional[dict[str, bool]] = None,
    include_border: bool = True,
) -> str:
    """Genera código OpenSCAD para una lámina técnica 2D completa.

    Los rótulos de la lámina (vistas, cajetín) salen en el idioma de la interfaz.
    """
    if views is None:
        views = {"top": True, "front": True, "side": True, "isometric": True}

    w, h = SHEET_SIZES.get(sheet_size, SHEET_SIZES["A4"])
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    clean_title = " ".join(title.split()) or tr("Plano técnico")
    clean_author = " ".join(author.split()) or "OpenSCAD GUI"
    scale_label = f"{scale:.2g}:1" if scale >= 1.0 else f"1:{int(round(1.0 / scale))}"
    author_line = f"{tr('Diseñador:')} {clean_author}"
    scale_line = f"{tr('Escala:')} {scale_label}  ·  {sheet_size}  ·  {date_str}"

    # include/use no pueden ir dentro de un módulo: se dejan arriba del todo.
    head, body = [], []
    for line in target_code.strip().splitlines():
        stripped = line.lstrip()
        (head if stripped.startswith(("include ", "include<", "use ", "use<")) else body).append(line)

    lines = ["// Lámina de dibujo técnico generada con OpenSCAD GUI Mejorada", *head, "$fn = 48;", "",
             "module __modelo_base__() {"]
    lines += ["  " + line if line.strip() else "" for line in body]
    lines += ["}", ""]

    if include_border:
        lines.extend([
            "// --- Marco exterior y margen ---",
            "difference() {",
            f"  square([{w}, {h}]);",
            f"  translate([10, 10]) square([{w - 20}, {h - 20}]);",
            "}",
            "",
            "// --- Cajetín técnico ---",
            f"translate([{w - 120}, 10]) {{",
            "  difference() {",
            "    square([110, 36]);",
            "    translate([1, 1]) square([108, 34]);",
            "  }",
            f"  translate([6, 24]) text({format_string(clean_title)}, size = 4.5);",
            f"  translate([6, 15]) text({format_string(author_line)}, size = 3);",
            f"  translate([6, 6]) text({format_string(scale_line)}, size = 2.8);",
            "}",
            "",
        ])

    scale_str = f"{scale}, {scale}, 1"

    # Cuadrícula 2×2 dentro del margen: columna izquierda/derecha, fila superior/inferior.
    x_left = round(10.0 + (w - 20.0) * 0.28, 2)
    x_right = round(10.0 + (w - 20.0) * 0.70, 2)
    y_top = round(10.0 + (h - 20.0) * 0.72, 2)
    y_bottom = round(10.0 + (h - 20.0) * 0.32, 2)
    layout = (  # clave, posición, rótulo
        ("front", (x_left, y_top), tr("Alzado").upper()),
        ("top", (x_left, y_bottom), tr("Planta").upper()),
        ("side", (x_right, y_top), tr("Perfil izquierdo").upper()),
        ("isometric", (x_right, y_bottom), tr("Isométrica").upper()),
    )

    lines.append("// --- Proyecciones 2D (sistema europeo) ---")
    for key, (x, y), label in layout:
        if not views.get(key, True):
            continue
        rot = VIEW_TRANSFORMS[key]
        model = f"{rot} __modelo_base__()" if rot else "__modelo_base__()"
        lines += [
            f"translate([{x}, {y}]) {{",
            f"  scale([{scale_str}]) projection(cut = false) {model};",
            f'  translate([0, -18]) text({format_string(label)}, size = 3.5, halign = "center");',
            "}",
        ]

    return "\n".join(lines) + "\n"
