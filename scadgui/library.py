"""Módulos de OpenSCAD que la interfaz escribe en el archivo cuando hacen falta.

Redondear o achaflanar aristas no existe en OpenSCAD, así que se usan dos módulos propios
(``cube_edges`` y ``cylinder_edges``). Cuando el modelo los usa, ``model.generate()`` añade su
definición al final del archivo; al abrirlo, ``parser.parse()`` quita esa definición si no se
ha modificado. Así el ``.scad`` funciona en cualquier OpenSCAD sin bibliotecas externas.

Cada arista de un cubo se nombra por los dos lados que toca, con 0 para el lado mínimo y 1
para el máximo: "x1y1" es la arista vertical en X máximo e Y máximo; "y0z1", la arista paralela
a X en Y mínimo y Z máximo.
"""

from __future__ import annotations

import re

CUBE_EDGE_KEYS = (
    "x0y0", "x0y1", "x1y0", "x1y1",   # paralelas a Z (verticales)
    "y0z0", "y0z1", "y1z0", "y1z1",   # paralelas a X
    "x0z0", "x0z1", "x1z0", "x1z1",   # paralelas a Y
)
CYLINDER_EDGE_KEYS = ("bottom", "top")

CUBE_EDGES = '''module cube_edges(size = [10, 10, 10], center = false, edges = [], rounding = 0, chamfer = 0) {
  // Cubo con aristas redondeadas o achaflanadas (lo escribe OpenSCAD GUI Mejorada).
  // "x1y1" es la arista vertical en X máximo e Y máximo; 0 es el lado mínimo.
  // Es la intersección de tres prismas, uno por eje, cada uno con las esquinas de su perfil
  // tratadas: solo usa polígonos e intersecciones, que no fallan ni con CGAL ni con Manifold.
  s = is_list(size) ? size : [size, size, size];
  r = min(chamfer > 0 ? chamfer : rounding, min(s) / 2);
  function has(k) = len([for (x = edges) if (x == k) 1]) > 0;
  n = max(1, ceil(($fn > 0 ? max($fn, 3) : ceil(max(min(360 / $fa, r * 2 * PI / $fs), 5))) / 4));
  // Puntos de la esquina c = [lado en u, lado en v] de un rectángulo w x h, en sentido antihorario:
  // redondeada, un arco de n tramos; achaflanada, los dos extremos del arco; viva, la esquina.
  function corner(w, h, c, cut) =
    let(p = [c[0] * w, c[1] * h], o = p + r * [c[0] ? -1 : 1, c[1] ? -1 : 1],
        a0 = c == [0, 0] ? 180 : c == [1, 0] ? 270 : c == [1, 1] ? 0 : 90)
    !cut || r <= 0 ? [p]
    : [for (k = chamfer > 0 ? [0, n] : [0 : n]) o + r * [cos(a0 + 90 * k / n), sin(a0 + 90 * k / n)]];
  // Rectángulo w x h con las esquinas de keys tratadas, en orden (0,0), (1,0), (1,1), (0,1).
  module profile(w, h, keys) {
    polygon(concat(corner(w, h, [0, 0], has(keys[0])), corner(w, h, [1, 0], has(keys[1])),
                   corner(w, h, [1, 1], has(keys[2])), corner(w, h, [0, 1], has(keys[3]))));
  }
  translate(center ? -s / 2 : [0, 0, 0]) intersection() {
    linear_extrude(s.z) profile(s.x, s.y, ["x0y0", "x1y0", "x1y1", "x0y1"]);
    multmatrix([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]])
      linear_extrude(s.x) profile(s.y, s.z, ["y0z0", "y1z0", "y1z1", "y0z1"]);
    multmatrix([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0]])
      linear_extrude(s.y) profile(s.z, s.x, ["x0z0", "x0z1", "x1z1", "x1z0"]);
  }
}'''

CYLINDER_EDGES = '''module cylinder_edges(h = 10, r = 5, center = false, edges = [], rounding = 0, chamfer = 0) {
  // Cilindro con el borde "top" y/o "bottom" redondeado o achaflanado (lo escribe OpenSCAD GUI Mejorada).
  c = min(chamfer > 0 ? chamfer : rounding, r, h / 2);
  function cut(k) = c > 0 && len([for (x = edges) if (x == k) 1]) > 0 ? c : 0;
  b = cut("bottom");
  t = cut("top");
  e = 0.001;
  translate([0, 0, center ? -h / 2 : 0]) rotate_extrude() intersection() {
    square([r, h]);
    hull() {
      square([e, h]);
      if (b == 0) translate([r - e, 0]) square(e);
      else if (chamfer > 0) polygon([[r - b, 0], [r, b], [r - b, b]]);
      else translate([r - b, b]) circle(b);
      if (t == 0) translate([r - e, h - e]) square(e);
      else if (chamfer > 0) polygon([[r - t, h], [r - t, h - t], [r, h - t]]);
      else translate([r - t, h - t]) circle(t);
    }
  }
}'''

LIBRARY = {"cube_edges": CUBE_EDGES, "cylinder_edges": CYLINDER_EDGES}


def _normalized(text: str) -> str:
    return " ".join(text.split())


_NORMALIZED = {_normalized(code): name for name, code in LIBRARY.items()}


def library_name(text: str) -> str:
    """Nombre del módulo si ``text`` es una definición de la biblioteca sin cambios; si no, ''."""
    return _NORMALIZED.get(_normalized(text), "")


def needed_definitions(code: str) -> list[str]:
    """Definiciones que hay que añadir: módulos usados en ``code`` que no están definidos en él."""
    out = []
    for name, definition in LIBRARY.items():
        used = re.search(rf"(?<![\w$]){name}\s*\(", code)
        defined = re.search(rf"\bmodule\s+{name}\s*\(", code)
        if used and not defined:
            out.append(definition)
    return out
