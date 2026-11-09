"""Árbol de levas completo (sin Qt): reparto de los lóbulos y comprobaciones del conjunto.

El eje (``camshaft_main_shaft``), cada lóbulo (``cam_lobe``), los muñones de apoyo (``camshaft_bearing``)
y los extremos (``camshaft_end``) son piezas del modelo; el asistente propone un reparto inicial
completo (lóbulos, apoyos y extremos) que luego se puede ajustar pieza a pieza en el árbol del proyecto.
No impone ningún motor: el número de cilindros, cuántos lóbulos lleva cada uno, las separaciones, el
desfase entre cilindros, el orden en que se reparten esos desfases y el ángulo entre admisión y escape
los pone el usuario. Todo en grados del árbol de levas y en el sentido de ``angle`` de cam_lobe.

Las comprobaciones (``shaft_problems``) miran los componentes que están junto al eje en el mismo
contenedor: lóbulos y muñones que se solapan, piezas fuera del eje, diámetros menores que el del eje,
radios base insuficientes y compatibilidad con cojinetes en túnel.
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


def bearing_layout(cylinders: int, per_cylinder: int, first_z: float, pitch: float, pair_gap: float,
                   shaft_length: float, bearing_width: float = 15.0) -> list[dict]:
    """Posiciones de los muñones de apoyo: delantero, intermedios entre cilindros y trasero.

    Para N cilindros se proponen N + 1 apoyos centrados en los huecos disponibles."""
    if cylinders < 1:
        return []
    out = []
    # Muñón delantero (antes del cilindro 1)
    z_front = max(bearing_width / 2, first_z / 2)
    out.append({"index": 1, "position": round(z_front, 3), "width": bearing_width})

    # Muñones intermedios (entre cilindro c y c+1)
    gap = pair_gap if per_cylinder == 2 else 0.0
    for c in range(1, cylinders):
        z_end_c = first_z + (c - 1) * pitch + gap
        z_start_next = first_z + c * pitch
        z_mid = (z_end_c + z_start_next) / 2
        out.append({"index": c + 1, "position": round(z_mid, 3), "width": bearing_width})

    # Muñón trasero (después del último cilindro)
    z_last = first_z + (cylinders - 1) * pitch + gap
    z_rear = (z_last + shaft_length) / 2
    out.append({"index": cylinders + 1, "position": round(z_rear, 3), "width": bearing_width})
    return out


def lobe_name(item: dict) -> str:
    return {"intake": tr("Admisión {n}"), "exhaust": tr("Escape {n}"),
            "single": tr("Leva {n}")}[item["kind"]].format(n=item["cylinder"])


def bearing_name(index: int) -> str:
    return tr("Muñón {n}").format(n=index)


def end_name(kind: str) -> str:
    return {"front": tr("Extremo delantero"), "rear": tr("Extremo trasero")}.get(kind, tr("Extremo"))


def _num(params: dict, key: str, default: float) -> Optional[float]:
    v = params.get(key, default)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def shaft_problems(shaft: Optional[dict], lobes: list[tuple[str, dict]],
                   bearings: Optional[list[tuple[str, dict]]] = None,
                   tunnel_bearings: bool = True) -> list[tuple[str, dict]]:
    """Problemas del conjunto: (texto en español, valores para format). ``lobes`` y ``bearings``
    son pares (nombre, parámetros); los que tienen expresiones en vez de números no se comprueban."""
    out = []
    lobe_spans = []
    max_lobe_r = 0.0
    max_lobe_name = ""

    for name, p in lobes:
        z = _num(p, "position", 20)
        w = _num(p, "width", 12)
        r = _num(p, "base_r", 15)
        lift = _num(p, "lift", 8) or 0.0
        if None in (z, w, r):
            continue
        lobe_spans.append((z - w / 2, z + w / 2, name, r, lift))
        outer_r = r + max(0.0, lift)
        if outer_r > max_lobe_r:
            max_lobe_r = outer_r
            max_lobe_name = name

    lobe_spans.sort()
    for (a0, a1, a, _, _), (b0, b1, b, _, _) in zip(lobe_spans, lobe_spans[1:]):
        if b0 < a1 - 1e-9:
            out.append((N_("Los lóbulos {a} y {b} se solapan en el eje (de z = {z0:g} a {z1:g})."),
                        {"a": a, "b": b, "z0": round(b0, 3), "z1": round(min(a1, b1), 3)}))

    length = _num(shaft or {}, "length", 250) if shaft is not None else None
    d = _num(shaft or {}, "d", 25) if shaft is not None else None

    for z0, z1, name, r, _ in lobe_spans:
        if length is not None and (z0 < -1e-9 or z1 > length + 1e-9):
            out.append((N_("El lóbulo {a} se sale del eje: ocupa de z = {z0:g} a {z1:g} y el eje va de 0 a {l:g}."),
                        {"a": name, "z0": round(z0, 3), "z1": round(z1, 3), "l": length}))
        if d is not None and r < d / 2:
            out.append((N_("El radio base de {a} ({r:g} mm) es menor que el radio del eje ({s:g} mm): el "
                           "seguidor tocaría el eje."), {"a": name, "r": r, "s": d / 2}))

    # Comprobaciones de los muñones de apoyo
    bearing_spans = []
    if bearings:
        for name, p in bearings:
            z = _num(p, "position", 0)
            w = _num(p, "width", 15)
            bd = _num(p, "d", 28)
            if None in (z, w, bd):
                continue
            bearing_spans.append((z - w / 2, z + w / 2, name, bd))

        bearing_spans.sort()
        # Solape entre muñones
        for (a0, a1, a, _), (b0, b1, b, _) in zip(bearing_spans, bearing_spans[1:]):
            if b0 < a1 - 1e-9:
                out.append((N_("Los muñones {a} y {b} se solapan en el eje (de z = {z0:g} a {z1:g})."),
                            {"a": a, "b": b, "z0": round(b0, 3), "z1": round(min(a1, b1), 3)}))

        # Muñones fuera del eje o menores que el eje
        for z0, z1, name, bd in bearing_spans:
            if length is not None and (z0 < -1e-9 or z1 > length + 1e-9):
                out.append((N_("El muñón {a} se sale del eje: ocupa de z = {z0:g} a {z1:g} y el eje va de 0 a {l:g}."),
                            {"a": name, "z0": round(z0, 3), "z1": round(z1, 3), "l": length}))
            if d is not None and bd < d:
                out.append((N_("El muñón {a} (Ø {d:g} mm) es menor que el diámetro del eje ({s:g} mm)."),
                            {"a": name, "d": bd, "s": d}))

        # Solape entre muñón y lóbulo
        for b0, b1, b_name, _ in bearing_spans:
            for l0, l1, l_name, _, _ in lobe_spans:
                ov0 = max(b0, l0)
                ov1 = min(b1, l1)
                if ov0 < ov1 - 1e-9:
                    out.append((N_("El muñón {b} y el lóbulo {a} se solapan en el eje (de z = {z0:g} a {z1:g})."),
                                {"b": b_name, "a": l_name, "z0": round(ov0, 3), "z1": round(ov1, 3)}))

        # Cojinetes en túnel (enterizos): el diámetro del muñón debe superar la envolvente máxima de la leva
        if tunnel_bearings and max_lobe_r > 0:
            max_lobe_d = 2 * max_lobe_r
            for _, _, b_name, bd in bearing_spans:
                if bd < max_lobe_d - 1e-9:
                    out.append((N_("El muñón {b} (Ø {d:g} mm) es menor que la envolvente del lóbulo más alto ({a}, Ø {d_max:g} mm): "
                                   "con cojinetes enteros (en túnel) el árbol no podría introducirse en el motor."),
                                {"b": b_name, "d": bd, "a": max_lobe_name, "d_max": round(max_lobe_d, 3)}))

    return out


class CamshaftSiblings(tuple):
    """Tupla de 2 elementos (shaft, lobes) para compatibilidad hacia atrás,
    con atributos adicionales .bearings y .ends."""
    shaft: Optional[Node]
    lobes: list[Node]
    bearings: list[Node]
    ends: list[Node]

    def __new__(cls, shaft: Optional[Node], lobes: list[Node],
                bearings: Optional[list[Node]] = None, ends: Optional[list[Node]] = None):
        return super().__new__(cls, (shaft, lobes))

    def __init__(self, shaft: Optional[Node], lobes: list[Node],
                 bearings: Optional[list[Node]] = None, ends: Optional[list[Node]] = None):
        self.shaft = shaft
        self.lobes = lobes
        self.bearings = bearings or []
        self.ends = ends or []


def siblings(doc, node: Node) -> CamshaftSiblings:
    """El eje, lóbulos, apoyos y extremos que están en el mismo contenedor que ``node``."""
    group = doc.parent_list(node.id)[0]
    if group is None:
        group = [node]
    shafts = [n for n in group if n.kind == "camshaft_main_shaft"]
    lobes = [n for n in group if n.kind == "cam_lobe"]
    bearings = [n for n in group if n.kind == "camshaft_bearing"]
    ends = [n for n in group if n.kind == "camshaft_end"]
    return CamshaftSiblings(shafts[0] if shafts else None, lobes, bearings, ends)


def create_camshaft(shaft: dict, lobe: dict, items: list[dict],
                    arg4: Optional[Callable[[str], str] | list[dict]] = None,
                    bearings: Optional[list[dict]] = None,
                    ends: Optional[list[dict]] = None,
                    unique_fn: Optional[Callable[[str], str]] = None) -> Node:
    """Grupo con el eje, lóbulos, muñones y extremos del árbol de levas."""
    if callable(arg4):
        u_fn = arg4
    elif isinstance(arg4, list):
        bearings = arg4
        u_fn = unique_fn or (lambda s: s)
    else:
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
    if bearings:
        for b in bearings:
            b_node = make_node("camshaft_bearing", u_fn(bearing_name(b.get("index", 1))))
            b_node.params.update({k: v for k, v in b.items() if k != "index"})
            group.children.append(b_node)
    if ends:
        for e in ends:
            e_node = make_node("camshaft_end", u_fn(end_name(e.get("kind", "front"))))
            e_node.params.update({k: v for k, v in e.items() if k != "kind"})
            group.children.append(e_node)
    return group
