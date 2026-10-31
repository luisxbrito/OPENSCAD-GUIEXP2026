"""Redondear y achaflanar aristas: convierte cube ↔ cube_edges y cylinder ↔ cylinder_edges.

Una arista se identifica por (id del nodo, clave), por ejemplo (12, "x1y1") o (7, "top"). La
clave se refiere a la primitiva y no a la malla final, así que sigue siendo válida aunque
cambien las medidas de la pieza.
"""

from __future__ import annotations

from typing import Any, Iterable

from .i18n import tr
from .library import CUBE_EDGE_KEYS, CYLINDER_EDGE_KEYS
from .model import Document, Expr, Node, as_factor

ROUNDABLE = {"cube": CUBE_EDGE_KEYS, "cube_edges": CUBE_EDGE_KEYS,
             "cylinder": CYLINDER_EDGE_KEYS, "cylinder_edges": CYLINDER_EDGE_KEYS}
MODES = ("round", "chamfer", "none")


def cylinder_problem(node: Node) -> str:
    """Por qué no se pueden redondear los bordes de este cilindro ('' si se puede)."""
    if any(k in node.params for k in ("r1", "r2", "d1", "d2")):
        return tr("Solo se pueden redondear cilindros rectos (con r o d, sin r1/r2).")
    return ""


def _radius(node: Node) -> Any:
    p = node.params
    if "r" in p:
        return p["r"]
    d = p.get("d")
    if d is None:
        return 1  # valor por defecto de OpenSCAD
    if isinstance(d, (int, float)) and not isinstance(d, bool):
        return d / 2
    return Expr(f"{as_factor(d)} / 2")


def _drop_default_name(node: Node) -> None:
    """Un nombre igual a la palabra de OpenSCAD ("cube") dejaría de serlo al cambiar de tipo."""
    if node.name == node.kind:
        node.name = ""


def _to_rounded(node: Node, keys: list) -> None:
    _drop_default_name(node)
    p = node.params
    if node.kind == "cube":
        params = {"size": p.get("size", 1)}
        if "center" in p:
            params["center"] = p["center"]
        node.kind = "cube_edges"
    else:
        problem = cylinder_problem(node)
        if problem:
            raise ValueError(problem)
        params = {"h": p.get("h", 1), "r": _radius(node)}
        if "center" in p:
            params["center"] = p["center"]
        node.kind = "cylinder_edges"
    for key in ("$fn", "$fa", "$fs"):
        if key in p:
            params[key] = p[key]
    params["edges"] = keys
    node.params = params


def _to_plain(node: Node) -> None:
    _drop_default_name(node)
    p = node.params
    keep = ("size", "center") if node.kind == "cube_edges" else ("h", "r", "center")
    node.kind = "cube" if node.kind == "cube_edges" else "cylinder"
    node.params = {k: v for k, v in p.items() if k in keep or k.startswith("$")}


def finish_edges(doc: Document, edges: Iterable[tuple[int, str]], mode: str, value: float) -> list[int]:
    """Redondea (``round``), achaflana (``chamfer``) o deja vivas (``none``) las aristas indicadas.

    Hay un solo valor por pieza: aplicarlo cambia también las aristas que ya estaban tratadas.
    Devuelve los ids de los nodos que cambiaron. Lanza ValueError si alguna no se puede.
    """
    if mode not in MODES:
        raise ValueError(mode)
    if mode != "none" and not value > 0:
        raise ValueError(tr("El radio o la distancia tiene que ser mayor que 0."))
    by_node: dict[int, list[str]] = {}
    for nid, key in edges:
        by_node.setdefault(nid, [])
        if key not in by_node[nid]:
            by_node[nid].append(key)

    plans = []  # primero se comprueba todo; así un error no deja el modelo a medias
    for nid, keys in by_node.items():
        node = doc.find(nid)
        if not isinstance(node, Node) or node.kind not in ROUNDABLE:
            raise ValueError(tr("Solo se pueden redondear aristas de cube y cylinder."))
        valid = ROUNDABLE[node.kind]
        if any(k not in valid for k in keys):
            raise ValueError(f"Arista desconocida: {keys}")
        if node.kind == "cylinder" and mode != "none" and cylinder_problem(node):
            raise ValueError(cylinder_problem(node))
        current = node.params.get("edges", []) if node.kind.endswith("_edges") else []
        if not isinstance(current, list):
            raise ValueError(tr("Las aristas de esta pieza dependen de una expresión: edítalas en el código."))
        chosen = set(current) - set(keys) if mode == "none" else set(current) | set(keys)
        plans.append((node, [k for k in valid if k in chosen]))

    changed = []
    for node, chosen in plans:
        rounded = node.kind.endswith("_edges")
        if not chosen:
            if rounded:
                _to_plain(node)
                changed.append(node.id)
            continue
        if rounded:
            node.params["edges"] = chosen
        else:
            _to_rounded(node, chosen)
        if mode != "none":
            node.params.pop("rounding" if mode == "chamfer" else "chamfer", None)
            node.params[mode if mode == "chamfer" else "rounding"] = value
        changed.append(node.id)
    return changed
