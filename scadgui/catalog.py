"""Catálogo de comandos de OpenSCAD que la interfaz sabe crear y editar.

Los nombres y parámetros salen del código fuente de OpenSCAD
(src/core/*.cc, llamadas a ``Builtins::init`` y ``Parameters::parse``).
Cada ``Spec`` describe un módulo: cómo se llama, qué parámetros acepta,
si tiene hijos y en qué pestaña de la cinta aparece.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .library import CUBE_EDGE_KEYS, CYLINDER_EDGE_KEYS


@dataclass(frozen=True)
class Param:
    name: str
    kind: str  # num, int, bool, vec2, vec3, str, choice, color, file, points2, points3, faces, matrix, edges, expr
    default: Any = None
    optional: bool = False
    label: str = ""
    options: tuple = ()
    minimum: float = -1e9
    maximum: float = 1e9
    step: float = 1.0
    initial: bool = False  # opcional, pero la pieza nueva ya lo trae (r: se puede cambiar por d)
    translated: bool = False  # choice cuyos valores salen en el idioma de la interfaz (y en el código)

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
    # Qué escribe si no es un módulo de OpenSCAD: "for" (matrices) o "module" (un módulo propio
    # cuya definición añade la interfaz al archivo, ver library.py).
    keyword: str = ""

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
    Param("r", "num", 10, optional=True, initial=True, label="Radio (r)", minimum=0),
    Param("d", "num", 20, optional=True, label="Diámetro (d)", minimum=0),
    FN,
), positional=("r",)))
_add(Spec("cylinder", "Cilindro", "solid", False, (
    Param("h", "num", 10, label="Altura (h)", minimum=0),
    Param("r", "num", 5, optional=True, initial=True, label="Radio (r)", minimum=0),
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
    Param("r", "num", 5, optional=True, initial=True, label="Radio (r)", minimum=0),
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

# --- Repetir (matrices) -----------------------------------------------------
# No son módulos de OpenSCAD: cada una escribe un bucle for con una forma fija que el
# parser reconoce al reabrir el archivo (ver model.array_head y parser.try_array).
COUNT = dict(minimum=1, maximum=1000)
_add(Spec("linear_array", "Matriz lineal", "array", True, (
    Param("n", "int", 4, label="Copias", **COUNT),
    Param("step", "vec3", [20, 0, 0], label="Separación entre copias"),
), keyword="for", hint="Copias en línea recta. Genera for (i = ...) translate(i * [x, y, z])."))
_add(Spec("polar_array", "Matriz polar", "array", True, (
    Param("n", "int", 6, label="Copias", **COUNT),
    Param("angle", "num", 60, label="Ángulo entre copias (°)", step=5),
    Param("axis", "vec3", [0, 0, 1], label="Eje de giro"),
), keyword="for", hint="Copias girando alrededor de un eje que pasa por el origen. "
                       "Para cerrar la vuelta: ángulo = 360 / copias."))
_add(Spec("grid_array", "Matriz rectangular", "array", True, (
    Param("nx", "int", 3, label="Columnas", **COUNT),
    Param("ny", "int", 2, label="Filas", **COUNT),
    Param("step_x", "vec3", [20, 0, 0], label="Separación entre columnas"),
    Param("step_y", "vec3", [0, 20, 0], label="Separación entre filas"),
), keyword="for", hint="Copias en filas y columnas. Genera for (i = ..., j = ...) translate(...)."))

# --- Aristas redondeadas ----------------------------------------------------
# Se crean al redondear o achaflanar aristas en el visor; no tienen botón en la cinta.
_add(Spec("cube_edges", "Cubo con aristas", "edges", False, (
    Param("size", "vec3", [10, 10, 10], label="Tamaño"),
    Param("center", "bool", False, label="Centrado"),
    Param("edges", "edges", [], label="Aristas", options=CUBE_EDGE_KEYS),
    Param("rounding", "num", 2, optional=True, label="Radio de redondeo", minimum=0, step=0.5),
    Param("chamfer", "num", 1, optional=True, label="Chaflán", minimum=0, step=0.5),
    FN,
), keyword="module", positional=("size", "center", "edges", "rounding", "chamfer"),
    hint="Cubo con las aristas elegidas redondeadas o achaflanadas. Si se indica chaflán, manda sobre el redondeo."))
_add(Spec("cylinder_edges", "Cilindro con bordes", "edges", False, (
    Param("h", "num", 10, label="Altura (h)", minimum=0),
    Param("r", "num", 5, label="Radio (r)", minimum=0),
    Param("center", "bool", False, label="Centrado"),
    Param("edges", "edges", [], label="Bordes", options=CYLINDER_EDGE_KEYS),
    Param("rounding", "num", 2, optional=True, label="Radio de redondeo", minimum=0, step=0.5),
    Param("chamfer", "num", 1, optional=True, label="Chaflán", minimum=0, step=0.5),
    FN,
), keyword="module", positional=("h", "r", "center", "edges", "rounding", "chamfer"),
    hint="Cilindro con el borde superior (top) y/o inferior (bottom) redondeado o achaflanado."))

# --- Piezas mecánicas -------------------------------------------------------
# Cuñero en el agujero de engranajes y poleas. Las medidas salen de la tabla según el Ø del agujero
# (gears.KEY_TABLE); el ancho y la profundidad son para los que no estén en ella o sean a medida.
KEYWAY = (
    Param("keyway", "bool", True, optional=True, label="Cuñero"),
    Param("key_width", "num", 2, optional=True, label="Ancho del cuñero", minimum=0.1, step=0.5),
    Param("key_depth", "num", 1, optional=True, label="Profundidad del cuñero", minimum=0.1, step=0.1),
)

_add(Spec("spur_gear", "Engranaje recto", "solid", False, (
    Param("mod", "num", 1, label="Módulo (m)", minimum=0.05, step=0.25),
    Param("teeth", "int", 20, label="Dientes (z)", minimum=3, maximum=400),
    Param("thickness", "num", 5, label="Grueso", minimum=0.01),
    Param("pressure_angle", "num", 20, label="Ángulo de presión (°)", minimum=10, maximum=35, step=0.5),
    # Holgura entre los dos engranajes (se reparte entre ambos). Viene puesta: sin ella, impresos
    # en 3D suelen quedar agarrotados.
    Param("backlash", "num", 0.1, label="Holgura (mm)", minimum=0, step=0.05),
    Param("bore", "num", 5, optional=True, label="Agujero (Ø)", minimum=0),
    *KEYWAY,
    Param("center", "bool", False, label="Centrado"),
    FN,
), keyword="module", hint="Engranaje recto de evolvente. Ø primitivo = m·z; dos engranajes del mismo "
   "módulo engranan con sus centros a m·(z1 + z2)/2."))
_add(Spec("helical_gear", "Engranaje helicoidal", "solid", False, (
    Param("mod", "num", 1, label="Módulo normal (mn)", minimum=0.05, step=0.25),
    Param("teeth", "int", 20, label="Dientes (z)", minimum=3, maximum=400),
    # Más grueso que un recto: el diente tiene que envolver al menos un paso axial para que el
    # engrane sea suave (ver el aviso del panel).
    Param("thickness", "num", 10, label="Grueso", minimum=0.01),
    Param("helix_angle", "num", 20, label="Ángulo de hélice (°)", minimum=1, maximum=45, step=1),
    Param("left_hand", "bool", False, label="Hélice a izquierdas"),
    Param("pressure_angle", "num", 20, label="Ángulo de presión normal (°)", minimum=10, maximum=35, step=0.5),
    Param("backlash", "num", 0.1, label="Holgura (mm)", minimum=0, step=0.05),
    Param("bore", "num", 5, optional=True, label="Agujero (Ø)", minimum=0),
    *KEYWAY,
    Param("center", "bool", False, label="Centrado"),
    FN,
), keyword="module", hint="Engranaje helicoidal de evolvente. El módulo y el ángulo de presión son los "
   "normales (perpendiculares al diente); Ø primitivo = m·z/cos ψ. Dos iguales de mano contraria "
   "engranan con sus centros a m·(z1 + z2)/(2·cos ψ)."))
_add(Spec("bevel_gear", "Engranaje cónico", "solid", False, (
    Param("mod", "num", 1, label="Módulo (m)", minimum=0.05, step=0.25),
    Param("teeth", "int", 20, label="Dientes (z)", minimum=3, maximum=400),
    # El cono de cada rueda depende de las dos: un cónico solo no existe, se diseña por parejas.
    Param("mate_teeth", "int", 20, label="Dientes de la pareja", minimum=3, maximum=400),
    Param("shaft_angle", "num", 90, label="Ángulo entre ejes (°)", minimum=20, maximum=160, step=5),
    Param("face_width", "num", 4, label="Ancho de cara", minimum=0.01, step=0.5),
    Param("pressure_angle", "num", 20, label="Ángulo de presión (°)", minimum=10, maximum=35, step=0.5),
    Param("backlash", "num", 0.1, label="Holgura (mm)", minimum=0, step=0.05),
    Param("bore", "num", 5, optional=True, label="Agujero (Ø)", minimum=0),
    *KEYWAY,
    FN,
), keyword="module", hint="Engranaje cónico recto para ejes que se cortan. El vértice del cono queda en "
   "el origen y la rueda mira hacia +Z, así que la pareja es la misma pieza girada el ángulo entre ejes, "
   "sin moverla. Su cono depende de los dientes de las dos, por eso hay que decir los de la otra."))
_add(Spec("rack", "Cremallera", "solid", False, (
    Param("mod", "num", 1, label="Módulo (m)", minimum=0.05, step=0.25),
    Param("teeth", "int", 10, label="Dientes (z)", minimum=1, maximum=400),
    Param("thickness", "num", 5, label="Grueso", minimum=0.01),
    Param("base", "num", 5, label="Base (bajo los dientes)", minimum=0, step=0.5),
    Param("pressure_angle", "num", 20, label="Ángulo de presión (°)", minimum=10, maximum=35, step=0.5),
    Param("backlash", "num", 0.1, label="Holgura (mm)", minimum=0, step=0.05),
    # Con estos dos el dentado se inclina y engrana con un helicoidal de la misma mano. Opcionales:
    # la cremallera normal es recta y así el panel no se llena de datos que no hacen nada.
    Param("helix_angle", "num", 20, optional=True, label="Ángulo de hélice (°)", minimum=0,
          maximum=45, step=1),
    Param("left_hand", "bool", False, optional=True, label="Hélice a izquierdas"),
    Param("center", "bool", False, label="Centrado"),
), keyword="module", hint="Cremallera: el dentado básico del sistema por módulo, de flancos rectos. "
   "Su línea primitiva queda en y = 0 y los dientes miran a +Y, así que un engranaje del mismo módulo "
   "engrana con su centro a su radio primitivo de altura. Con ángulo de hélice el dentado se inclina y "
   "engrana con un helicoidal de la misma mano; entonces los extremos quedan al sesgo del dentado."))

_add(Spec("pulley", "Polea dentada", "solid", False, (
    Param("section", "choice", "XL", label="Sección", options=("MXL", "XL", "L", "H", "XH")),
    Param("teeth", "int", 20, label="Dientes (z)", minimum=3, maximum=400),
    Param("width", "num", 6, label="Ancho (correa)", minimum=0.01),
    Param("bore", "num", 5, optional=True, label="Agujero (Ø)", minimum=0),
    *KEYWAY,
    # Sin pestañas la correa se puede salir por el eje; con ellas, un collar sobresale del Ø
    # exterior a un lado, al otro o a los dos. Opcionales: con "ninguna" no hace falta decir más.
    Param("flange", "choice", "ninguna", optional=True, label="Pestañas",
          options=("ninguna", "superior", "inferior", "ambas"), translated=True),
    Param("flange_height", "num", 1.5, optional=True, label="Vuelo de la pestaña", minimum=0.1, step=0.5),
    Param("center", "bool", False, label="Centrado"),
), keyword="module", hint="Polea para correa dentada (síncrona), secciones ANSI/RMA clásicas "
   "MXL/XL/L/H/XH. Ø primitivo = dientes·paso/π; el hueco es el negativo del diente de la "
   "correa. No necesita pareja: el centro entre dos poleas lo pone la longitud de la correa."))

_add(Spec("spline", "Estriado", "solid", False, (
    Param("mod", "num", 1, label="Módulo (m)", minimum=0.25, step=0.25),
    Param("teeth", "int", 20, label="Dientes (z)", minimum=3, maximum=400),
    Param("length", "num", 20, label="Longitud", minimum=0.01),
    Param("pressure_angle", "num", 30, label="Ángulo de presión (°)", minimum=30, maximum=45, step=7.5),
    Param("fillet_root", "bool", True, optional=True, label="Fondo redondeado (30°)"),
    Param("internal", "bool", True, optional=True, label="Cubo (estriado interior)"),
    Param("hub_d", "num", 60, optional=True, label="Ø exterior del cubo", minimum=0.1),
    Param("clearance", "num", 0.1, optional=True, label="Holgura (mm)", minimum=0, step=0.05),
    Param("center", "bool", False, label="Centrado"),
    FN,
), keyword="module", hint="Estriado de evolvente por módulo, de ajuste lateral (ANSI B92.2M, derivada de "
   "ISO 4156). El eje y el cubo encajan en el mismo sitio, sin moverlos ni girarlos. La holgura solo "
   "adelgaza el diente del eje: el hueco del cubo siempre tiene el ancho básico."))

_add(Spec("cam", "Leva de disco", "solid", False, (
    Param("base_d", "num", 40, label="Ø base", minimum=1),
    Param("lift", "num", 10, label="Alzada", minimum=0.1),
    Param("rise_angle", "num", 90, label="Ángulo de subida (°)", minimum=1, maximum=358, step=5),
    Param("dwell_angle", "num", 30, optional=True, label="Reposo arriba (°)", minimum=0, maximum=358, step=5),
    Param("fall_angle", "num", 90, label="Ángulo de bajada (°)", minimum=1, maximum=358, step=5),
    Param("motion", "choice", "cicloidal", label="Ley de movimiento",
          options=("cicloidal", "armonica", "parabolica", "velocidad_constante")),
    Param("thickness", "num", 8, label="Espesor", minimum=0.01),
    Param("bore", "num", 6, optional=True, label="Agujero (Ø)", minimum=0),
    Param("center", "bool", False, label="Centrado"),
), keyword="module", hint="Leva de disco: el seguidor sube la alzada con la ley de movimiento "
   "elegida durante el ángulo de subida, se queda arriba el reposo, baja con la misma ley "
   "espejada y el resto del giro se queda en el Ø base. 4 leyes clásicas de «Cams and Cam "
   "Design» (Machinery's Handbook 27, pp. 2190-2192): cicloidal (la de menos vibración, usada en "
   "maquinaria rápida), armónica, parabólica y velocidad constante (con golpe en los cambios, "
   "solo para mecanismos lentos)."))

# Árbol de levas: el eje y los lóbulos son piezas separadas, cada lóbulo con su posición y su ángulo.
_add(Spec("camshaft_main_shaft", "Eje del árbol de levas", "solid", False, (
    Param("length", "num", 250, label="Longitud", minimum=0.01, step=5),
    Param("d", "num", 25, label="Ø del eje", minimum=0.01),
), keyword="module", hint="Eje principal de un árbol de levas, a lo largo de Z desde z = 0 hasta su "
   "longitud. Los lóbulos (cam_lobe) se colocan sobre él con su propia posición y ángulo."))
_add(Spec("cam_lobe", "Lóbulo de leva", "solid", False, (
    Param("base_r", "num", 15, label="Radio base", minimum=0.01),
    Param("lift", "num", 8, label="Alzada", minimum=0),
    Param("width", "num", 12, label="Ancho", minimum=0.01),
    Param("rise_angle", "num", 110, label="Ángulo de subida (°)", minimum=1, maximum=358, step=5),
    Param("dwell_angle", "num", 20, label="Reposo en la punta (°)", minimum=0, maximum=358, step=5),
    Param("fall_angle", "num", 110, label="Ángulo de bajada (°)", minimum=1, maximum=358, step=5),
    Param("motion", "choice", "cicloidal", label="Ley de movimiento",
          options=("cicloidal", "armonica", "parabolica", "velocidad_constante")),
    Param("angle", "num", 0, label="Orientación de la punta (°)", minimum=-360, maximum=360, step=15),
    Param("position", "num", 20, label="Posición en el eje (Z)", step=5),
    Param("step", "num", 1, label="Resolución (° por punto)", minimum=0.1, maximum=10, step=0.5),
), keyword="module", hint="Lóbulo de un árbol de levas, extruido a lo largo de Z y centrado en su "
   "posición. La punta (alzada máxima) mira a la orientación dada: sube durante el ángulo de "
   "subida, se mantiene el reposo centrado en la punta y baja durante el de bajada; el resto del "
   "giro queda en el radio base. Si subida y bajada son distintas, el lóbulo es asimétrico. Las "
   "mismas 4 leyes que la leva de disco (Machinery's Handbook 27, pp. 2190-2192)."))

_add(Spec("v_pulley", "Polea trapecial", "solid", False, (
    Param("section", "choice", "A", label="Sección", options=("A", "B", "C", "D")),
    Param("datum_d", "num", 80, label="Ø primitivo (datum)", minimum=10, step=5),
    Param("grooves", "int", 1, label="Ranuras", minimum=1, maximum=20),
    Param("bore", "num", 10, optional=True, label="Agujero (Ø)", minimum=0),
    *KEYWAY,
    Param("center", "bool", False, label="Centrado"),
), keyword="module", hint="Polea para correa en V, secciones trapeciales clásicas ANSI/RMA "
   "A/B/C/D (las variantes de muesca moldeada AX/BX/CX/DX usan la misma ranura que su letra). "
   "El ancho de cara sale solo de las ranuras: separación·(ranuras−1) + 2·margen. El ángulo y "
   "ancho de la ranura cambian con el Ø primitivo, por tramos de la tabla."))

# Por defecto, una brida de cuello NPS 4 clase 150 con resalte (ASME B16.5-2013, tablas 7, 8 y 4).
# Las medidas de cada norma las pone el asistente de bridas (flanges.py); aquí se pueden retocar.
_add(Spec("pipe_flange", "Brida", "solid", False, (
    Param("od", "num", 230, label="Ø exterior", minimum=0.1, step=5),
    Param("thickness", "num", 22.3, label="Grueso (sin resalte)", minimum=0.1),
    Param("bolt_circle", "num", 190.5, label="Ø del círculo de tornillos", minimum=0, step=5),
    Param("bolts", "int", 8, label="Agujeros", minimum=0, maximum=200),
    Param("hole", "num", 19.05, label="Ø de los agujeros", minimum=0),
    Param("bore", "num", 102.3, label="Agujero (Ø)", minimum=0),
    Param("face_d", "num", 157.2, optional=True, initial=True, label="Ø del resalte", minimum=0, step=5),
    Param("face_h", "num", 2, optional=True, initial=True, label="Alto del resalte", minimum=0),
    Param("hub_d", "num", 135, optional=True, initial=True, label="Ø del cuello en la brida", minimum=0, step=5),
    Param("hub_end_d", "num", 114.3, optional=True, initial=True, label="Ø del cuello en el extremo", minimum=0,
          step=5),
    Param("length", "num", 77, optional=True, initial=True, label="Largo total", minimum=0, step=5),
    Param("neck_length", "num", 0, optional=True, label="Tramo recto del cuello", minimum=0),
    Param("center", "bool", False, label="Centrado"),
), keyword="module", hint="Brida para tubería: la cara de la junta en z = 0 y el cuello hacia +Z. "
   "El resalte va encima del grueso; el cuello baja del Ø en la brida al Ø del extremo y acaba en un "
   "tramo recto. Sin cuello (Ø 0) es una brida plana o ciega; sin agujero, ciega. Para las medidas de "
   "ASME B16.5 o EN 1092-1, use el asistente de bridas."))

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
    ("array", "Repetir", "Selecciona las piezas que quieres repetir. Se genera un bucle for de "
     "OpenSCAD que puedes editar aquí o en el código."),
    ("adv", "Avanzado", "roof() es experimental: actívalo con --enable=roof en OpenSCAD."),
    ("imp", "Importar", "Abre un selector de archivo: STL, OFF, 3MF, AMF, OBJ, SVG, DXF o imagen."),
)


def specs_in(category: str) -> list[Spec]:
    return [s for s in SPECS.values() if s.category == category]


def openscad_modules() -> list[str]:
    """Nombres que existen como módulos en OpenSCAD (sin las matrices, que escriben un for)."""
    return [name for name, spec in SPECS.items() if not spec.keyword]


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
    "spur_gear": "M19.42 10.37 L21.92 10.71 L21.92 13.29 L19.42 13.63 L18.96 15.05 L20.78 16.78 L19.26 18.87 L17.05 17.68 L15.84 18.56 L16.29 21.03 L13.84 21.83 L12.74 19.56 L11.26 19.56 L10.16 21.83 L7.71 21.03 L8.16 18.56 L6.95 17.68 L4.74 18.87 L3.22 16.78 L5.04 15.05 L4.58 13.63 L2.08 13.29 L2.08 10.71 L4.58 10.37 L5.04 8.95 L3.22 7.22 L4.74 5.13 L6.95 6.32 L8.16 5.44 L7.71 2.97 L10.16 2.17 L11.26 4.44 L12.74 4.44 L13.84 2.17 L16.29 2.97 L15.84 5.44 L17.05 6.32 L19.26 5.13 L20.78 7.22 L18.96 8.95z M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6z",
    "helical_gear": ("M4.5 6c0-1.21 3.36-2.2 7.5-2.2s7.5 0.99 7.5 2.2v11c0 1.21-3.36 2.2-7.5 2.2"
                     "s-7.5-0.99-7.5-2.2z M4.5 6c0 1.21 3.36 2.2 7.5 2.2s7.5-0.99 7.5-2.2"
                     " M5.5 7.1l5 12.1 M9 8l5 11.1 M12.5 8.2l5 10.3"),
    "bevel_gear": ("M7 18L4 10l2-2.6l2 2.6l2-2.6l2 2.6l2-2.6l2 2.6l2-2.6l2 2.6L17 18Z"
                   " M12 18v3"),
    "pulley": ("M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20z M12 6a6 6 0 1 0 0 12a6 6 0 1 0 0-12z"
               " M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5.3 5.3l2.2 2.2 M16.5 16.5l2.2 2.2"
               " M5.3 18.7l2.2-2.2 M16.5 7.5l2.2-2.2"),
    "spline": ("M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M12 3v5 M12 16v5 M3 12h5 M16 12h5"
               " M5.6 5.6l3.5 3.5 M14.9 14.9l3.5 3.5 M5.6 18.4l3.5-3.5 M14.9 9.1l3.5-3.5"),
    "cam": ("M13 3c-4.5 0-8 3.8-8 9s3.5 9 8 9c0.9 0 1.7-1.6 2.3-4.2c0.4-1.7 1.7-3 3.4-3l1.3 0"
            "c0.6 0 1-0.4 1-1v-1.6c0-0.6-0.4-1-1-1l-1.3 0c-1.7 0-3-1.3-3.4-3C14.7 4.6 13.9 3 13 3z"
            " M12 9a3 3 0 1 0 0.01 0"),
    "camshaft_main_shaft": "M2 10h20v4H2z M5 10v4 M19 10v4",
    "cam_lobe": ("M2 11h20v2H2z M9 6c0-2 1.5-3.5 3-3.5S15 4 15 6v12c0 2-1.5 3.5-3 3.5S9 20 9 18z"),
    "pipe_flange": ("M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20z M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8z"
                    " M12 4.2a.9.9 0 1 0 0 1.8a.9.9 0 1 0 0-1.8z M12 18a.9.9 0 1 0 0 1.8a.9.9 0 1 0 0-1.8z"
                    " M4.2 12a.9.9 0 1 0 1.8 0a.9.9 0 1 0-1.8 0z M18 12a.9.9 0 1 0 1.8 0a.9.9 0 1 0-1.8 0z"),
    "v_pulley": ("M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20z"
                 " M9 2.5l3 3l3-3 M9 21.5l3-3l3 3 M2.5 9l3 3l-3 3 M21.5 9l-3 3l3 3"),
    "rack": ("M2 14H2.7L3.5 7h2l0.8 7h1.4L8.5 7h2l0.8 7h1.4L13.5 7h2l0.8 7h1.4L18.5 7h2l0.8 7H22"
             "V19H2Z"),
    "cube_edges": "M12 3l8 4.5v9L12 21l-8-4.5v-9z M12 12l8-4.5 M12 12v9 M12 12L4 7.5 M17 4.2a4 4 0 0 1 3 3.3",
    "cylinder_edges": "M5 8c0-1.7 3.1-3 7-3s7 1.3 7 3v10c0 1.7-3.1 3-7 3s-7-1.3-7-3z M5 8c0 1.7 3.1 3 7 3s7-1.3 7-3",
    "linear_array": "M2 9h5v6H2z M9.5 9h5v6h-5z M17 9h5v6h-5z M4 5h16 M17 2.5L20 5l-3 2.5",
    "polar_array": ("M10 4a2 2 0 1 0 4 0a2 2 0 1 0-4 0z M3.1 8a2 2 0 1 0 4 0a2 2 0 1 0-4 0z "
                    "M3.1 16a2 2 0 1 0 4 0a2 2 0 1 0-4 0z M10 20a2 2 0 1 0 4 0a2 2 0 1 0-4 0z "
                    "M16.9 16a2 2 0 1 0 4 0a2 2 0 1 0-4 0z M16.9 8a2 2 0 1 0 4 0a2 2 0 1 0-4 0z M12 12h.01"),
    "grid_array": "M3 3h3.5v3.5h-3.5z M10.25 3h3.5v3.5h-3.5z M17.5 3h3.5v3.5h-3.5z M3 10.25h3.5v3.5h-3.5z M10.25 10.25h3.5v3.5h-3.5z M17.5 10.25h3.5v3.5h-3.5z M3 17.5h3.5v3.5h-3.5z M10.25 17.5h3.5v3.5h-3.5z M17.5 17.5h3.5v3.5h-3.5z",
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
    "search": "M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14z M20 20l-4-4",
    "sketch": "M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25z M20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z",
    "hardware": "M7 2h10v4H7z M9 6v12l3 4 3-4V6 M7 10h10 M7 14h10",
}
