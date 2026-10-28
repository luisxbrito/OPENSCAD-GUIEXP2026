"""Generador de planos técnicos 2D (vistas ortogonales, isométrica, marco y cajetín)."""

from __future__ import annotations

import datetime
from typing import Any, Callable, Optional

from .model import AnyNode, Document, Node, RawCode, generate, make_node


SHEET_SIZES = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
}


def generate_technical_drawing_code(
    target_code: str,
    title: str = "Plano Técnico",
    author: str = "",
    sheet_size: str = "A4",
    scale: float = 1.0,
    views: Optional[dict[str, bool]] = None,
    include_border: bool = True,
) -> str:
    """Genera código OpenSCAD para una lámina técnica 2D completa."""
    if views is None:
        views = {"top": True, "front": True, "side": True, "isometric": True}

    w, h = SHEET_SIZES.get(sheet_size, SHEET_SIZES["A4"])
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    clean_title = title.replace('"', '\\"').strip() or "Plano Técnico"
    clean_author = author.replace('"', '\\"').strip() or "OpenSCAD GUI"
    scale_label = f"{scale:.2g}:1" if scale >= 1.0 else f"1:{int(round(1.0 / scale))}"

    lines = [
        "// Lámina de dibujo técnico generada con OpenSCAD GUI Mejorada",
        "$fn = 48;",
        "",
        "module __modelo_base__() {",
    ]
    for line in target_code.strip().splitlines():
        lines.append("  " + line)
    lines.append("}")
    lines.append("")

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
            f'  translate([6, 24]) text("{clean_title}", size = 4.5);',
            f'  translate([6, 15]) text("Diseñador: {clean_author}", size = 3);',
            f'  translate([6, 6]) text("Escala {scale_label}  ·  {sheet_size}  ·  {date_str}", size = 2.8);',
            "}",
            "",
        ])

    scale_str = f"{scale}, {scale}, 1"

    # Posiciones relativas en la lámina
    x_col1 = round(10.0 + (w - 20.0) * 0.28, 2)
    x_col2 = round(10.0 + (w - 20.0) * 0.70, 2)
    y_row1 = round(10.0 + (h - 20.0) * 0.32, 2)
    y_row2 = round(10.0 + (h - 20.0) * 0.72, 2)

    lines.append("// --- Proyecciones 2D ---")

    # 1. Alzado (Frontal) - Columna 1, Fila 1
    if views.get("front", True):
        lines.extend([
            f"translate([{x_col1}, {y_row1}]) {{",
            f"  scale([{scale_str}]) projection(cut = false) rotate([90, 0, 0]) __modelo_base__();",
            '  translate([0, -18]) text("ALZADO", size = 3.5, halign = "center");',
            "}",
        ])

    # 2. Planta (Superior) - Columna 1, Fila 2
    if views.get("top", True):
        lines.extend([
            f"translate([{x_col1}, {y_row2}]) {{",
            f"  scale([{scale_str}]) projection(cut = false) __modelo_base__();",
            '  translate([0, -18]) text("PLANTA", size = 3.5, halign = "center");',
            "}",
        ])

    # 3. Perfil (Lateral) - Columna 2, Fila 1
    if views.get("side", True):
        lines.extend([
            f"translate([{x_col2}, {y_row1}]) {{",
            f"  scale([{scale_str}]) projection(cut = false) rotate([0, 90, 0]) __modelo_base__();",
            '  translate([0, -18]) text("PERFIL", size = 3.5, halign = "center");',
            "}",
        ])

    # 4. Isométrica - Columna 2, Fila 2
    if views.get("isometric", True):
        lines.extend([
            f"translate([{x_col2}, {y_row2}]) {{",
            f"  scale([{scale_str}]) projection(cut = false) rotate([35.264, 0, 45]) __modelo_base__();",
            '  translate([0, -18]) text("ISOMÉTRICA", size = 3.5, halign = "center");',
            "}",
        ])

    return "\n".join(lines) + "\n"
