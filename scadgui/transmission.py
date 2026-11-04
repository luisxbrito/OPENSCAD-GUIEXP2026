"""Calculadora de transmisiones (sin Qt): busca los dientes de los engranajes, o las poleas y la correa,
para una relación pedida y crea la transmisión ya colocada. Las correas están al final del archivo.

La relación es la de velocidades, entrada/salida: 3.75 quiere decir que la salida gira 3.75 veces más
despacio que la entrada (reductora); menos de 1 es multiplicadora. En una etapa vale z2/z1 (dientes
del conducido entre los del motriz) y en dos, (z2/z1)·(z4/z3), con z2 y z3 en el mismo eje intermedio.

* El error es (relación real − pedida)/pedida, y solo se aceptan soluciones dentro de la tolerancia.
* Todas las ruedas llevan el mismo módulo (y en los helicoidales la misma hélice), así que la distancia
  entre centros de cada etapa es m·(za + zb)/2, o m·(za + zb)/(2·cos ψ) con hélice.
* **Tren revertido** (ejes de entrada y salida alineados): con el mismo módulo, las dos etapas tienen
  que tener la misma distancia entre centros, es decir z1 + z2 = z3 + z4.
* **Diente de caza**: si los dientes de una pareja no tienen divisores comunes, cada diente acaba
  tocando a todos los de la otra rueda y el desgaste se reparte; si los tienen (20/40), siempre se
  tocan los mismos. No impide la solución: solo se marca.

Las soluciones van ordenadas por error; a igual error, primero las que tienen diente de caza en todas sus
parejas y luego por tamaño (menos dientes en total).
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import gears
from .catalog import SPECS
from .i18n import tr
from .model import Node, make_node

N_ = str  # marca un texto que se traduce después con tr() (lo recoge test_i18n)

KINDS = ("spur_gear", "helical_gear", "herringbone_gear")
HELICAL = ("helical_gear", "herringbone_gear")


@dataclass
class Solution:
    stages: list                  # [(z motriz, z conducido), …], una o dos etapas
    ratio: float                  # relación real, entrada/salida
    error: float                  # (real − pedida)/pedida
    centers: list = field(default_factory=list)   # distancia entre centros de cada etapa (mm)

    @property
    def teeth(self) -> int:
        return sum(a + b for a, b in self.stages)

    @property
    def hunting(self) -> list:
        """Por etapa: True si los dientes no tienen divisores comunes (diente de caza)."""
        return [math.gcd(a, b) == 1 for a, b in self.stages]


def ratio_from_speeds(rpm_in: float, rpm_out: float) -> float:
    if rpm_in <= 0 or rpm_out <= 0:
        raise ValueError(tr("Las velocidades tienen que ser mayores que cero."))
    return rpm_in / rpm_out


def default_min_teeth(kind: str, helix_angle: float = 0.0, pressure_angle: float = 20.0) -> int:
    """Dientes mínimos sin socavado para ese tipo de engranaje."""
    if kind in HELICAL:
        return gears.helical_min_teeth(helix_angle, pressure_angle)
    return gears.min_teeth(pressure_angle)


def pitch_d(kind: str, mod: float, teeth: int, helix_angle: float = 0.0) -> float:
    psi = helix_angle if kind in HELICAL else 0.0
    return mod * teeth / max(1e-9, math.cos(math.radians(psi)))


def center(kind: str, mod: float, z1: int, z2: int, helix_angle: float = 0.0) -> float:
    return (pitch_d(kind, mod, z1, helix_angle) + pitch_d(kind, mod, z2, helix_angle)) / 2


def search(ratio: float, tolerance: float = 1.0, stages: int = 1, z_min: int = 18, z_max: int = 100,
           kind: str = "spur_gear", mod: float = 1.0, helix_angle: float = 0.0, max_center: float = 0.0,
           coaxial: bool = False, limit: int = 60) -> list[Solution]:
    """Las mejores ``limit`` soluciones con error ≤ ``tolerance`` (%). ``max_center`` (0 = sin límite)
    limita la distancia entre centros de cada etapa; ``coaxial`` pide un tren revertido (dos etapas)."""
    if ratio <= 0 or not math.isfinite(ratio):
        raise ValueError(tr("La relación tiene que ser mayor que cero."))
    if stages not in (1, 2):
        raise ValueError(tr("La transmisión tiene una o dos etapas."))
    z_min, z_max = max(3, int(z_min)), int(z_max)
    if z_max < z_min:
        raise ValueError(tr("Los dientes máximos no pueden ser menos que los mínimos."))
    tol = max(0.0, tolerance) / 100.0
    # Factor que pasa de la suma de dientes a la distancia entre centros.
    k = center(kind, mod, 1, 0, helix_angle)
    max_sum = max_center / k if max_center > 0 else math.inf
    best: list = []        # montículo con (-clave, contador, solución): se queda con las mejores
    count = 0

    def offer(st: list, real: float) -> None:
        nonlocal count
        err = (real - ratio) / ratio
        if abs(err) > tol + 1e-12:
            return
        sol = Solution(st, real, err, [k * (a + b) for a, b in st])
        key = (round(abs(err), 12), sol.hunting.count(False), sol.teeth, st)
        count += 1
        item = (_neg(key), count, sol)
        if len(best) < limit:
            heapq.heappush(best, item)
        elif item[0] > best[0][0]:
            heapq.heapreplace(best, item)

    def driven_for(z: int, r: float):
        """Dientes del conducido más cercanos a z·r que caben en el rango (uno o dos candidatos)."""
        x = z * r
        out = {math.floor(x), math.ceil(x)}
        return [c for c in out if z_min <= c <= z_max]

    zs = range(z_min, z_max + 1)
    if stages == 1:
        for z1 in zs:
            for z2 in driven_for(z1, ratio):
                if z1 + z2 <= max_sum + 1e-9:
                    offer([(z1, z2)], z2 / z1)
    else:
        reduce = ratio >= 1
        seen = set()
        for z1 in zs:
            for z2 in zs:
                if z1 + z2 > max_sum + 1e-9:
                    continue
                r1 = z2 / z1
                # Las dos etapas van en el mismo sentido que la relación (las dos reducen o las dos
                # multiplican); una etapa que deshace lo que hace la otra no tiene sentido.
                if (reduce and not 1 <= r1 <= ratio) or (not reduce and not ratio <= r1 <= 1):
                    continue
                r2 = ratio / r1
                if coaxial:
                    s = z1 + z2
                    # z4/z3 = r2 con z3 + z4 = s: z3 = s/(1 + r2)
                    x = s / (1 + r2)
                    cands = [(z3, s - z3) for z3 in {math.floor(x), math.ceil(x)}
                             if z_min <= z3 <= z_max and z_min <= s - z3 <= z_max]
                else:
                    cands = [(z3, z4) for z3 in zs for z4 in driven_for(z3, r2)]
                for z3, z4 in cands:
                    if z3 + z4 > max_sum + 1e-9:
                        continue
                    st = [(z1, z2), (z3, z4)]
                    # Las mismas dos etapas en el otro orden son la misma solución.
                    canon = tuple(sorted(st))
                    if canon in seen:
                        continue
                    seen.add(canon)
                    offer(st, (z2 * z4) / (z1 * z3))
    return [item[2] for item in sorted(best, key=lambda it: it[0], reverse=True)]


def _neg(key):
    """Clave invertida para el montículo de mínimos (se queda con las de menor clave)."""
    err, shared, teeth, st = key
    return (-err, -shared, -teeth, tuple((-a, -b) for a, b in st))


def notes(sol: Solution, kind: str, helix_angle: float = 0.0, pressure_angle: float = 20.0) -> list[tuple[str, dict]]:
    """Avisos de una solución: (texto en español, valores para format)."""
    out = []
    zmin = default_min_teeth(kind, helix_angle, pressure_angle)
    small = sorted({z for st in sol.stages for z in st if z < zmin})
    if small:
        out.append((N_("{z} dientes es menos que el mínimo sin socavado ({n}): el pie del diente se debilita."),
                    {"z": ", ".join(str(z) for z in small), "n": zmin}))
    for i, ((a, b), ok) in enumerate(zip(sol.stages, sol.hunting), 1):
        if not ok:
            out.append((N_("Etapa {i}: {a} y {b} tienen divisores comunes, así que siempre se tocan los mismos "
                           "dientes (el desgaste no se reparte)."), {"i": i, "a": a, "b": b}))
    return out


def create_train(sol: Solution, kind: str, params: dict, stage_gap: float = 1.0, coaxial: bool = False,
                 unique_fn: Optional[Callable[[str], str]] = None) -> Node:
    """Grupo con las ruedas ya colocadas y engranando.

    La rueda motriz queda en el origen y la primera pareja en +X. En dos etapas, la segunda pareja va
    encima de la primera (subida el grueso más ``stage_gap``): su motriz comparte eje con el conducido de
    la primera, y su conducido sigue en +X o, en un tren revertido, vuelve al eje de entrada (en −X).
    ``params`` son los parámetros comunes de las ruedas (módulo, grueso, hélice…)."""
    if kind not in KINDS:
        raise ValueError(kind)
    u_fn = unique_fn or (lambda s: s)
    group = make_node("group", u_fn(tr("Transmisión {r}:1").format(r=f"{sol.ratio:.4g}")))
    thickness = float(params.get("thickness", 5))
    if len(sol.stages) == 1:
        names = [tr("Motriz"), tr("Conducido")]
    else:
        names = [tr("Motriz"), tr("Intermedio 1"), tr("Intermedio 2"), tr("Salida")]
    left = bool(params.get("left_hand", False))
    gears_out = []

    def wheel(z: int, name: str, hand: bool) -> Node:
        node = make_node(kind, u_fn(name))
        for key, value in params.items():
            if kind not in HELICAL and key in ("helix_angle", "left_hand"):
                continue
            if key == "bore" and not value:
                continue
            if _has_param(kind, key):
                node.params[key] = value
        node.params["teeth"] = int(z)
        if kind in HELICAL:
            node.params["left_hand"] = hand
        gears_out.append(node)
        return node

    def place(node: Node, x: float, z: float, rot: float) -> Node:
        inner = node
        if round(rot % 360, 6):
            inner = Node(kind="rotate", params={"a": [0, 0, round(rot, 6)]}, children=[inner])
        if round(x, 6) or round(z, 6):
            inner = Node(kind="translate", params={"v": [round(x, 6), 0, round(z, 6)]}, children=[inner])
        return inner

    (z1, z2) = sol.stages[0]
    a1 = sol.centers[0]
    # Las ruedas que engranan llevan hélices contrarias; las dos del eje intermedio, la misma, para
    # que sus empujes axiales se resten.
    group.children.append(place(wheel(z1, names[0], left), 0, 0, 0))
    group.children.append(place(wheel(z2, names[1], not left), a1, 0, gears.mesh_rotation(z2)))
    if len(sol.stages) == 2:
        (z3, z4) = sol.stages[1]
        a2 = sol.centers[1]
        h = thickness + stage_gap
        if coaxial:
            # Toda la pareja girada 180° sobre el eje intermedio: el conducido cae en −X, sobre la entrada.
            group.children.append(place(wheel(z3, names[2], not left), a1, h, 180))
            group.children.append(place(wheel(z4, names[3], left), a1 - a2, h, 180 + gears.mesh_rotation(z4)))
        else:
            group.children.append(place(wheel(z3, names[2], not left), a1, h, 0))
            group.children.append(place(wheel(z4, names[3], left), a1 + a2, h, gears.mesh_rotation(z4)))
    return group


def _has_param(kind: str, key: str) -> bool:
    return SPECS[kind].param(key) is not None


# --------------------------------------------------------------------------- correas
# Correa abierta entre dos poleas de Ø primitivo d1 y d2 con los centros a C (Machinery's Handbook,
# «Belts and Pulleys»; Shigley, cap. 17):
#
# * longitud primitiva     L = 2C + π(d1 + d2)/2 + (d2 − d1)²/(4C)
# * y al revés             C = [b + √(b² − 2(d2 − d1)²)]/4, con b = L − π(d1 + d2)/2
# * abrazamiento de la polea pequeña   θ = 180° − 2·asin(|d2 − d1|/(2C))
#
# Correa dentada: su longitud es un número entero de pasos, así que se redondea al diente más cercano y
# se recalcula C; la relación es exacta (z2/z1). Correa en V: el Ø primitivo (datum) puede ser
# cualquiera, la relación es d2/d1 (sin contar el deslizamiento, del 1 al 2 %) y la longitud que sale es
# la primitiva: la de catálogo se mete después para recalcular C. Las longitudes de catálogo no se
# incluyen: cambian de un fabricante a otro.

BELT_KINDS = ("pulley", "v_pulley")
MIN_MESH_TEETH = 6      # dientes engranados mínimos en la polea pequeña (regla de los fabricantes)
MIN_WRAP = 120.0        # abrazamiento mínimo de una correa en V (°)
MAX_V_SPEED = 30.0      # velocidad de correa en V clásica (m/s)


@dataclass
class BeltSolution:
    kind: str               # "pulley" (dentada) o "v_pulley" (en V)
    section: str
    driver: float           # dientes (dentada) o Ø primitivo (en V) de la motriz
    driven: float
    ratio: float            # entrada/salida
    error: float
    center: float           # distancia entre centros (mm)
    length: float           # longitud primitiva de la correa (mm)
    belt_teeth: int = 0     # dientes de la correa (solo dentada)

    @property
    def diameters(self) -> tuple[float, float]:
        if self.kind == "pulley":
            return (gears.pulley_dims(self.section, int(self.driver))["pitch_d"],
                    gears.pulley_dims(self.section, int(self.driven))["pitch_d"])
        return float(self.driver), float(self.driven)

    @property
    def wrap(self) -> float:
        d1, d2 = self.diameters
        return wrap_angle(d1, d2, self.center)

    @property
    def mesh_teeth(self) -> float:
        """Dientes de la polea pequeña que abraza la correa (solo dentada)."""
        if self.kind != "pulley":
            return 0.0
        return min(self.driver, self.driven) * self.wrap / 360.0


def belt_length(d1: float, d2: float, c: float) -> float:
    return 2 * c + math.pi * (d1 + d2) / 2 + (d2 - d1) ** 2 / (4 * c)


def belt_center(d1: float, d2: float, length: float) -> Optional[float]:
    """Distancia entre centros para esa longitud; None si la correa no da la vuelta a las dos."""
    b = length - math.pi * (d1 + d2) / 2
    disc = b * b - 2 * (d2 - d1) ** 2
    if b <= 0 or disc < 0:
        return None
    return (b + math.sqrt(disc)) / 4


def wrap_angle(d1: float, d2: float, c: float) -> float:
    x = min(1.0, abs(d2 - d1) / (2 * c)) if c > 0 else 1.0
    return 180.0 - 2 * math.degrees(math.asin(x))


def _outer(kind: str, section: str, value: float) -> float:
    if kind == "pulley":
        return gears.pulley_dims(section, int(value))["outer_d"]
    return gears.v_pulley_dims(section, value, 1)["outer_d"]


def _belt_offer(best: list, counter: list, sol: BeltSolution, key: tuple, limit: int) -> None:
    item = (tuple(-k for k in key), counter[0], sol)
    counter[0] += 1
    if len(best) < limit:
        heapq.heappush(best, item)
    elif item[0] > best[0][0]:
        heapq.heapreplace(best, item)


def _check_ratio(ratio: float) -> None:
    if ratio <= 0 or not math.isfinite(ratio):
        raise ValueError(tr("La relación tiene que ser mayor que cero."))


def search_timing(ratio: float, tolerance: float = 1.0, section: str = "XL", z_min: int = 10, z_max: int = 80,
                  center: float = 0.0, limit: int = 60) -> list[BeltSolution]:
    """Poleas dentadas para la relación. ``center`` es la distancia aproximada (0: d1 + d2); la real sale
    de redondear la correa a un número entero de dientes."""
    _check_ratio(ratio)
    z_min, z_max = max(3, int(z_min)), int(z_max)
    if z_max < z_min:
        raise ValueError(tr("Los dientes máximos no pueden ser menos que los mínimos."))
    pitch = gears.PULLEY_SECTIONS[section][0]
    tol = max(0.0, tolerance) / 100.0
    best: list = []
    counter = [0]
    for z1 in range(z_min, z_max + 1):
        x = z1 * ratio
        for z2 in {math.floor(x), math.ceil(x)}:
            if not z_min <= z2 <= z_max:
                continue
            real = z2 / z1
            err = (real - ratio) / ratio
            if abs(err) > tol + 1e-12:
                continue
            d1 = gears.pulley_dims(section, z1)["pitch_d"]
            d2 = gears.pulley_dims(section, z2)["pitch_d"]
            c0 = center if center > 0 else d1 + d2
            teeth = max(1, round(belt_length(d1, d2, c0) / pitch))
            c = belt_center(d1, d2, teeth * pitch)
            # Las poleas no pueden tocarse: entre los Ø exteriores tiene que quedar algo de hueco.
            if c is None or c <= (_outer("pulley", section, z1) + _outer("pulley", section, z2)) / 2 + 1:
                continue
            sol = BeltSolution("pulley", section, z1, z2, real, err, c, teeth * pitch, teeth)
            # A igual error, antes las que no avisan de pocos dientes engranados.
            weak = int(sol.mesh_teeth < MIN_MESH_TEETH)
            _belt_offer(best, counter, sol, (round(abs(err), 12), weak, z1 + z2, abs(c - c0), z1), limit)
    return [it[2] for it in sorted(best, key=lambda it: it[0], reverse=True)]


def search_v(ratio: float, tolerance: float = 1.0, section: str = "A", d_min: float = 0.0, d_max: float = 400.0,
             step: float = 5.0, center: float = 0.0, length: float = 0.0, limit: int = 60) -> list[BeltSolution]:
    """Poleas en V para la relación. Los Ø de las dos van de ``d_min`` (0: el mínimo recomendado para la
    sección) a ``d_max`` de ``step`` en ``step`` y el de la conducida se redondea a 0.5 mm. Con ``length``
    (la de una correa de catálogo) la distancia sale de ella; si no, se usa ``center`` (0: d1 + d2)."""
    _check_ratio(ratio)
    min_rec = gears.V_BELT_SECTIONS[section][3]
    d_lo = d_min if d_min > 0 else min_rec
    if d_max < d_lo:
        raise ValueError(tr("El Ø máximo no puede ser menor que el mínimo."))
    step = max(0.5, step)
    tol = max(0.0, tolerance) / 100.0
    best: list = []
    counter = [0]
    # Diámetros redondos: los múltiplos de step desde el mínimo.
    first = math.ceil(d_lo / step - 1e-9)
    n = int(math.floor(d_max / step + 1e-9)) - first
    for i in range(n + 1):
        d1 = round((first + i) * step, 3)
        d2 = round(d1 * ratio * 2) / 2
        # La polea pequeña tampoco puede bajar del mínimo de la sección (ni la conducida).
        if d2 < d_lo or d2 > d_max + 1e-9:
            continue
        real = d2 / d1
        err = (real - ratio) / ratio
        if abs(err) > tol + 1e-12:
            continue
        if length > 0:
            c = belt_center(d1, d2, length)
            L = length
        else:
            c = center if center > 0 else d1 + d2
            L = belt_length(d1, d2, c)
        if c is None or c <= (d1 + d2) / 2 + 1:
            continue
        sol = BeltSolution("v_pulley", section, d1, d2, real, err, c, L)
        _belt_offer(best, counter, sol, (round(abs(err), 12), int(sol.wrap < MIN_WRAP), d1 + d2), limit)
    return [it[2] for it in sorted(best, key=lambda it: it[0], reverse=True)]


def belt_notes(sol: BeltSolution, rpm_in: float = 0.0, bore: float = 0.0) -> list[tuple[str, dict]]:
    """Avisos de una transmisión por correa: los de cada polea y los del conjunto."""
    out = []
    if sol.kind == "pulley":
        for z in sorted({int(sol.driver), int(sol.driven)}):
            out += gears.pulley_warnings(sol.section, z, bore)
        if sol.mesh_teeth < MIN_MESH_TEETH:
            out.append((N_("La correa solo abraza {n:.1f} dientes de la polea pequeña: con menos de {m} "
                           "puede saltar. Separa más las poleas o usa más dientes."),
                        {"n": sol.mesh_teeth, "m": MIN_MESH_TEETH}))
    else:
        for d in sorted({sol.driver, sol.driven}):
            out += gears.v_pulley_warnings(sol.section, d, 1, bore)
        if sol.wrap < MIN_WRAP:
            out.append((N_("El abrazamiento de la polea pequeña es {a:.0f}° (menos de {m:.0f}°): la correa "
                           "patina. Separa más las poleas."), {"a": sol.wrap, "m": MIN_WRAP}))
        if rpm_in > 0:
            v = math.pi * sol.driver * rpm_in / 60000.0
            if v > MAX_V_SPEED:
                out.append((N_("La correa va a {v:.1f} m/s: una correa en V clásica no pasa de {m:.0f} m/s."),
                            {"v": v, "m": MAX_V_SPEED}))
    return out


def create_belt_drive(sol: BeltSolution, params: dict, belt: bool = True,
                      unique_fn: Optional[Callable[[str], str]] = None) -> Node:
    """Grupo con las dos poleas (la motriz en el origen, la conducida en +X a la distancia calculada) y,
    si ``belt``, la correa como una pieza más: una banda lisa por la línea primitiva, sin dientes, para
    ver por dónde pasa (se puede borrar o desactivar)."""
    if sol.kind not in BELT_KINDS:
        raise ValueError(sol.kind)
    u_fn = unique_fn or (lambda s: s)
    group = make_node("group", u_fn(tr("Transmisión {r}:1").format(r=f"{sol.ratio:.4g}")))
    names = (tr("Motriz"), tr("Conducido"))
    nodes = []
    for value, name in zip((sol.driver, sol.driven), names):
        node = make_node(sol.kind, u_fn(name))
        node.params["section"] = sol.section
        for key, v in params.items():
            if key == "bore" and not v:
                continue
            if key == "flange" and v == "ninguna":
                continue
            if _has_param(sol.kind, key):
                node.params[key] = v
        if sol.kind == "pulley":
            node.params["teeth"] = int(value)
        else:
            node.params["datum_d"] = round(float(value), 3)
        nodes.append(node)
    group.children.append(nodes[0])
    group.children.append(Node(kind="translate", params={"v": [round(sol.center, 6), 0, 0]},
                               children=[nodes[1]]))
    if belt:
        group.children.extend(_belt_parts(sol, params, u_fn))
    return group


def _band(r1: float, r2: float, c: float, inner: float, outer: float, height: float, z: float,
          name: str) -> Node:
    """Banda (corona) alrededor de dos círculos de radio r1 y r2 separados c: lo que queda entre la
    envolvente de los dos círculos agrandados ``outer`` y la de los dos achicados ``inner``."""
    def hull(dr: float) -> Node:
        a = make_node("circle")
        a.params = {"r": round(r1 + dr, 4), "$fn": 96}
        b = make_node("circle")
        b.params = {"r": round(r2 + dr, 4), "$fn": 96}
        h = make_node("hull")
        h.children = [a, Node(kind="translate", params={"v": [round(c, 6), 0, 0]}, children=[b])]
        return h
    diff = make_node("difference")
    diff.children = [hull(outer), hull(-inner)]
    ext = make_node("linear_extrude")
    ext.params = {"height": round(height, 4)}
    ext.children = [diff]
    inner_node: Node = ext
    if round(z, 6):
        inner_node = Node(kind="translate", params={"v": [0, 0, round(z, 6)]}, children=[ext])
    col = make_node("color", name)
    col.params = {"c": "DimGray"}
    col.children = [inner_node]
    return col


def _belt_parts(sol: BeltSolution, params: dict, u_fn) -> list[Node]:
    d1, d2 = sol.diameters
    if sol.kind == "pulley":
        # Del Ø exterior de la polea (donde apoya la correa) hacia fuera, el alto del diente más la
        # distancia a la línea primitiva, por los dos lados: un lomo aproximado, no el de la tabla.
        dims = gears.pulley_dims(sol.section, int(sol.driver))
        o1 = dims["outer_d"] / 2
        o2 = gears.pulley_dims(sol.section, int(sol.driven))["outer_d"] / 2
        thick = dims["tooth_height"] + 2 * dims["pld"]
        width = float(params.get("width", 6))
        # Con pestaña inferior el dentado empieza encima de ella (como en el módulo pulley).
        bottom = params.get("flange") in ("ambas", "inferior")
        z0 = float(params.get("flange_height", SPECS["pulley"].param("flange_height").default)) if bottom else 0.0
        # 0.1 mm de aire para que los lados rectos del círculo facetado no se metan en la polea, y 0.05
        # arriba y abajo para que no toque las pestañas.
        return [_band(o1, o2, sol.center, -0.1, thick, max(0.1, width - 0.1), z0 + 0.05, u_fn(tr("Correa")))]
    # En V: un anillo por ranura, de la mitad de la profundidad bajo el Ø primitivo hasta un poco por
    # encima. De sección rectangular, con el ancho que tiene la ranura en su parte más honda, para que
    # quepa dentro de la V sin tocar los flancos.
    dims = gears.v_pulley_dims(sol.section, d1, int(params.get("grooves", 1)))
    depth = dims["groove_depth"]
    width = dims["groove_width"] - depth * math.tan(math.radians(dims["groove_angle"] / 2)) - 0.4
    out = []
    for k in range(dims["grooves"]):
        z = dims["edge_distance"] + k * dims["groove_spacing"] - width / 2
        name = tr("Correa") if dims["grooves"] == 1 else tr("Correa {n}").format(n=k + 1)
        out.append(_band(d1 / 2, d2 / 2, sol.center, depth / 2, depth * 0.15, width, z, u_fn(name)))
    return out
