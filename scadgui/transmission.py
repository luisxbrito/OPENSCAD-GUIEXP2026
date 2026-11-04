"""Calculadora de transmisiones por engranajes (sin Qt): busca los dientes para una relación pedida y
crea el tren ya colocado.

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
