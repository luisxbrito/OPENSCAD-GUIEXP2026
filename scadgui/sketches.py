"""Perfiles 2D paramétricos (rectángulo redondeado, ranura, polígono, estrella, corona, L).

Cada perfil se construye con nodos normales de OpenSCAD (square, circle, offset, hull,
polygon…), así que después se editan en el árbol como cualquier otra pieza.
"""

from __future__ import annotations

import math
from typing import Callable

from .i18n import tr
from .model import Node, make_node


PROFILES = (
    ("rounded_rect", "Rectángulo redondeado"),
    ("slot", "Ranura / Chavetero"),
    ("regular_polygon", "Polígono regular"),
    ("star", "Estrella paramétrica"),
    ("ring", "Corona / Anillo"),
    ("l_profile", "Perfil en L"),
)


def create_sketch_node(profile: str, params: dict, unique_name_fn: Callable[[str], str],
                       extrude_3d: bool = False, extrude_h: float = 10.0) -> Node:
    """Construye un árbol de Node estándar de OpenSCAD para el perfil 2D elegido.

    Los nombres de las piezas salen en el idioma de la interfaz.
    """
    if profile == "rounded_rect":
        w = float(params.get("w", 40.0))
        h = float(params.get("h", 25.0))
        r = float(params.get("r", 3.0))
        center = bool(params.get("center", True))
        if r > 0.001:
            w_inner = max(0.1, w - 2 * r)
            h_inner = max(0.1, h - 2 * r)
            off = make_node("offset", unique_name_fn(tr("Redondeo")))
            off.params["r"] = round(r, 4)
            sq = make_node("square", unique_name_fn(tr("Base")))
            sq.params["size"] = [round(w_inner, 4), round(h_inner, 4)]
            sq.params["center"] = center
            off.children.append(sq)
            root = off
        else:
            sq = make_node("square", unique_name_fn(tr("Rectángulo")))
            sq.params["size"] = [round(w, 4), round(h, 4)]
            sq.params["center"] = center
            root = sq

    elif profile == "slot":
        l = float(params.get("l", 30.0))
        r = float(params.get("r", 5.0))
        hull = make_node("hull", unique_name_fn(tr("Ranura")))
        t1 = make_node("translate", unique_name_fn(tr("Extremo 1")))
        t1.params["v"] = [-round(l / 2, 4), 0, 0]
        c1 = make_node("circle", unique_name_fn(tr("Círculo 1")))
        c1.params["r"] = round(r, 4)
        t1.children.append(c1)
        t2 = make_node("translate", unique_name_fn(tr("Extremo 2")))
        t2.params["v"] = [round(l / 2, 4), 0, 0]
        c2 = make_node("circle", unique_name_fn(tr("Círculo 2")))
        c2.params["r"] = round(r, 4)
        t2.children.append(c2)
        hull.children.extend([t1, t2])
        root = hull

    elif profile == "regular_polygon":
        n = int(params.get("n", 6))
        r = float(params.get("r", 15.0))
        c = make_node("circle", unique_name_fn(tr("Polígono de {n} lados").format(n=n)))
        c.params["r"] = round(r, 4)
        c.params["$fn"] = max(3, n)
        root = c

    elif profile == "star":
        p = int(params.get("p", 5))
        r1 = float(params.get("r1", 20.0))
        r2 = float(params.get("r2", 9.0))
        p = max(3, p)
        points = []
        for i in range(2 * p):
            rad = r1 if i % 2 == 0 else r2
            angle = math.pi / 2 - i * (math.pi / p)
            points.append([round(rad * math.cos(angle), 4), round(rad * math.sin(angle), 4)])
        p_node = make_node("polygon", unique_name_fn(tr("Estrella de {p} puntas").format(p=p)))
        p_node.params["points"] = points
        root = p_node

    elif profile == "ring":
        r_ext = float(params.get("r_ext", 20.0))
        r_int = float(params.get("r_int", 12.0))
        if r_int >= r_ext:
            r_int = max(0.1, r_ext - 1.0)
        diff = make_node("difference", unique_name_fn(tr("Anillo")))
        c1 = make_node("circle", unique_name_fn(tr("Exterior")))
        c1.params["r"] = round(r_ext, 4)
        c2 = make_node("circle", unique_name_fn(tr("Interior")))
        c2.params["r"] = round(r_int, 4)
        diff.children.extend([c1, c2])
        root = diff

    elif profile == "l_profile":
        w = float(params.get("w", 30.0))
        h = float(params.get("h", 30.0))
        t = float(params.get("t", 4.0))
        t_safe = min(t, min(w, h) - 0.5)
        p_node = make_node("polygon", unique_name_fn(tr("Perfil en L")))
        p_node.params["points"] = [
            [0.0, 0.0],
            [round(w, 4), 0.0],
            [round(w, 4), round(t_safe, 4)],
            [round(t_safe, 4), round(t_safe, 4)],
            [round(t_safe, 4), round(h, 4)],
            [0.0, round(h, 4)],
        ]
        root = p_node

    else:
        raise ValueError(f"Perfil desconocido: {profile}")

    if extrude_3d:
        ext = make_node("linear_extrude", unique_name_fn(tr("Extrusión {name}").format(name=root.name)))
        ext.params["height"] = round(max(0.01, extrude_h), 4)
        ext.children.append(root)
        root = ext

    return root
