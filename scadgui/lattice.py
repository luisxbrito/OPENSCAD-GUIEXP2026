"""Estructuras aligeradas, lattice celular y superficies matemáticas periódicas TPMS (Gyroid, Schwarz P, Honeycomb, Voronoi).

Cálculo de densidad relativa, masa según material y generación de módulos paramétricos OpenSCAD.
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from .i18n import tr
from .model import Node, RawCode, new_id

PATTERNS = ("gyroid", "schwarz_p", "honeycomb", "voronoi")

MATERIALS = {
    "pla": (tr("PLA"), 1.24),
    "petg": (tr("PETG"), 1.27),
    "abs": (tr("ABS"), 1.04),
    "resin": (tr("Resina"), 1.15),
    "nylon": (tr("Nylon PA12"), 1.01),
    "aluminum": (tr("Aluminio"), 2.67),
    "titanium": (tr("Titanio"), 4.43),
}


def pattern_name(pattern: str) -> str:
    """Nombre descriptivo del patrón."""
    names = {
        "gyroid": tr("Giroide (Gyroid TPMS)"),
        "schwarz_p": tr("Schwarz P (TPMS)"),
        "honeycomb": tr("Panal de abeja (Honeycomb)"),
        "voronoi": tr("Voronoi 3D celular"),
    }
    return names.get(pattern, pattern)


def estimate_metrics(dx: float, dy: float, dz: float,
                     cell_size: float, wall_thick: float,
                     has_shell: bool = False, shell_thick: float = 1.2,
                     has_drain: bool = False, drain_d: float = 4.0,
                     material_key: str = "pla") -> dict:
    """Calcula volumen sólido, volumen aligerado, masa estimada y ahorro de material."""
    dx = max(1.0, dx)
    dy = max(1.0, dy)
    dz = max(1.0, dz)
    cell_size = max(1.0, cell_size)
    wall_thick = max(0.2, min(wall_thick, cell_size * 0.9))

    total_vol_mm3 = dx * dy * dz
    total_vol_cm3 = total_vol_mm3 / 1000.0

    _, density_g_cm3 = MATERIALS.get(material_key, MATERIALS["pla"])
    solid_mass_g = total_vol_cm3 * density_g_cm3

    # Densidad relativa del núcleo celular según relación t / lambda
    ratio = wall_thick / cell_size
    rel_density = min(0.90, max(0.08, ratio * 2.6))

    if has_shell and dx > 2 * shell_thick and dy > 2 * shell_thick and dz > 2 * shell_thick:
        inner_dx = dx - 2 * shell_thick
        inner_dy = dy - 2 * shell_thick
        inner_dz = dz - 2 * shell_thick
        inner_vol_mm3 = inner_dx * inner_dy * inner_dz
        shell_vol_mm3 = total_vol_mm3 - inner_vol_mm3
        infill_vol_mm3 = inner_vol_mm3 * rel_density

        # Descontar agujeros de drenaje si están activos (2 agujeros pasantes mínimos)
        drain_vol_mm3 = 0.0
        if has_drain and drain_d > 0:
            drain_vol_mm3 = 2.0 * (math.pi * ((drain_d / 2.0) ** 2) * shell_thick)

        lattice_vol_mm3 = max(0.0, shell_vol_mm3 + infill_vol_mm3 - drain_vol_mm3)
    else:
        lattice_vol_mm3 = total_vol_mm3 * rel_density

    lattice_vol_cm3 = lattice_vol_mm3 / 1000.0
    lattice_mass_g = lattice_vol_cm3 * density_g_cm3

    savings_pct = 0.0
    if solid_mass_g > 0:
        savings_pct = max(0.0, min(95.0, (1.0 - (lattice_mass_g / solid_mass_g)) * 100.0))

    return {
        "solid_volume_cm3": total_vol_cm3,
        "solid_mass_g": solid_mass_g,
        "lattice_volume_cm3": lattice_vol_cm3,
        "lattice_mass_g": lattice_mass_g,
        "savings_pct": savings_pct,
        "relative_density_pct": (lattice_vol_mm3 / total_vol_mm3) * 100.0 if total_vol_mm3 > 0 else 0.0,
    }


def generate_scad_code(dx: float, dy: float, dz: float,
                       cell_size: float, wall_thick: float,
                       pattern: str = "gyroid",
                       has_shell: bool = False, shell_thick: float = 1.2,
                       has_drain: bool = False, drain_d: float = 4.0,
                       cx: float = 0.0, cy: float = 0.0, cz: float = 0.0,
                       solid_code: Optional[str] = None,
                       solid_name: str = "") -> str:
    """Genera código OpenSCAD paramétrico modular con la estructura aligerada."""
    p_upper = pattern.upper()
    header_comment = f"// {tr('Estructura aligerada paramétrica')} ({p_upper})"
    if solid_name:
        sub_comment = f"// {tr('Aplicada a:')} {solid_name}"
    else:
        sub_comment = f"// {tr('Bloque independiente')}"

    code_lines = [
        header_comment,
        sub_comment,
        f"// {tr('Dimensiones:')} {dx:.1f} x {dy:.1f} x {dz:.1f} mm | {tr('Celda:')} {cell_size:.1f} mm | {tr('Espesor:')} {wall_thick:.1f} mm",
        "",
        f"dim_x = {dx:.2f};",
        f"dim_y = {dy:.2f};",
        f"dim_z = {dz:.2f};",
        f"centro_x = {cx:.2f};",
        f"centro_y = {cy:.2f};",
        f"centro_z = {cz:.2f};",
        f"tam_celda = {cell_size:.2f};",
        f"espesor_pared = {wall_thick:.2f};",
        "",
    ]

    if pattern == "gyroid":
        code_lines.extend([
            "// Celda unitaria de Giroide (TPMS triplemente periódica mínima)",
            "module celda_gyroid(s = 10, t = 1.2) {",
            "  intersection() {",
            "    cube([s, s, s], center = true);",
            "    union() {",
            "      rotate([45, 35.26, 0]) cylinder(r = s * 0.65, h = s * 1.5, center = true, $fn = 12);",
            "      rotate([-45, 35.26, 0]) cylinder(r = s * 0.65, h = s * 1.5, center = true, $fn = 12);",
            "    }",
            "  }",
            "}",
            "",
            "module nucleo_lattice(dim, s, t) {",
            "  nx = ceil(dim[0] / s);",
            "  ny = ceil(dim[1] / s);",
            "  nz = ceil(dim[2] / s);",
            "  intersection() {",
            "    cube(dim, center = true);",
            "    for (ix = [0 : nx - 1])",
            "      for (iy = [0 : ny - 1])",
            "        for (iz = [0 : nz - 1])",
            "          translate([(ix - (nx-1)/2) * s, (iy - (ny-1)/2) * s, (iz - (nz-1)/2) * s])",
            "            celda_gyroid(s, t);",
            "  }",
            "}",
        ])
    elif pattern == "schwarz_p":
        code_lines.extend([
            "// Celda unitaria Schwarz P (superficie mínima con canales ortogonales cruzados)",
            "module celda_schwarz_p(s = 10, t = 1.2) {",
            "  difference() {",
            "    cube([s, s, s], center = true);",
            "    cylinder(d = max(0.2, s - t), h = s + 1, center = true, $fn = 16);",
            "    rotate([90, 0, 0]) cylinder(d = max(0.2, s - t), h = s + 1, center = true, $fn = 16);",
            "    rotate([0, 90, 0]) cylinder(d = max(0.2, s - t), h = s + 1, center = true, $fn = 16);",
            "  }",
            "}",
            "",
            "module nucleo_lattice(dim, s, t) {",
            "  nx = ceil(dim[0] / s);",
            "  ny = ceil(dim[1] / s);",
            "  nz = ceil(dim[2] / s);",
            "  intersection() {",
            "    cube(dim, center = true);",
            "    for (ix = [0 : nx - 1])",
            "      for (iy = [0 : ny - 1])",
            "        for (iz = [0 : nz - 1])",
            "          translate([(ix - (nx-1)/2) * s, (iy - (ny-1)/2) * s, (iz - (nz-1)/2) * s])",
            "            celda_schwarz_p(s, t);",
            "  }",
            "}",
        ])
    elif pattern == "honeycomb":
        code_lines.extend([
            "// Núcleo celular de panal de abeja hexagonal (máxima resistencia a compresión Z)",
            "module nucleo_lattice(dim, s, t) {",
            "  r_cell = s / 1.7320508;",
            "  paso_x = 1.5 * r_cell;",
            "  paso_y = 1.7320508 * r_cell;",
            "  r_hole = max(0.1, (s - t) / 1.7320508);",
            "",
            "  linear_extrude(height = dim[2] + 0.1, center = true) {",
            "    difference() {",
            "      square([dim[0], dim[1]], center = true);",
            "      k_x = ceil(dim[0] / paso_x / 2) + 1;",
            "      k_y = ceil(dim[1] / paso_y / 2) + 1;",
            "      for (ix = [-k_x : k_x]) {",
            "        y_offset = (abs(ix) % 2 == 1) ? (paso_y / 2) : 0;",
            "        for (iy = [-k_y : k_y]) {",
            "          translate([ix * paso_x, iy * paso_y + y_offset])",
            "            circle(r = r_hole, $fn = 6);",
            "        }",
            "      }",
            "    }",
            "  }",
            "}",
        ])
    else:  # voronoi
        code_lines.extend([
            "// Núcleo celular trabecular biomimético tipo Voronoi 3D",
            "module celda_voronoi(s = 10, t = 1.2) {",
            "  difference() {",
            "    cube([s, s, s], center = true);",
            "    sphere(r = s * 0.45, $fn = 12);",
            "    for (a = [0, 90]) rotate([0, a, 45]) cylinder(r = s * 0.25, h = s * 1.5, center = true, $fn = 8);",
            "  }",
            "}",
            "",
            "module nucleo_lattice(dim, s, t) {",
            "  nx = ceil(dim[0] / s);",
            "  ny = ceil(dim[1] / s);",
            "  nz = ceil(dim[2] / s);",
            "  intersection() {",
            "    cube(dim, center = true);",
            "    for (ix = [0 : nx - 1])",
            "      for (iy = [0 : ny - 1])",
            "        for (iz = [0 : nz - 1])",
            "          translate([(ix - (nx-1)/2) * s, (iy - (ny-1)/2) * s, (iz - (nz-1)/2) * s])",
            "            celda_voronoi(s, t);",
            "  }",
            "}",
        ])

    code_lines.append("")
    code_lines.append("// Sólido original a procesar")
    if solid_code and solid_code.strip():
        indented_code = "\n".join("  " + ln for ln in solid_code.strip().splitlines())
        code_lines.append("module solido_original() {")
        code_lines.append(indented_code)
        code_lines.append("}")
    else:
        code_lines.extend([
            "module solido_original() {",
            "  cube([dim_x, dim_y, dim_z], center = true);",
            "}",
        ])

    code_lines.append("")
    code_lines.append("// Pieza final aligerada")

    if has_shell and dx > 2 * shell_thick and dy > 2 * shell_thick and dz > 2 * shell_thick:
        code_lines.extend([
            f"espesor_piel = {shell_thick:.2f};",
            "",
            "module solido_interior() {",
            "  sx = max(0.01, (dim_x - 2 * espesor_piel) / dim_x);",
            "  sy = max(0.01, (dim_y - 2 * espesor_piel) / dim_y);",
            "  sz = max(0.01, (dim_z - 2 * espesor_piel) / dim_z);",
            "  translate([centro_x, centro_y, centro_z])",
            "    scale([sx, sy, sz])",
            "      translate([-centro_x, -centro_y, -centro_z])",
            "        solido_original();",
            "}",
            "",
            "module pieza_aligerada() {",
            "  difference() {",
            "    union() {",
            "      // Piel sólida exterior",
            "      difference() {",
            "        solido_original();",
            "        solido_interior();",
            "      }",
            "      // Núcleo celular interno",
            "      intersection() {",
            "        solido_interior();",
            "        translate([centro_x, centro_y, centro_z])",
            "          nucleo_lattice([dim_x, dim_y, dim_z], tam_celda, espesor_pared);",
            "      }",
            "    }",
        ])
        if has_drain and drain_d > 0:
            code_lines.extend([
                f"    // Orificios de drenaje para resina SLA / polvo SLS (diam = {drain_d:.1f} mm)",
                f"    translate([centro_x, centro_y, centro_z - dim_z/2]) cylinder(d = {drain_d:.2f}, h = espesor_piel * 3, center = true, $fn = 24);",
                f"    translate([centro_x, centro_y, centro_z + dim_z/2]) cylinder(d = {drain_d:.2f}, h = espesor_piel * 3, center = true, $fn = 24);",
            ])
        code_lines.extend([
            "  }",
            "}",
            "",
            "pieza_aligerada();",
        ])
    else:
        code_lines.extend([
            "module pieza_aligerada() {",
            "  intersection() {",
            "    solido_original();",
            "    translate([centro_x, centro_y, centro_z])",
            "      nucleo_lattice([dim_x, dim_y, dim_z], tam_celda, espesor_pared);",
            "  }",
            "}",
            "",
            "pieza_aligerada();",
        ])

    return "\n".join(code_lines)


def create_lattice_node(dx: float, dy: float, dz: float,
                        cell_size: float, wall_thick: float,
                        pattern: str = "gyroid",
                        has_shell: bool = False, shell_thick: float = 1.2,
                        has_drain: bool = False, drain_d: float = 4.0,
                        cx: float = 0.0, cy: float = 0.0, cz: float = 0.0,
                        solid_code: Optional[str] = None,
                        target_name: str = "",
                        unique_fn: Optional[Callable[[str], str]] = None) -> RawCode:
    """Crea un nodo de código OpenSCAD con la estructura aligerada."""
    u_fn = unique_fn or (lambda s: s)
    code = generate_scad_code(
        dx, dy, dz, cell_size, wall_thick, pattern,
        has_shell, shell_thick, has_drain, drain_d,
        cx=cx, cy=cy, cz=cz,
        solid_code=solid_code, solid_name=target_name
    )
    p_name = pattern_name(pattern)
    if target_name:
        name = u_fn(tr("{name} (aligerado {pattern})").format(name=target_name, pattern=p_name))
    else:
        name = u_fn(tr("Estructura aligerada {pattern}").format(pattern=p_name))
    return RawCode(
        text=code,
        name=name,
        params={"size": (dx, dy, dz), "center": (cx, cy, cz)}
    )
