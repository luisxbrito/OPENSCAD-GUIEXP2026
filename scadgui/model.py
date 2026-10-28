"""Modelo de objetos ("el ORM") y generador de código OpenSCAD.

La idea es la misma que la de un ORM con una base de datos:

* La interfaz solo trabaja con objetos Python (``Node``) y sus propiedades.
* ``generate()`` traduce ese árbol de objetos a código ``.scad``.
* ``parser.parse()`` hace el camino inverso: lee un ``.scad`` y lo
  convierte en objetos. Lo que no sabe representar (bucles, variables,
  módulos propios...) lo guarda tal cual en un ``RawCode`` para no
  perderlo nunca.
"""

from __future__ import annotations

import copy
import itertools
import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from .catalog import SPECS, Spec

HEADER = "// Generado con OpenSCAD GUI Mejorada"
MODIFIERS = ("#", "%", "!", "*")

_VAR_RE = re.compile(r"^\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(.+?)\s*;\s*(?://\s*(.*))?$")


# Módulos cuyo primer argumento se escribe sin nombre, como es costumbre en OpenSCAD:
# cube([10, 10, 10]), translate([0, 0, 5]), color("red")...
FIRST_UNNAMED = {"cube", "square", "translate", "rotate", "scale", "mirror", "resize",
                 "multmatrix", "color", "text", "import", "surface"}

_ids = itertools.count(1)


def new_id() -> int:
    return next(_ids)


class Expr:
    """Expresión OpenSCAD que no es un literal simple (``x * 2``, ``[for ...]``...)."""

    __slots__ = ("text",)

    def __init__(self, text: str):
        self.text = text.strip()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Expr) and other.text == self.text

    def __hash__(self) -> int:
        return hash(self.text)

    def __repr__(self) -> str:
        return f"Expr({self.text!r})"


# --------------------------------------------------------------------------- valores

