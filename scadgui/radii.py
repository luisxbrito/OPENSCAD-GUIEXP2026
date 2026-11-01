"""Radios de sphere, circle y cylinder sin parámetros que choquen.

OpenSCAD admite r o d, y en cylinder también r1/d1 (base) y r2/d2 (tapa). Si se dan a la vez
dos que dicen lo mismo, avisa ("Ignoring radius variable…" o "Cylinder parameters ambiguous")
y aplica unas reglas de prioridad (src/core/primitives.cc, lookup_radius):

* d manda sobre r, d1 sobre r1 y d2 sobre r2;
* en cylinder, r (o d) fija las dos tapas y r1/d1 o r2/d2, si están, la sustituyen.

Aquí se usan esas mismas reglas para dejar solo los parámetros que hacen falta sin cambiar la
forma que OpenSCAD ya calcula.
"""

from __future__ import annotations

from typing import Any, Optional

from .i18n import tr
from .model import Expr, Node, as_factor

KINDS = {"sphere", "circle", "cylinder"}
# Parámetro → (lado, forma): lado "" es todo el cilindro; "1" la base y "2" la tapa.
_ROLE = {"r": ("", "r"), "d": ("", "d"), "r1": ("1", "r"), "d1": ("1", "d"), "r2": ("2", "r"), "d2": ("2", "d")}


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _half(v):
    return v / 2 if _number(v) else Expr(f"{as_factor(v)} / 2")


def _double(v):
    return v * 2 if _number(v) else Expr(f"2 * {as_factor(v)}")


def _radius(p: dict, side: str) -> Optional[Any]:
    """Radio de un lado según las reglas de OpenSCAD (None si no se indica)."""
    if "d" + side in p:
        return _half(p["d" + side])
    return p.get("r" + side)


def effective_radius(node: Node, side: str = "") -> Any:
    """Radio que usa OpenSCAD para ese lado ("" en sphere/circle; "1" o "2" en cylinder)."""
    p = node.params
    if side:
        own = _radius(p, side)
        if own is not None:
            return own
    base = _radius(p, "")
    return 1 if base is None else base


def conflicts(node: Node) -> list[str]:
    """Avisos que daría OpenSCAD con los parámetros actuales (vacío si no hay ninguno)."""
    if not isinstance(node, Node) or node.kind not in KINDS:
        return []
    p = node.params
    out = []
    for side in ("", "1", "2") if node.kind == "cylinder" else ("",):
        if "r" + side in p and "d" + side in p:
            out.append(tr("{d} y {r} a la vez: OpenSCAD usa {d} e ignora {r}.").format(d="d" + side, r="r" + side))
    if node.kind == "cylinder" and ("r" in p or "d" in p) and any(k in p for k in ("r1", "r2", "d1", "d2")):
        out.append(tr("Radio general (r o d) junto con el de la base o la tapa: OpenSCAD avisa "
                      "\"Cylinder parameters ambiguous\"."))
    return out


def normalize(node: Node, added: str = "", edited: str = "") -> bool:
    """Quita los parámetros que sobran conservando la forma. Devuelve si cambió algo.

    ``added`` es el parámetro que se acaba de activar en el panel: si es el radio general (r o
    d) de un cilindro, se entiende que se quiere un cilindro recto y se quitan los de base y
    tapa; si es uno de base o tapa, el radio general se reparte en el lado que falte.
    ``edited`` es el que se acaba de cambiar: entre r y d (o r1 y d1…) se conserva ese.
    """
    if not isinstance(node, Node) or node.kind not in KINDS:
        return False
    p = node.params
    before = dict(p)
    for side in ("", "1", "2") if node.kind == "cylinder" else ("",):
        if "r" + side in p and "d" + side in p:
            chosen = added or edited
            keep = chosen if chosen in ("r" + side, "d" + side) else "d" + side  # como OpenSCAD: manda d
            p.pop("r" + side if keep.startswith("d") else "d" + side)
    if node.kind == "cylinder" and ("r" in p or "d" in p) and any(k in p for k in ("r1", "r2", "d1", "d2")):
        if _ROLE.get(added, ("x",))[0] == "":
            for k in ("r1", "r2", "d1", "d2"):
                p.pop(k, None)
        else:
            form = "d" if "d" in p else "r"
            base = p.pop(form)
            for side in ("1", "2"):
                if "r" + side not in p and "d" + side not in p:
                    p[form + side] = base
    return p != before


def initial_value(node: Node, key: str, default: Any) -> Any:
    """Valor con el que se activa un radio en el panel: el que ya tiene la pieza, para que no cambie."""
    if not isinstance(node, Node) or node.kind not in KINDS or key not in _ROLE or key in node.params:
        return default
    side, form = _ROLE[key]
    if not any(k in node.params for k in _ROLE):
        return default
    # Un radio general en un cono: el cilindro recto toma el radio de la base.
    r = effective_radius(node, side or ("1" if node.kind == "cylinder" else ""))
    return _double(r) if form == "d" else r
