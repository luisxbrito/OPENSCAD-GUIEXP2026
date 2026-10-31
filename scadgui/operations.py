"""Guía de cada operación de OpenSCAD: explicación, ejemplo y ajustes rápidos.

Son datos sin dependencias de Qt (los muestra ``ui/operation_helper.py``). Cada ajuste
rápido es (texto del botón, función que recibe los parámetros actuales y devuelve el
valor nuevo, nombre del parámetro).
"""

from __future__ import annotations

from typing import Any, Callable

Preset = Callable[[dict], Any]


def _as_vec3(value) -> list:
    """Vector de 3 números aunque el parámetro sea un escalar (rotate(45)) o falte."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [0.0, 0.0, float(value)]
    if isinstance(value, (list, tuple)):
        nums = [float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else 0.0 for x in value[:3]]
        return nums + [0.0] * (3 - len(nums))
    return [0.0, 0.0, 0.0]


def _shift(key: str, axis: int, delta: float, wrap: float = 0.0) -> Preset:
    def apply(params: dict) -> list:
        v = _as_vec3(params.get(key))
        v[axis] += delta
        if wrap:
            v[axis] %= wrap
        return v
    return apply


def _set_axis(key: str, axis: int, value: float) -> Preset:
    def apply(params: dict) -> list:
        v = _as_vec3(params.get(key))
        v[axis] = value
        return v
    return apply


def _const(value) -> Preset:
    return lambda params: value


def _toggle(key: str) -> Preset:
    return lambda params: not params.get(key, False)


def _spread(total: float) -> Preset:
    """Ángulo entre copias para repartir las copias de una matriz polar en ``total`` grados.

    En una vuelta completa la última copia no repite la primera (360 / n); en un arco, la
    primera y la última quedan en los extremos (arco / (n - 1)).
    """
    def apply(params: dict) -> float:
        n = params.get("n")
        n = int(n) if isinstance(n, (int, float)) and not isinstance(n, bool) and n >= 1 else 1
        parts = n if abs(total) >= 360 else max(n - 1, 1)
        return round(total / parts, 6)
    return apply


OPERATION_HELPERS: dict[str, dict[str, Any]] = {
    "translate": {
        "title": "Mover (translate)",
        "icon": "translate",
        "category": "Transformaciones",
        "summary": "Desplaza las piezas hijas a lo largo de los ejes X, Y y Z.",
        "how_it_works": (
            "El vector [X, Y, Z] define cuántos milímetros se mueve el objeto respecto a su "
            "posición actual. El movimiento es relativo a su sistema de coordenadas local."
        ),
        "pro_tip": "Si quieres apoyar una pieza sobre el plano de trabajo XY, desplázala en Z la mitad de su altura (si está centrada) o colócala en Z=0.",
        "example_code": (
            "translate([20, 0, 10]) {\n"
            "    cube([10, 10, 10], center = true); // Se mueve 20mm en X y 10mm en Z\n"
            "}"
        ),
        "presets": [
            ("X +10", _shift("v", 0, 10), "v"),
            ("X -10", _shift("v", 0, -10), "v"),
            ("Y +10", _shift("v", 1, 10), "v"),
            ("Y -10", _shift("v", 1, -10), "v"),
            ("Z +10", _shift("v", 2, 10), "v"),
            ("Z -10", _shift("v", 2, -10), "v"),
            ("Z = 0", _set_axis("v", 2, 0.0), "v"),
            ("Origen [0,0,0]", _const([0.0, 0.0, 0.0]), "v"),
        ],
    },
    "rotate": {
        "title": "Rotar (rotate)",
        "icon": "rotate",
        "category": "Transformaciones",
        "summary": "Gira las piezas hijas alrededor de los ejes X, Y y Z en grados sexagesimales.",
        "how_it_works": (
            "El vector [aX, aY, aZ] indica el ángulo de giro en grados. "
            "El giro se realiza alrededor del origen de coordenadas (0,0,0), salvo que se combine "
            "con un translate previo para cambiar el punto de pivote."
        ),
        "pro_tip": "rotate([x, y, z]) gira primero alrededor de X, luego de Y y por último de Z, siempre sobre los ejes fijos del mundo. "
                   "Si necesitas otro orden, anida varios rotate().",
        "example_code": (
            "rotate([0, 0, 45]) {\n"
            "    cube([20, 10, 5], center = true); // Girado 45° en el plano horizontal\n"
            "}"
        ),
        "presets": [
            ("X +90°", _shift("a", 0, 90, wrap=360), "a"),
            ("Y +90°", _shift("a", 1, 90, wrap=360), "a"),
            ("Z +90°", _shift("a", 2, 90, wrap=360), "a"),
            ("Z +45°", _shift("a", 2, 45, wrap=360), "a"),
            ("Z +180°", _shift("a", 2, 180, wrap=360), "a"),
            ("Restablecer [0,0,0]", _const([0.0, 0.0, 0.0]), "a"),
        ],
    },
    "scale": {
        "title": "Escalar (scale)",
        "icon": "scale",
        "category": "Transformaciones",
        "summary": "Multiplica el tamaño de los sólidos por un factor independiente en X, Y, Z.",
        "how_it_works": (
            "Un factor mayor que 1 amplía el objeto; entre 0 y 1 lo reduce. "
            "Un factor negativo invierte el objeto a lo largo de ese eje (efecto espejo)."
        ),
        "pro_tip": "Para agrandar todo proporcionalmente, usa el mismo valor en los tres ejes [s, s, s].",
        "example_code": (
            "scale([2, 1, 0.5]) {\n"
            "    sphere(r = 10); // Doble de ancho en X y mitad de alto en Z (elipsoide)\n"
            "}"
        ),
        "presets": [
            ("2x Doble", _const([2.0, 2.0, 2.0]), "v"),
            ("0.5x Mitad", _const([0.5, 0.5, 0.5]), "v"),
            ("Espejo X [-1]", _const([-1.0, 1.0, 1.0]), "v"),
            ("Espejo Y [-1]", _const([1.0, -1.0, 1.0]), "v"),
            ("Restablecer [1,1,1]", _const([1.0, 1.0, 1.0]), "v"),
        ],
    },
    "mirror": {
        "title": "Espejo (mirror)",
        "icon": "mirror",
        "category": "Transformaciones",
        "summary": "Refleja los sólidos a través de un plano que pasa por el origen perpendicular al vector normal.",
        "how_it_works": (
            "El vector [X, Y, Z] es la dirección perpendicular al plano de reflexión. "
            "[1,0,0] refleja a través del plano YZ (invierte X). [0,1,0] a través del plano XZ. [0,0,1] a través del XY."
        ),
        "pro_tip": "Si quieres conservar tanto la pieza original como su reflejo simétrico, agrupa ambas con union().",
        "example_code": (
            "mirror([1, 0, 0]) {\n"
            "    cube([15, 10, 5]); // Reflejado horizontalmente en el eje X\n"
            "}"
        ),
        "presets": [
            ("Plano YZ [X]", _const([1.0, 0.0, 0.0]), "v"),
            ("Plano XZ [Y]", _const([0.0, 1.0, 0.0]), "v"),
            ("Plano XY [Z]", _const([0.0, 0.0, 1.0]), "v"),
        ],
    },
    "color": {
        "title": "Color (color)",
        "icon": "color",
        "category": "Transformaciones",
        "summary": "Asigna un color y opacidad visual al sólido para previsualización y render.",
        "how_it_works": (
            "Admite nombres de color web ('SteelBlue', 'Tomato', 'Gold'), código hexadecimal ('#FF8800') "
            "o un vector [r, g, b, a] con valores entre 0 y 1."
        ),
        "pro_tip": "El parámetro alpha (0 a 1) permite crear piezas transparentes o translúcidas muy útiles para ver mecanismos interiores.",
        "example_code": (
            "color(\"SteelBlue\", alpha = 0.8) {\n"
            "    cylinder(h = 20, r = 5); // Cilindro azul semitransparente\n"
            "}"
        ),
        "presets": [
            ("SteelBlue", _const("SteelBlue"), "c"),
            ("Tomato", _const("Tomato"), "c"),
            ("Gold", _const("Gold"), "c"),
            ("SeaGreen", _const("SeaGreen"), "c"),
            ("DimGray", _const("DimGray"), "c"),
            ("Purple", _const("Purple"), "c"),
            ("Opaco 1.0", _const(1.0), "alpha"),
            ("Semivisible 0.5", _const(0.5), "alpha"),
        ],
    },
    "difference": {
        "title": "Restar (difference)",
        "icon": "difference",
        "category": "Operaciones booleanas",
        "summary": "Resta uno o varios sólidos de un sólido base (cortes, taladros y cajeados).",
        "how_it_works": (
            "El PRIMER hijo es el sólido base (positivo, minuendo). "
            "Todos los hijos subsiguientes (2º, 3º...) se restan (negativos, sustraendos) de esa base."
        ),
        "pro_tip": "Evita caras coincidentes (Z-fighting): haz que los cilindros de agujero sobresalgan ligeramente (ej. +0.02mm o +1mm) por ambos extremos del corte para garantizar una resta limpia sin paredes infinitamente delgadas.",
        "example_code": (
            "difference() {\n"
            "    cube([40, 40, 10], center = true); // 1. Base (+)\n"
            "    cylinder(h = 12, r = 5, center = true); // 2. Taladro que resta (-)\n"
            "}"
        ),
        "presets": [],
    },
    "union": {
        "title": "Unir (union)",
        "icon": "union",
        "category": "Operaciones booleanas",
        "summary": "Fusiona múltiples sólidos en un único cuerpo volumétrico continuo.",
        "how_it_works": (
            "Une todos los hijos. Los volúmenes que se intersecan se fusionan automáticamente, "
            "eliminando las superficies interiores intermedias."
        ),
        "pro_tip": "En OpenSCAD, los sólidos colocados uno junto a otro en la raíz ya tienen una unión implícita. Usar union() explícito es útil para aplicar transformaciones conjuntas o como base de una resta.",
        "example_code": (
            "union() {\n"
            "    cube([20, 20, 10], center = true);\n"
            "    cylinder(h = 25, r = 4, center = true);\n"
            "}"
        ),
        "presets": [],
    },
    "intersection": {
        "title": "Intersecar (intersection)",
        "icon": "intersection",
        "category": "Operaciones booleanas",
        "summary": "Conserva únicamente el volumen compartido donde todos los sólidos hijos coinciden.",
        "how_it_works": (
            "Deja solo la región del espacio tridimensional cubierta simultáneamente por todos los sólidos. "
            "Cualquier parte que no pertenezca a todos los hijos a la vez desaparece."
        ),
        "pro_tip": "Útil para recortar una pieza dentro de un volumen límite, o para lentes y perfiles redondeados (cubo ∩ esfera).",
        "example_code": (
            "intersection() {\n"
            "    cube([20, 20, 20], center = true);\n"
            "    sphere(r = 13);\n"
            "}"
        ),
        "presets": [],
    },
    "linear_extrude": {
        "title": "Extruir lineal (linear_extrude)",
        "icon": "linear_extrude",
        "category": "2D a 3D",
        "summary": "Convierte una forma 2D plana en un sólido 3D estirándola verticalmente a lo largo del eje Z.",
        "how_it_works": (
            "Toma las formas 2D hijas (square, circle, polygon, text) y las proyecta hacia arriba "
            "según el parámetro 'height'. Soporta torsión ('twist') y escala progresiva ('scale')."
        ),
        "pro_tip": "Las formas hijas deben ser estrictamente 2D. No intentes extruir un cubo o esfera 3D.",
        "example_code": (
            "linear_extrude(height = 15, center = false, twist = 0) {\n"
            "    circle(r = 10);\n"
            "}"
        ),
        "presets": [
            ("5 mm", _const(5.0), "height"),
            ("10 mm", _const(10.0), "height"),
            ("20 mm", _const(20.0), "height"),
            ("Centrado Sí/No", _toggle("center"), "center"),
            ("Twist 90°", _const(90.0), "twist"),
            ("Cono scale=0.5", _const(0.5), "scale"),
        ],
    },
    "rotate_extrude": {
        "title": "Revolución (rotate_extrude)",
        "icon": "rotate_extrude",
        "category": "2D a 3D",
        "summary": "Gira una forma 2D alrededor del eje Z para crear sólidos de revolución (anillos, botellas, poleas).",
        "how_it_works": (
            "Toma una figura 2D situada en el semiplano derecho (X >= 0) y la hace girar en torno al eje vertical Z. "
            "El parámetro 'angle' controla el arco en grados (360° para un sólido cerrado completo)."
        ),
        "pro_tip": "Todos los puntos de la forma 2D deben quedar al mismo lado del eje Y (normalmente X >= 0). "
                   "Si la forma cruza X = 0, OpenSCAD da un error y no genera la revolución.",
        "example_code": (
            "rotate_extrude(angle = 360, $fn = 64) {\n"
            "    translate([20, 0]) circle(r = 5); // Crea un toroide (dona)\n"
            "}"
        ),
        "presets": [
            ("360° Completo", _const(360.0), "angle"),
            ("180° Mitad", _const(180.0), "angle"),
            ("90° Cuarto", _const(90.0), "angle"),
            ("Alta suave ($fn=64)", _const(64), "$fn"),
        ],
    },
    "offset": {
        "title": "Desfase 2D (offset)",
        "icon": "offset",
        "category": "Formas 2D",
        "summary": "Expande, contrae o redondea el contorno de formas bidimensionales.",
        "how_it_works": (
            "Aplica una dilatación (r > 0) o erosión (r < 0) sobre curvas y polígonos 2D. "
            "Con 'r' redondea las esquinas; con 'delta' y 'chamfer' crea chaflanes biselados."
        ),
        "pro_tip": "Para redondear las esquinas sin cambiar el tamaño, primero encoge y después crece: "
                   "offset(r = 3) offset(delta = -3) square(...). El de dentro se aplica primero.",
        "example_code": (
            "offset(r = 3) {\n"
            "    square([30, 20], center = true); // Queda de 36 x 26 con esquinas R3\n"
            "}"
        ),
        "presets": [
            ("Radio R=2", _const(2.0), "r"),
            ("Radio R=5", _const(5.0), "r"),
            ("Delta +1", _const(1.0), "delta"),
            ("Delta -1", _const(-1.0), "delta"),
            ("Chaflán Sí/No", _toggle("chamfer"), "chamfer"),
        ],
    },
    "hull": {
        "title": "Envolvente convexa (hull)",
        "icon": "hull",
        "category": "Avanzado",
        "summary": "Calcula la envolvente convexa continua envolviendo todos los sólidos hijos como una banda elástica.",
        "how_it_works": (
            "Conecta dos o más figuras creando una transición continua y suave entre ellas. "
            "Es ideal para crear brazos mecánicos, bielas, mangos redondeados y soportes orgánicos."
        ),
        "pro_tip": "Crea ranuras o chaveteros uniendo dos cilindros separados con hull().",
        "example_code": (
            "hull() {\n"
            "    translate([-15, 0, 0]) cylinder(h = 5, r = 5, center = true);\n"
            "    translate([15, 0, 0]) cylinder(h = 5, r = 8, center = true);\n"
            "}"
        ),
        "presets": [],
    },
    "minkowski": {
        "title": "Suma de Minkowski (minkowski)",
        "icon": "minkowski",
        "category": "Avanzado",
        "summary": "Suma matemática de dos formas: desplaza la segunda figura sobre cada punto de la primera.",
        "how_it_works": (
            "Sirve para redondear todas las aristas de un sólido sumándole una esfera pequeña; el sólido crece el diámetro de la esfera. "
            "Atención: puede ser muy exigente en tiempo de cálculo si el $fn es alto."
        ),
        "pro_tip": "Mantén $fn bajo (ej. 8 o 16) mientras diseñas para que el visor responda rápido, y súbelo solo para la exportación final.",
        "example_code": (
            "minkowski() {\n"
            "    cube([30, 20, 10], center = true);\n"
            "    sphere(r = 2, $fn = 16); // Aristas con radio 2; el resultado mide 34 x 24 x 14\n"
            "}"
        ),
        "presets": [],
    },    "linear_array": {
        "title": "Matriz lineal (for + translate)",
        "icon": "linear_array",
        "category": "Repetir",
        "summary": "Repite las piezas de dentro en línea recta, con la misma separación entre cada copia.",
        "how_it_works": (
            "Genera un bucle for: la copia número i se desplaza i veces el vector de separación. "
            "La primera copia (i = 0) queda donde está la pieza original."
        ),
        "pro_tip": "Todas las copias son la misma pieza: al cambiar la original cambian todas. Para un patrón de agujeros, mete la matriz dentro del difference, después de la base.",
        "example_code": (
            "for (i = [0 : 3]) translate(i * [20, 0, 0]) {\n"
            "    cylinder(h = 12, r = 3); // 4 cilindros cada 20 mm en X\n"
            "}"
        ),
        "presets": [
            ("2 copias", _const(2), "n"),
            ("5 copias", _const(5), "n"),
            ("10 copias", _const(10), "n"),
            ("X cada 10 mm", _const([10, 0, 0]), "step"),
            ("X cada 20 mm", _const([20, 0, 0]), "step"),
            ("Y cada 10 mm", _const([0, 10, 0]), "step"),
            ("Y cada 20 mm", _const([0, 20, 0]), "step"),
            ("Z cada 10 mm", _const([0, 0, 10]), "step"),
        ],
    },
    "polar_array": {
        "title": "Matriz polar (for + rotate)",
        "icon": "polar_array",
        "category": "Repetir",
        "summary": "Repite las piezas de dentro girándolas alrededor de un eje que pasa por el origen.",
        "how_it_works": (
            "Genera un bucle for: la copia número i gira i veces el ángulo entre copias. "
            "El giro es alrededor del origen, así que la pieza original debe estar separada del eje "
            "(por ejemplo, con un translate dentro de la matriz)."
        ),
        "pro_tip": "Al cambiar el número de copias, pulsa \"Repartir en 360°\" para que vuelvan a cerrar la vuelta.",
        "example_code": (
            "for (i = [0 : 5]) rotate(a = i * 60, v = [0, 0, 1]) {\n"
            "    translate([30, 0, 0]) cylinder(h = 5, r = 4); // 6 agujeros en un círculo de radio 30\n"
            "}"
        ),
        "presets": [
            ("Repartir en 360°", _spread(360), "angle"),
            ("Repartir en 180°", _spread(180), "angle"),
            ("Repartir en 90°", _spread(90), "angle"),
            ("4 copias", _const(4), "n"),
            ("6 copias", _const(6), "n"),
            ("8 copias", _const(8), "n"),
            ("Eje X", _const([1, 0, 0]), "axis"),
            ("Eje Y", _const([0, 1, 0]), "axis"),
            ("Eje Z", _const([0, 0, 1]), "axis"),
        ],
    },
    "grid_array": {
        "title": "Matriz rectangular (for con i, j)",
        "icon": "grid_array",
        "category": "Repetir",
        "summary": "Repite las piezas de dentro en filas y columnas.",
        "how_it_works": (
            "Genera un bucle for con dos índices: i recorre las columnas y j las filas. "
            "Cada copia se desplaza i veces la separación entre columnas más j veces la separación "
            "entre filas, así que también sirve para rejillas inclinadas."
        ),
        "pro_tip": "Para una rejilla de agujeros en una placa, mete la matriz dentro del difference, después de la placa.",
        "example_code": (
            "for (i = [0 : 2], j = [0 : 1]) translate(i * [20, 0, 0] + j * [0, 15, 0]) {\n"
            "    cylinder(h = 12, r = 2); // 3 columnas x 2 filas\n"
            "}"
        ),
        "presets": [
            ("Columnas cada 10 mm", _const([10, 0, 0]), "step_x"),
            ("Columnas cada 20 mm", _const([20, 0, 0]), "step_x"),
            ("Filas cada 10 mm", _const([0, 10, 0]), "step_y"),
            ("Filas cada 20 mm", _const([0, 20, 0]), "step_y"),
        ],
    },
}