def format_number(x: float) -> str:
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if not math.isfinite(x):
        return "0"
    if float(x).is_integer():
        return str(int(x))
    text = f"{x:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def format_string(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def format_value(v: Any) -> str:
    if v is None:
        return "undef"
    if isinstance(v, Expr):
        return v.text
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return format_number(v)
    if isinstance(v, str):
        return format_string(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(format_value(x) for x in v) + "]"
    raise TypeError(f"Valor no soportado: {v!r}")


# --------------------------------------------------------------------------- nodos

@dataclass
class Node:
    kind: str
    params: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    name: str = ""
    modifier: str = ""
    id: int = field(default_factory=new_id)

    @property
    def spec(self) -> Optional[Spec]:
        return SPECS.get(self.kind)

    @property
    def is_container(self) -> bool:
        spec = self.spec
        return bool(spec and spec.container)

    @property
    def editable(self) -> bool:
        return True

    @property
    def label(self) -> str:
        if self.name:
            return self.name
        spec = self.spec
        return spec.label if spec else self.kind

    def call(self) -> str:
        """``cube([10, 10, 10], center = true)`` sin modificador ni punto y coma."""
        spec = self.spec
        ordered: list[str] = []
        if spec:
            ordered = [p.name for p in spec.params if p.name in self.params]
        ordered += [k for k in self.params if k not in ordered]
        parts = []
        for i, key in enumerate(ordered):
            value = format_value(self.params[key])
            if i == 0 and self.kind in FIRST_UNNAMED and spec and spec.positional and key == spec.positional[0]:
                parts.append(value)
            else:
                parts.append(f"{key} = {value}")
        return f"{self.kind}({', '.join(parts)})"


@dataclass
class RawCode:
    """Código que la interfaz no edita con botones: se conserva literal."""

    text: str
    is_comment: bool = False
    id: int = field(default_factory=new_id)
    name: str = ""
    modifier: str = ""

    kind = "__raw__"
    children: list = field(default_factory=list)  # siempre vacía

    @property
    def is_container(self) -> bool:
        return False

    @property
    def editable(self) -> bool:
        return False

    @property
    def spec(self) -> None:
        return None

    @property
    def label(self) -> str:
        first = self.text.strip().splitlines()[0] if self.text.strip() else ""
        return first if len(first) <= 48 else first[:45] + "..."


AnyNode = Any  # Node | RawCode


def make_node(kind: str, name: str = "") -> Node:
    spec = SPECS[kind]
    params = {p.name: copy.deepcopy(p.default) for p in spec.params if not p.optional}
    return Node(kind=kind, params=params, name=name)


def clean_name(name: str) -> str:
    return " ".join(name.replace("\r", " ").replace("\n", " ").split())


# --------------------------------------------------------------------------- documento

@dataclass
class Document:
    children: list = field(default_factory=list)
    fn: Optional[int] = None  # $fn global

    # ----- recorrido
    def walk(self) -> Iterator[tuple[AnyNode, int, Optional[Node]]]:
        """Recorre en orden de documento: (nodo, profundidad, padre)."""
        def rec(items, depth, parent):
            for n in items:
                yield n, depth, parent
                yield from rec(n.children, depth + 1, n)
        yield from rec(self.children, 0, None)

    def find(self, node_id: int) -> Optional[AnyNode]:
        for n, _, _ in self.walk():
            if n.id == node_id:
                return n
        return None

    def parent_list(self, node_id: int) -> tuple[Optional[list], Optional[Node]]:
        if any(n.id == node_id for n in self.children):
            return self.children, None
        for n, _, _ in self.walk():
            if any(c.id == node_id for c in n.children):
                return n.children, n
        return None, None

    def order(self) -> list[int]:
        return [n.id for n, _, _ in self.walk()]

    def is_descendant(self, node_id: int, ancestor_id: int) -> bool:
        anc = self.find(ancestor_id)
        if anc is None:
            return False
        stack = list(anc.children)
        while stack:
            n = stack.pop()
            if n.id == node_id:
                return True
            stack.extend(n.children)
        return False

    def unique_name(self, base: str) -> str:
        used = {n.name for n, _, _ in self.walk()}
        if base not in used:
            return base
        for i in itertools.count(1):
            cand = f"{base}{i:03d}"
            if cand not in used:
                return cand
        raise AssertionError

    # ----- operaciones (las usan los botones)
    def add(self, kind: str, target_id: Optional[int] = None) -> Node:
        """Crea una pieza. Si el destino es un contenedor, la mete dentro; si no, va al final."""
        node = make_node(kind, self.unique_name(SPECS[kind].label))
        target = self.find(target_id) if target_id is not None else None
        if target is not None and target.is_container:
            target.children.append(node)
        else:
            self.children.append(node)
        return node

    def _top_selection(self, ids) -> list[int]:
        """Ordena por documento y quita los que están dentro de otro seleccionado."""
        wanted = set(ids)
        result = []
        for nid in self.order():
            if nid in wanted and not any(self.is_descendant(nid, other) for other in result):
                result.append(nid)
        return result

    def wrap(self, ids, kind: str) -> Node:
        """Envuelve los nodos en un contenedor nuevo (translate, difference...)."""
        sel = self._top_selection(ids)
        if not sel:
            raise ValueError("No hay nada seleccionado")
        container = make_node(kind, self.unique_name(SPECS[kind].label))
        first_list, _ = self.parent_list(sel[0])
        index = next(i for i, n in enumerate(first_list) if n.id == sel[0])
        for nid in sel:
            lst, _ = self.parent_list(nid)
            node = next(n for n in lst if n.id == nid)
            lst.remove(node)
            container.children.append(node)
        first_list.insert(index, container)
        return container

    def wrap_ordered(self, ids: list[int], kind: str) -> Node:
        """Envuelve los nodos en un contenedor nuevo respetando exactamente el orden de ids."""
        sel = [nid for nid in ids if not any(self.is_descendant(nid, other) for other in ids if other != nid)]
        if not sel:
            raise ValueError("No hay nada seleccionado")
        container = make_node(kind, self.unique_name(SPECS[kind].label))
        first_list, _ = self.parent_list(sel[0])
        index = next(i for i, n in enumerate(first_list) if n.id == sel[0]) if first_list else len(self.children)
        for nid in sel:
            lst, _ = self.parent_list(nid)
            if lst is not None:
                node = next((n for n in lst if n.id == nid), None)
                if node is not None:
                    lst.remove(node)
                    container.children.append(node)
        if first_list is not None:
            first_list.insert(index, container)
        else:
            self.children.append(container)
        return container

    def set_difference_base(self, diff_id: int, new_base_id: int) -> bool:
        """Mueve el nodo new_base_id a la primera posición (base) de los hijos del difference."""
        diff = self.find(diff_id)
        if diff is None or getattr(diff, "kind", "") != "difference":
            return False
        for i, child in enumerate(diff.children):
            if child.id == new_base_id:
                if i != 0:
                    node = diff.children.pop(i)
                    diff.children.insert(0, node)
                return True
        return False

    def get_solids(self) -> list[tuple[int, str, str]]:
        """Devuelve una lista de (node_id, label, kind) de todos los nodos editables que no sean RawCode."""
        solids = []
        for n, _, _ in self.walk():
            if isinstance(n, Node):
                solids.append((n.id, n.label, n.kind))
        return solids

    def delete(self, ids) -> None:
        for nid in self._top_selection(ids):
            lst, _ = self.parent_list(nid)
            if lst is not None:
                lst[:] = [n for n in lst if n.id != nid]

    def move(self, node_id: int, delta: int) -> bool:
        lst, _ = self.parent_list(node_id)
        if lst is None:
            return False
        i = next(k for k, n in enumerate(lst) if n.id == node_id)
        j = i + delta
        if not 0 <= j < len(lst):
            return False
        lst[i], lst[j] = lst[j], lst[i]
        return True

    def outdent(self, node_id: int) -> bool:
        """Saca el nodo de su contenedor y lo deja justo después de él."""
        lst, parent = self.parent_list(node_id)
        if parent is None:
            return False
        grand, _ = self.parent_list(parent.id)
        node = next(n for n in lst if n.id == node_id)
        lst.remove(node)
        grand.insert(grand.index(parent) + 1, node)
        return True

    def indent(self, node_id: int) -> bool:
        """Mete el nodo en el contenedor que tiene justo encima."""
        lst, _ = self.parent_list(node_id)
        if lst is None:
            return False
        i = next(k for k, n in enumerate(lst) if n.id == node_id)
        if i == 0 or not lst[i - 1].is_container:
            return False
        node = lst.pop(i)
        lst[i - 1].children.append(node)
        return True

    def unwrap(self, node_id: int) -> bool:
        """Quita un contenedor dejando sus hijos en su lugar."""
        lst, _ = self.parent_list(node_id)
        node = self.find(node_id)
        if lst is None or node is None or not node.is_container:
            return False
        i = lst.index(node)
        lst[i:i + 1] = node.children
        return True

    def reparent(self, source_ids: list[int], target_id: Optional[int], position: str = "into") -> bool:
        """Mueve nodos a otro lugar del árbol (arrastrar y soltar).

        position puede ser:
          - "into": coloca los nodos dentro de target (debe ser contenedor) o en la raíz si target_id es None.
          - "before": coloca los nodos justo antes de target.
          - "after": coloca los nodos justo después de target.
        """
        sel = self._top_selection(source_ids)
        if not sel:
            return False

        if target_id is not None:
            for nid in sel:
                if nid == target_id or self.is_descendant(target_id, nid):
                    return False

        sources = []
        for nid in sel:
            lst, _ = self.parent_list(nid)
            if lst is not None:
                n = next((x for x in lst if x.id == nid), None)
                if n is not None:
                    sources.append(n)
        if not sources:
            return False

        if position == "into":
            if target_id is None:
                target_container = self.children
            else:
                target = self.find(target_id)
                if target is None or not target.is_container:
                    return False
                target_container = target.children

            for node in sources:
                lst, _ = self.parent_list(node.id)
                if lst is not None and node in lst:
                    lst.remove(node)
            target_container.extend(sources)
            return True

        if position in ("before", "after"):
            if target_id is None:
                return False
            target = self.find(target_id)
            if target is None or target in sources:
                return False

            for node in sources:
                lst, _ = self.parent_list(node.id)
                if lst is not None and node in lst:
                    lst.remove(node)

            target_list, _ = self.parent_list(target_id)
            if target_list is None or target not in target_list:
                return False
            idx = target_list.index(target)
            if position == "after":
                idx += 1
            target_list[idx:idx] = sources
            return True

        return False

    def duplicate(self, node_id: int) -> Optional[AnyNode]:
        lst, _ = self.parent_list(node_id)
        node = self.find(node_id)
        if lst is None or node is None:
            return None
        clone = copy.deepcopy(node)
        _renumber(clone)
        if clone.name:
            clone.name = self.unique_name(clone.name)
        lst.insert(lst.index(node) + 1, clone)
        return clone

    def set_param(self, node_id: int, key: str, value: Any) -> None:
        node = self.find(node_id)
        if value is None:
            node.params.pop(key, None)
        else:
            node.params[key] = value

    def get_variables(self) -> list[dict]:
        """Obtiene la lista de variables globales definidas en el documento."""
        vars_list = []
        for n in self.children:
            if isinstance(n, RawCode) and not n.is_comment:
                m = _VAR_RE.match(n.text.strip())
                if m:
                    name, val_str, comment = m.groups()
                    if name != "$fn":
                        vars_list.append({
                            "id": n.id,
                            "name": name,
                            "value": val_str,
                            "comment": comment or "",
                        })
        return vars_list

    def set_variable(self, name: str, value: Any, comment: str = "") -> RawCode:
        """Crea o actualiza una variable global en el documento."""
        clean_name = re.sub(r"[^a-zA-Z0-9_$]", "_", name).strip("_")
        if not clean_name or (clean_name[0].isdigit() and not clean_name.startswith("$")):
            clean_name = "var_" + clean_name

        val_str = str(value).strip() if isinstance(value, (str, Expr)) else format_value(value)
        comment_part = f" // {comment.strip()}" if comment.strip() else ""
        new_text = f"{clean_name} = {val_str};{comment_part}"

        for n in self.children:
            if isinstance(n, RawCode):
                m = _VAR_RE.match(n.text.strip())
                if m and m.group(1) == clean_name:
                    n.text = new_text
                    return n

        new_node = RawCode(new_text)
        idx = 0
        for i, c in enumerate(self.children):
            if isinstance(c, RawCode) and _VAR_RE.match(c.text.strip()):
                idx = i + 1
        self.children.insert(idx, new_node)
        return new_node

    def delete_variable(self, name: str) -> bool:
        """Elimina una variable global por su nombre."""
        for i, n in enumerate(self.children):
            if isinstance(n, RawCode):
                m = _VAR_RE.match(n.text.strip())
                if m and m.group(1) == name:
                    self.children.pop(i)
                    return True
        return False

    def collect_module_parameters(self, selected_ids: list[int]) -> list[dict]:
        """Recopila los parámetros configurables de los nodos seleccionados."""
        sel = self._top_selection(selected_ids)
        if not sel:
            return []

        nodes = []
        for nid in sel:
            root = self.find(nid)
            if root is not None:
                def walk_node(n):
                    nodes.append(n)
                    for c in n.children:
                        walk_node(c)
                walk_node(root)

        result = []
        used_names = set()

        for n in nodes:
            if not isinstance(n, Node):
                continue
            clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", n.name or n.kind).lower().strip("_")
            if not clean_name:
                clean_name = n.kind

            for key, val in n.params.items():
                if key.startswith("$") and key != "$fn":
                    continue
                if isinstance(val, (int, float, bool, str, list, tuple)):
                    base_var = f"{key}_{clean_name}" if len(clean_name) <= 12 else f"{clean_name}_{key}"
                    base_var = re.sub(r"[^a-zA-Z0-9_]", "_", base_var).lower().strip("_")
                    if not base_var or base_var[0].isdigit():
                        base_var = "p_" + base_var

                    cand = base_var
                    idx = 1
                    while cand in used_names:
                        idx += 1
                        cand = f"{base_var}_{idx}"
                    used_names.add(cand)

                    result.append({
                        "node_id": n.id,
                        "node_name": n.name or n.label,
                        "node_kind": n.kind,
                        "param_key": key,
                        "current_value": val,
                        "suggested_name": cand,
                        "enabled": True,
                    })

        return result

    def make_module(self, selected_ids: list[int], module_name: str,
                    bindings: list[dict]) -> tuple[RawCode, RawCode]:
        """Convierte las piezas seleccionadas en un module de OpenSCAD y las reemplaza por su llamada.

        bindings es una lista de diccionarios con:
          - "node_id": int
          - "param_key": str
          - "var_name": str
          - "default_value": Any
          - "enabled": bool
        """
        sel = self._top_selection(selected_ids)
        if not sel:
            raise ValueError("No hay piezas seleccionadas")

        clean_mod = re.sub(r"[^a-zA-Z0-9_]", "_", module_name).strip("_")
        if not clean_mod or clean_mod[0].isdigit():
            clean_mod = "mod_" + (clean_mod or "custom")

        first_list, _ = self.parent_list(sel[0])
        if first_list is None:
            raise ValueError("No se encontró la lista padre de la selección")
        insert_idx = next(i for i, n in enumerate(first_list) if n.id == sel[0])

        clones = [copy.deepcopy(self.find(nid)) for nid in sel]

        id_to_clone = {}
        def map_ids(n):
            id_to_clone[n.id] = n
            for c in n.children:
                map_ids(c)
        for c in clones:
            map_ids(c)

        active_bindings = []
        for b in bindings:
            if not b.get("enabled", True):
                continue
            nid = b["node_id"]
            pkey = b["param_key"]
            var_name = re.sub(r"[^a-zA-Z0-9_]", "_", b.get("var_name") or b.get("suggested_name") or "").strip("_")
            if not var_name or var_name[0].isdigit():
                var_name = "p_" + (var_name or pkey)

            if nid in id_to_clone and isinstance(id_to_clone[nid], Node):
                val = b.get("default_value", id_to_clone[nid].params.get(pkey))
                id_to_clone[nid].params[pkey] = Expr(var_name)
                active_bindings.append({
                    "var_name": var_name,
                    "default_value": val,
                })

        temp_doc = Document()
        temp_doc.children = clones
        body_lines = generate(temp_doc, header=False).text.splitlines()
        indented_body = "\n".join("  " + l if l.strip() else "" for l in body_lines)

        args_str = ", ".join(f"{b['var_name']} = {format_value(b['default_value'])}"
                             for b in active_bindings)
        module_text = f"module {clean_mod}({args_str}) {{\n{indented_body}\n}}\n"
        module_node = RawCode(module_text)

        call_label = clean_mod.replace("_", " ").title()
        call_text = f"{clean_mod}({args_str}); // {call_label}"
        call_node = RawCode(call_text)

        for nid in sel:
            lst, _ = self.parent_list(nid)
            if lst is not None:
                node = next((n for n in lst if n.id == nid), None)
                if node is not None:
                    lst.remove(node)

        first_list.insert(insert_idx, call_node)
        self.children.insert(0, module_node)

        return module_node, call_node

    def snapshot(self) -> "Document":
        return copy.deepcopy(self)


def _renumber(node: AnyNode) -> None:
    node.id = new_id()
    for c in node.children:
        _renumber(c)


# --------------------------------------------------------------------------- generador

@dataclass
class Generated:
    text: str
    lines: dict  # id -> (primera_linea, ultima_linea), base 0

    def node_at(self, line: int) -> Optional[int]:
        """El nodo más interno que ocupa esa línea."""
        best = None
        best_span = None
        for nid, (a, b) in self.lines.items():
            if a <= line <= b and (best_span is None or b - a < best_span):
                best, best_span = nid, b - a
        return best


def generate(doc: Document, highlight=(), header: bool = True) -> Generated:
    """Convierte el documento en código. ``highlight`` antepone ``#`` (solo para la vista previa)."""
    out: list[str] = []
    spans: dict = {}
    highlight = set(highlight)

    if header:
        out.append(HEADER)
    if doc.fn:
        out.append(f"$fn = {int(doc.fn)};")
    if out:
        out.append("")

    def emit(node: AnyNode, indent: str) -> None:
        start = len(out)
        if isinstance(node, RawCode):
            lines = node.text.splitlines() or [""]
            for ln in lines:
                out.append((indent + ln) if ln.strip() else "")
            spans[node.id] = (start, len(out) - 1)
            return
        mod = node.modifier
        if not mod and node.id in highlight:
            mod = "#"
        comment = f" // {clean_name(node.name)}" if clean_name(node.name) else ""
        head = f"{indent}{mod}{node.call()}"
        if not node.is_container:
            out.append(head + ";" + comment)
        elif not node.children:
            out.append(head + " {}" + comment)
        else:
            out.append(head + " {" + comment)
            for child in node.children:
                emit(child, indent + "  ")
            out.append(indent + "}")
        spans[node.id] = (start, len(out) - 1)

    for n in doc.children:
        emit(n, "")
    return Generated("\n".join(out) + "\n", spans)
