"""Catálogo de comandos de OpenSCAD que la interfaz sabe crear y editar.

Los nombres y parámetros salen del código fuente de OpenSCAD
(src/core/*.cc, llamadas a ``Builtins::init`` y ``Parameters::parse``).
Cada ``Spec`` describe un módulo: cómo se llama, qué parámetros acepta,
si tiene hijos y en qué pestaña de la cinta aparece.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class Param:
    name: str
    kind: str  # num, int, bool, vec2, vec3, str, choice, color, file, points2, points3, faces, matrix, expr
    default: Any = None
    optional: bool = False
    label: str = ""
    options: tuple = ()
    minimum: float = -1e9
    maximum: float = 1e9
    step: float = 1.0

    @property
    def title(self) -> str:
        return self.label or self.name


@dataclass(frozen=True)
class Spec:
    name: str
    label: str
    category: str
    container: bool
    params: tuple = ()
    level: str = "direct"  # direct | editor | experimental
    hint: str = ""
    positional: tuple = ()  # orden de los argumentos posicionales que acepta OpenSCAD

    def param(self, name: str) -> Optional[Param]:
        for p in self.params:
            if p.name == name:
                return p
        return None


FN = Param("$fn", "int", 64, optional=True, label="Resolución ($fn)", minimum=0, maximum=512)

SPECS: dict[str, Spec] = {}


def _add(spec: Spec) -> None:
    SPECS[spec.name] = spec


# --- Sólidos 3D -------------------------------------------------------------
_add(Spec("cube", "Cubo", "solid", False, (
    Param("size", "vec3", [10, 10, 10], label="Tamaño"),
    Param("center", "bool", False, label="Centrado"),
), positional=("size", "center")))
_add(Spec("sphere", "Esfera", "solid", False, (
    Param("r", "num", 10, label="Radio (r)", minimum=0),
    Param("d", "num", 20, optional=True, label="Diámetro (d)", minimum=0),
    FN,
), positional=("r",)))
_add(Spec("cylinder", "Cilindro", "solid", False, (
    Param("h", "num", 10, label="Altura (h)", minimum=0),
    Param("r", "num", 5, label="Radio (r)", minimum=0),
    Param("r1", "num", 5, optional=True, label="Radio inferior (r1)", minimum=0),
    Param("r2", "num", 2, optional=True, label="Radio superior (r2)", minimum=0),
    Param("d", "num", 10, optional=True, label="Diámetro (d)", minimum=0),
    Param("d1", "num", 10, optional=True, label="Diámetro inferior (d1)", minimum=0),
    Param("d2", "num", 4, optional=True, label="Diámetro superior (d2)", minimum=0),
    Param("center", "bool", False, label="Centrado"),
    FN,
), positional=("h", "r1", "r2", "center")))
_add(Spec("polyhedron", "Poliedro", "solid", False, (
    Param("points", "points3", [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0], [5, 5, 10]], label="Vértices"),
    Param("faces", "faces", [[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4], [1, 0, 3], [2, 1, 3]], label="Caras"),
    Param("convexity", "int", 1, optional=True, label="Convexidad", minimum=1),
), level="editor", positional=("points", "faces", "convexity")))

# --- Formas 2D --------------------------------------------------------------
_add(Spec("square", "Rectángulo", "shape2d", False, (
    Param("size", "vec2", [10, 10], label="Tamaño"),
    Param("center", "bool", False, label="Centrado"),
), positional=("size", "center")))
_add(Spec("circle", "Círculo", "shape2d", False, (
    Param("r", "num", 5, label="Radio (r)", minimum=0),
    Param("d", "num", 10, optional=True, label="Diámetro (d)", minimum=0),
    FN,
), positional=("r",)))
_add(Spec("polygon", "Polígono", "shape2d", False, (
    Param("points", "points2", [[0, 0], [20, 0], [10, 15]], label="Puntos"),
    Param("paths", "expr", None, optional=True, label="Caminos (paths)"),
    Param("convexity", "int", 1, optional=True, label="Convexidad", minimum=1),
), level="editor", positional=("points", "paths", "convexity")))
_add(Spec("text", "Texto", "shape2d", False, (
    Param("text", "str", "Hola", label="Texto"),
    Param("size", "num", 10, label="Tamaño", minimum=0),
    Param("font", "str", "Liberation Sans", optional=True, label="Fuente"),
    Param("halign", "choice", "left", optional=True, label="Alineación H", options=("left", "center", "right")),
    Param("valign", "choice", "baseline", optional=True, label="Alineación V", options=("top", "center", "baseline", "bottom")),
    Param("spacing", "num", 1, optional=True, label="Espaciado", step=0.1),
    Param("direction", "choice", "ltr", optional=True, label="Dirección", options=("ltr", "rtl", "ttb", "btt")),
    Param("language", "str", "es", optional=True, label="Idioma"),
    Param("script", "str", "latin", optional=True, label="Escritura"),
    FN,
), positional=("text", "size", "font")))
_add(Spec("offset", "Desfase", "shape2d", True, (
    Param("r", "num", 1, label="Radio (r)", step=0.5),
    Param("delta", "num", 1, optional=True, label="Delta", step=0.5),
    Param("chamfer", "bool", False, optional=True, label="Chaflán"),
    FN,
), positional=("r",), hint="Se aplica a formas 2D."))

# --- Transformaciones -------------------------------------------------------
_add(Spec("translate", "Mover", "transform", True, (
    Param("v", "vec3", [0, 0, 0], label="Desplazamiento"),
), positional=("v",)))
_add(Spec("rotate", "Rotar", "transform", True, (
    Param("a", "vec3", [0, 0, 0], label="Ángulos (°)", step=5),
    Param("v", "vec3", [0, 0, 1], optional=True, label="Eje (v)"),
), positional=("a", "v")))
_add(Spec("scale", "Escalar", "transform", True, (
    Param("v", "vec3", [1, 1, 1], label="Factor", step=0.1),
), positional=("v",)))
_add(Spec("mirror", "Espejo", "transform", True, (
    Param("v", "vec3", [1, 0, 0], label="Normal del plano"),
), positional=("v",)))
_add(Spec("resize", "Redimensionar", "transform", True, (
    Param("newsize", "vec3", [10, 10, 10], label="Nuevo tamaño"),
    Param("auto", "bool", False, optional=True, label="Proporcional (auto)"),
    Param("convexity", "int", 1, optional=True, label="Convexidad", minimum=1),
), positional=("newsize", "auto", "convexity")))
_add(Spec("multmatrix", "Matriz", "transform", True, (
    Param("m", "matrix", [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], label="Matriz 4×4"),
), level="editor", positional=("m",)))
_add(Spec("color", "Color", "transform", True, (
    Param("c", "color", "SteelBlue", label="Color"),
    Param("alpha", "num", 1.0, optional=True, label="Opacidad", minimum=0, maximum=1, step=0.1),
), positional=("c", "alpha")))

# --- Booleanas --------------------------------------------------------------
_add(Spec("union", "Unir", "bool", True, hint="Une todos los hijos."))
_add(Spec("difference", "Restar", "bool", True, hint="El primer hijo es la base; los demás se restan."))
_add(Spec("intersection", "Intersecar", "bool", True, hint="Deja solo lo común a todos los hijos."))
_add(Spec("group", "Agrupar", "bool", True, hint="Agrupa sin operar (equivale a unión implícita)."))

# --- 2D → 3D ----------------------------------------------------------------
_add(Spec("linear_extrude", "Extruir", "extrude", True, (
    Param("height", "num", 10, label="Altura", minimum=0),
    Param("center", "bool", False, label="Centrado"),
    Param("twist", "num", 0, optional=True, label="Giro (°)", step=5),
    Param("scale", "num", 1, optional=True, label="Escala final", step=0.1),
    Param("slices", "int", 20, optional=True, label="Rebanadas", minimum=1),
    Param("segments", "int", 0, optional=True, label="Segmentos", minimum=0),
    Param("v", "vec3", [0, 0, 1], optional=True, label="Dirección (v)"),
    FN,
), positional=("height",)))
_add(Spec("rotate_extrude", "Revolución", "extrude", True, (
    Param("angle", "num", 360, label="Ángulo (°)", minimum=-360, maximum=360, step=15),
    Param("start", "num", 0, optional=True, label="Inicio (°)", step=15),
    Param("convexity", "int", 2, optional=True, label="Convexidad", minimum=1),
    FN,
), positional=("angle",)))
_add(Spec("projection", "Proyección", "extrude", True, (
    Param("cut", "bool", False, label="Corte en z=0 (cut)"),
    Param("convexity", "int", 1, optional=True, label="Convexidad", minimum=1),
), positional=("cut",)))

# --- Avanzado ---------------------------------------------------------------
_add(Spec("hull", "Envolvente", "adv", True, hint="Envolvente convexa de los hijos."))
_add(Spec("minkowski", "Minkowski", "adv", True, (
    Param("convexity", "int", 1, optional=True, label="Convexidad", minimum=1),
), hint="Suma de Minkowski: útil para redondear aristas. Puede ser lenta."))
_add(Spec("fill", "Rellenar", "adv", True, hint="Rellena los huecos de una forma 2D."))
_add(Spec("render", "Forzar render", "adv", True, (
    Param("convexity", "int", 1, optional=True, label="Convexidad", minimum=1),
)))
_add(Spec("roof", "Techo", "adv", True, (
    Param("method", "choice", "voronoi", label="Método", options=("voronoi", "straight")),
    Param("convexity", "int", 1, optional=True, label="Convexidad", minimum=1),
), level="experimental", hint="Requiere activar la función experimental 'roof'."))

# --- Importar ---------------------------------------------------------------
_add(Spec("import", "Importar", "imp", False, (
    Param("file", "file", "", label="Archivo"),
    Param("center", "bool", False, optional=True, label="Centrado"),
    Param("convexity", "int", 1, optional=True, label="Convexidad", minimum=1),
    Param("layer", "str", "", optional=True, label="Capa (DXF/SVG)"),
    Param("origin", "vec2", [0, 0], optional=True, label="Origen (DXF)"),
    Param("scale", "num", 1, optional=True, label="Escala (DXF)", step=0.1),
    Param("dpi", "num", 96, optional=True, label="DPI (SVG)"),
    Param("id", "str", "", optional=True, label="Id (SVG)"),
), level="editor", positional=("file", "layer", "convexity", "origin", "scale")))
_add(Spec("surface", "Superficie", "imp", False, (
    Param("file", "file", "", label="Archivo"),
    Param("center", "bool", False, label="Centrado"),
    Param("invert", "bool", False, optional=True, label="Invertir"),
    Param("convexity", "int", 1, optional=True, label="Convexidad", minimum=1),
), level="editor", positional=("file", "center", "convexity")))


# Comandos de control: existen en OpenSCAD pero solo se editan como código.
CONTROL_KEYWORDS = ("for", "intersection_for", "if", "let", "echo", "assert", "children",
                    "module", "function", "include", "use", "each")

CATEGORIES = (
    ("solid", "Sólidos 3D", "Crea la pieza con valores por defecto. Si hay una operación o "
     "transformación seleccionada, la pieza se añade dentro de ella."),
    ("shape2d", "Formas 2D", "Perfiles 2D para extruir, o para exportar a SVG / DXF."),
    ("transform", "Transformar", "Envuelve las piezas seleccionadas en la transformación."),
    ("bool", "Booleanas", "Selecciona dos o más piezas (Ctrl+clic). La primera en el árbol es la base."),
    ("extrude", "2D → 3D", "Envuelve el perfil 2D seleccionado: lo convierte en sólido o al revés."),
    ("adv", "Avanzado", "roof() es experimental: actívalo con --enable=roof en OpenSCAD."),
    ("imp", "Importar", "Abre un selector de archivo: STL, OFF, 3MF, AMF, OBJ, SVG, DXF o imagen."),
)


def specs_in(category: str) -> list[Spec]:
    return [s for s in SPECS.values() if s.category == category]


# Iconos: trazos SVG en una caja de 24×24 (los mismos del mockup).
ICONS = {
    "cube": "M12 3l8 4.5v9L12 21l-8-4.5v-9z M12 12l8-4.5 M12 12v9 M12 12L4 7.5",
    "sphere": "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M3 12c0 2.5 4 4.5 9 4.5s9-2 9-4.5",
    "cylinder": "M5 6c0-1.7 3.1-3 7-3s7 1.3 7 3v12c0 1.7-3.1 3-7 3s-7-1.3-7-3z M5 6c0 1.7 3.1 3 7 3s7-1.3 7-3",
    "polyhedron": "M12 3l8 6-3 11H7L4 9z M12 3l-2 8 M10 11L4 9 M10 11l7 9 M10 11l10-2",
    "square": "M5 5h14v14H5z",
    "circle": "M12 4a8 8 0 1 0 0 16a8 8 0 1 0 0-16z",
    "polygon": "M12 3l9 7-4 10H7L3 10z",
    "text": "M5 6V4h14v2 M12 4v16 M9 20h6",
    "offset": "M9 9h6v6H9z M4 7a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3z",
    "translate": "M12 3v18 M3 12h18 M12 3l-3 3 M12 3l3 3 M21 12l-3-3 M21 12l-3 3 M12 21l-3-3 M12 21l3-3 M3 12l3-3 M3 12l3 3",
    "rotate": "M20 12a8 8 0 1 1-2.3-5.7 M20 4v4h-4",
    "scale": "M4 20L20 4 M14 4h6v6 M10 20H4v-6",
    "mirror": "M12 3v18 M9 6L4 18h5z M15 6l5 12h-5z",
    "resize": "M4 4h6 M4 4v6 M20 20h-6 M20 20v-6 M8 8h8v8H8z",
    "multmatrix": "M7 4H4v16h3 M17 4h3v16h-3 M9 9h.01 M15 9h.01 M9 15h.01 M15 15h.01",
    "color": "M12 3c4 5 6 8 6 11a6 6 0 0 1-12 0c0-3 2-6 6-11z",
    "union": "M9 6a6 6 0 1 0 0 12a6 6 0 1 0 0-12z M15 6a6 6 0 1 0 0 12a6 6 0 1 0 0-12z",
    "difference": "M9 6a6 6 0 1 0 0 12a6 6 0 1 0 0-12z M15 7.5a6 6 0 0 1 0 9",
    "intersection": "M12 7.2a6 6 0 0 1 0 9.6a6 6 0 0 1 0-9.6z M9 6a6 6 0 1 0 0 12 M15 6a6 6 0 1 1 0 12",
    "group": "M3 3h18v18H3z M7 7h5v5H7z M12 12h5v5h-5z",
    "linear_extrude": "M6 20h12 M8 20V9h8v11 M12 3v4 M10 5l2-2 2 2",
    "rotate_extrude": "M8 4v16 M8 4c6 0 10 3 10 8s-4 8-10 8 M3 9l2 3-2 3",
    "projection": "M12 3l7 4v6l-7 4-7-4V7z M5 21h14 M12 17v4",
    "hull": "M4 16l5-11 11 5-4 10z",
    "minkowski": "M5 9a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v6a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4z M10 10h4v4h-4z",
    "fill": "M5 5h14v14H5z M5 13l8-8 M5 19L19 5 M11 19l8-8",
    "render": "M12 3l8 4.5v9L12 21l-8-4.5v-9z M8 12l3 3 5-6",
    "roof": "M3 18L12 6l9 12z M12 6v12",
    "import": "M12 3v12 M8 11l4 4 4-4 M4 17v3h16v-3",
    "surface": "M3 18l4-6 4 3 4-7 6 10z",
    # Iconos de interfaz
    "raw": "M8 7l-5 5 5 5 M16 7l5 5-5 5",
    "comment": "M4 5h16v11H9l-5 4z",
    "new": "M6 3h8l4 4v14H6z M14 3v4h4",
    "open": "M3 7h6l2 2h10v10H3z",
    "save": "M5 3h11l3 3v15H5z M8 3v5h7V3 M8 21v-7h8v7",
    "undo": "M9 14L4 9l5-5 M4 9h11a5 5 0 0 1 0 10h-3",
    "redo": "M15 14l5-5-5-5 M20 9H9a5 5 0 0 0 0 10h3",
    "preview": "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6z",
    "render_action": "M12 3l8 4.5v9L12 21l-8-4.5v-9z M12 12v9 M12 12l8-4.5 M12 12L4 7.5",
    "export": "M12 15V3 M8 7l4-4 4 4 M4 15v5h16v-5",
    "delete": "M4 7h16 M9 7V4h6v3 M6 7l1 13h10l1-13",
    "up": "M12 19V5 M6 11l6-6 6 6",
    "down": "M12 5v14 M6 13l6 6 6-6",
    "outdent": "M20 6H9 M20 12H9 M20 18H9 M6 9l-3 3 3 3",
    "unwrap": "M4 4h6 M4 4v6 M20 20h-6 M20 20v-6 M9 15l6-6",
    "duplicate": "M8 8h12v12H8z M4 16V4h12",
    "lock": "M6 11h12v9H6z M9 11V8a3 3 0 0 1 6 0v3",
    "sketch": "M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25z M20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z",
    "hardware": "M7 2h10v4H7z M9 6v12l3 4 3-4V6 M7 10h10 M7 14h10",
}
