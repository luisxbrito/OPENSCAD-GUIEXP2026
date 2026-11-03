"""Árbol de levas completo (sin Qt): reparto de los lóbulos y comprobaciones del conjunto.

El eje (``camshaft_main_shaft``) y cada lóbulo (``cam_lobe``) son piezas separadas del modelo; el
asistente solo propone un reparto inicial, que luego se cambia lóbulo a lóbulo. No impone ningún
motor: el número de cilindros, cuántos lóbulos lleva cada uno, las separaciones, el desfase entre
cilindros, el orden en que se reparten esos desfases y el ángulo entre admisión y escape los pone
el usuario. Todo en grados del árbol de levas y en el sentido de ``angle`` de cam_lobe.

Las comprobaciones (``shaft_problems``) miran los lóbulos que están junto al eje en el mismo
contenedor, con sus propios ``position`` y ``width``: lóbulos que se solapan, lóbulos fuera del eje y
radios base menores que el del eje.
"""

from __future__ import annotations

from typing import Callable, Optional

from .i18n import tr
from .model import Node, make_node

N_ = str  # marca un texto que se traduce después con tr() (lo recoge test_i18n)

# Parámetros del lóbulo que el asistente reparte igual a todos.
LOBE_SHARED = ("base_r", "lift", "width", "rise_angle", "dwell_angle", "fall_angle", "motion", "step",
               "profile", "nose_r")


def parse_order(text: str, cylinders: int) -> list[int]:
    """'1-3-4-2' → [1, 3, 4, 2]. Vacío: 1, 2, 3… Tiene que nombrar cada cilindro una vez."""
    text = (text or "").strip()
    if not text:
        return list(range(1, cylinders + 1))
    parts = [p for p in text.replace(",", "-").replace(" ", "-").split("-") if p]
    try:
        order = [int(p) for p in parts]
    except ValueError:
        raise ValueError(tr("El orden tiene que ser una lista de números de cilindro, como 1-3-4-2.")) from None
    if sorted(order) != list(range(1, cylinders + 1)):
        raise ValueError(tr("El orden tiene que nombrar una vez cada cilindro del 1 al {n}.").format(n=cylinders))
    return order


def layout(cylinders: int, per_cylinder: int, first_z: float, pitch: float, pair_gap: float,
           cylinder_offset: float, pair_angle: float, order: Optional[list[int]] = None,
           start_angle: float = 0.0) -> list[dict]:
    """Posición y ángulo de cada lóbulo.

    El cilindro c (1 es el más cercano a z = 0) va en z = first_z + (c - 1)·pitch. Su ángulo es
    start_angle + k·cylinder_offset, con k el puesto de c en ``order``. Con dos lóbulos por cilindro,
    el de escape va pair_gap más allá en el eje y pair_angle más girado que el de admisión."""
    if cylinders < 1 or per_cylinder not in (1, 2):
        raise ValueError(tr("Hace falta al menos un cilindro, con uno o dos lóbulos."))
    order = order or list(range(1, cylinders + 1))
    out = []
    for c in range(1, cylinders + 1):
        z = first_z + (c - 1) * pitch
        a = (start_angle + order.index(c) * cylinder_offset) % 360
        if per_cylinder == 1:
            out.append({"cylinder": c, "kind": "single", "position": z, "angle": round(a, 6)})
        else:
            out.append({"cylinder": c, "kind": "intake", "position": z, "angle": round(a, 6)})
            out.append({"cylinder": c, "kind": "exhaust", "position": z + pair_gap,
                        "angle": round((a + pair_angle) % 360, 6)})
    return out


def lobe_name(item: dict) -> str:
    return {"intake": tr("Admisión {n}"), "exhaust": tr("Escape {n}"),
            "single": tr("Leva {n}")}[item["kind"]].format(n=item["cylinder"])


def _num(params: dict, key: str, default: float) -> Optional[float]:
    v = params.get(key, default)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def shaft_problems(shaft: Optional[dict], lobes: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Problemas del conjunto: (texto en español, valores para format). ``lobes`` son pares
    (nombre, parámetros); los que tienen expresiones en vez de números no se comprueban."""
    out = []
    spans = []
    for name, p in lobes:
        z, w, r = _num(p, "position", 20), _num(p, "width", 12), _num(p, "base_r", 15)
        if None in (z, w, r):
            continue
        spans.append((z - w / 2, z + w / 2, name, r))
    spans.sort()
    for (a0, a1, a, _), (b0, b1, b, _) in zip(spans, spans[1:]):
        if b0 < a1 - 1e-9:
            out.append((N_("Los lóbulos {a} y {b} se solapan en el eje (de z = {z0:g} a {z1:g})."),
                        {"a": a, "b": b, "z0": round(b0, 3), "z1": round(min(a1, b1), 3)}))
    length = _num(shaft or {}, "length", 250) if shaft is not None else None
    d = _num(shaft or {}, "d", 25) if shaft is not None else None
    for z0, z1, name, r in spans:
        if length is not None and (z0 < -1e-9 or z1 > length + 1e-9):
            out.append((N_("El lóbulo {a} se sale del eje: ocupa de z = {z0:g} a {z1:g} y el eje va de 0 a {l:g}."),
                        {"a": name, "z0": round(z0, 3), "z1": round(z1, 3), "l": length}))
        if d is not None and r < d / 2:
            out.append((N_("El radio base de {a} ({r:g} mm) es menor que el radio del eje ({s:g} mm): el "
                           "seguidor tocaría el eje."), {"a": name, "r": r, "s": d / 2}))
    return out


def siblings(doc, node: Node) -> tuple[Optional[Node], list[Node]]:
    """El eje y los lóbulos que están en el mismo contenedor que ``node`` (si aún no está en el
    documento, solo él)."""
    group = doc.parent_list(node.id)[0]
    if group is None:
        group = [node]
    shafts = [n for n in group if n.kind == "camshaft_main_shaft"]
    return (shafts[0] if shafts else None), [n for n in group if n.kind == "cam_lobe"]


def create_camshaft(shaft: dict, lobe: dict, items: list[dict],
                    unique_fn: Optional[Callable[[str], str]] = None) -> Node:
    """Grupo con el eje y un lóbulo por elemento de ``layout``; ``lobe`` son los parámetros comunes."""
    u_fn = unique_fn or (lambda s: s)
    group = make_node("group", u_fn(tr("Árbol de levas")))
    axis = make_node("camshaft_main_shaft", u_fn(tr("Eje")))
    axis.params.update({k: shaft[k] for k in ("length", "d")})
    group.children.append(axis)
    for item in items:
        node = make_node("cam_lobe", u_fn(lobe_name(item)))
        node.params.update({k: lobe[k] for k in LOBE_SHARED if k in lobe})
        if node.params.get("profile") != "periforme":
            node.params.pop("nose_r", None)
        node.params.update(position=item["position"], angle=item["angle"])
        group.children.append(node)
    return group
