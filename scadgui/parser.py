"""Lector de archivos .scad → modelo de objetos.

Es un parser tolerante: reconoce las llamadas a los módulos del catálogo
(cube, translate, difference...) con argumentos literales y las convierte
en ``Node``, y también los bucles for con la forma exacta que escriben las
matrices. Todo lo demás (variables, otros for, if, módulos propios, include...)
se guarda tal cual en un ``RawCode``, de modo que abrir y volver a guardar
un archivo nunca pierde código.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any, Optional

from .catalog import SPECS
from .model import HEADER, MODIFIERS, Document, Expr, Node, RawCode


class ParseError(Exception):
    def __init__(self, message: str, line: int = 0):
        super().__init__(f"Línea {line}: {message}" if line else message)
        self.line = line


@dataclass
class Tok:
    type: str  # id, num, str, op, comment
    text: str
    start: int
    end: int
    line: int        # base 1
    end_line: int
    trailing: bool = False  # comentario con código antes en la misma línea


_TOKEN_RE = re.compile(r"""
    (?P<ws>\s+)
  | (?P<lcomment>//[^\n]*)
  | (?P<bcomment>/\*.*?\*/)
  | (?P<str>"(?:[^"\\\n]|\\.)*")
  | (?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<id>\$?[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>==|!=|<=|>=|&&|\|\||[^\s])
""", re.VERBOSE | re.DOTALL)


def tokenize(src: str) -> list[Tok]:
    toks: list[Tok] = []
    pos = 0
    line = 1
    last_code_line = 0
    while pos < len(src):
        if src.startswith("/*", pos) and src.find("*/", pos + 2) < 0:
            raise ParseError("Comentario /* sin cerrar", line)
        if src[pos] == '"' and not re.match(r'"(?:[^"\\\n]|\\.)*"', src[pos:]):
            raise ParseError("Texto entre comillas sin cerrar", line)
        m = _TOKEN_RE.match(src, pos)
        kind = m.lastgroup
        text = m.group(0)
        nl = text.count("\n")
        if kind != "ws":
            if kind in ("lcomment", "bcomment"):
                toks.append(Tok("comment", text, pos, m.end(), line, line + nl,
                                trailing=(last_code_line == line)))
            else:
                toks.append(Tok(kind, text, pos, m.end(), line, line + nl))
                last_code_line = line + nl
        line += nl
        pos = m.end()
    return toks


_NUMERIC_LITERAL = re.compile(r"[\s\d.eE+\-\[\],]*")
_STRING_LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"', re.DOTALL)
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"'}


def _only_numbers(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, list):
        return all(_only_numbers(x) for x in v)
    return False


def literal(text: str) -> Any:
    """Convierte el texto de un argumento en valor Python si es un literal simple."""
    t = text.strip()
    if t == "true":
        return True
    if t == "false":
        return False
    if _STRING_LITERAL.fullmatch(t):
        return re.sub(r"\\(.)", lambda m: _ESCAPES.get(m.group(1), m.group(1)), t[1:-1])
    if t and _NUMERIC_LITERAL.fullmatch(t):
        try:
            value = ast.literal_eval(t)
        except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
            return Expr(t)
        if isinstance(value, tuple):
            value = list(value)
        if _only_numbers(value):
            return value
    return Expr(t)


# Un valor dentro de la cabecera de una matriz: vector sin anidar, expresión entre
# paréntesis (un nivel de paréntesis dentro), identificador o número.
_VAL = r"(?:\[[^\[\]]*\]|\((?:[^()]|\([^()]*\))*\)|[A-Za-z_$][\w$]*|-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"


def _end(name: str) -> str:
    return rf"\[\s*0\s*:\s*(?:(?P<{name}>\d+)|(?P<{name}_expr>{_VAL})\s*-\s*1)\s*\]"


_ARRAY_HEADS = {
    "linear_array": re.compile(
        rf"for\s*\(\s*i\s*=\s*{_end('n')}\s*\)\s*translate\s*\(\s*i\s*\*\s*(?P<step>{_VAL})\s*\)"),
    "polar_array": re.compile(
        rf"for\s*\(\s*i\s*=\s*{_end('n')}\s*\)\s*rotate\s*\(\s*a\s*=\s*i\s*\*\s*(?P<angle>{_VAL})"
        rf"\s*,\s*v\s*=\s*(?P<axis>{_VAL})\s*\)"),
    "grid_array": re.compile(
        rf"for\s*\(\s*i\s*=\s*{_end('nx')}\s*,\s*j\s*=\s*{_end('ny')}\s*\)\s*translate\s*\(\s*"
        rf"i\s*\*\s*(?P<step_x>{_VAL})\s*\+\s*j\s*\*\s*(?P<step_y>{_VAL})\s*\)"),
}


def _factor(text: str):
    """Inverso de model.as_factor: quita los paréntesis que se pusieron al escribir."""
    t = text.strip()
    if t.startswith("(") and t.endswith(")"):
        depth = 0
        for k, ch in enumerate(t):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and k < len(t) - 1:
                break  # (a) + (b): los paréntesis no envuelven todo
        else:
            t = t[1:-1]
    return literal(t)


def _array_params(m: re.Match) -> dict:
    """Parámetros de la matriz; un último índice literal k es k + 1 copias."""
    params = {}
    for key, value in m.groupdict().items():
        if value is None:
            continue
        if key.endswith("_expr"):
            params[key[:-5]] = _factor(value)
        elif key in ("n", "nx", "ny"):
            params[key] = int(value) + 1
        else:
            params[key] = _factor(value)
    return params


class _Parser:
    def __init__(self, src: str):
        self.src = src
        all_toks = tokenize(src)
        self.toks = [t for t in all_toks if t.type != "comment"]
        self.comments = [t for t in all_toks if t.type == "comment"]
        self.trailing = {c.line: c for c in self.comments if c.trailing and c.type == "comment"
                         and c.text.startswith("//")}
        self.standalone = [c for c in self.comments if not c.trailing]
        self.used_comments: set[int] = set()
        self.i = 0
        self.ci = 0  # siguiente comentario independiente
        self.doc = Document()

    # ----- utilidades
    def peek(self, k: int = 0) -> Optional[Tok]:
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None

    def text(self, k: int = 0) -> Optional[str]:
        t = self.peek(k)
        return t.text if t else None

    def next_line_after(self, idx: int) -> int:
        return self.toks[idx + 1].line if idx + 1 < len(self.toks) else 10 ** 9

    def name_comment(self, tok_index: int) -> str:
        """Comentario // al final de la línea del token, si no hay más código detrás."""
        tok = self.toks[tok_index]
        c = self.trailing.get(tok.end_line)
        if c is None or self.next_line_after(tok_index) == tok.end_line:
            return ""
        self.used_comments.add(c.start)
        return c.text[2:].strip()

    def flush_comments(self, before: int, out: list) -> None:
        while self.ci < len(self.standalone) and self.standalone[self.ci].start < before:
            c = self.standalone[self.ci]
            self.ci += 1
            if c.text.strip() == HEADER:
                continue
            out.append(RawCode(self._dedent(c.text, c.start), is_comment=True))

    def _dedent(self, text: str, start: int) -> str:
        line_start = self.src.rfind("\n", 0, start) + 1
        prefix = re.match(r"[ \t]*", self.src[line_start:start]).group(0)
        lines = text.split("\n")
        fixed = [lines[0]] + [ln[len(prefix):] if ln.startswith(prefix) else ln.lstrip() for ln in lines[1:]]
        return "\n".join(fixed).rstrip()

    # ----- gramática
    def parse(self) -> Document:
        self.doc.children = self.block(top=True)
        return self.doc

    def block(self, top: bool, open_line: int = 0) -> list:
        items: list = []
        while True:
            tok = self.peek()
            self.flush_comments(tok.start if tok else len(self.src) + 1, items)
            if tok is None:
                if not top:
                    raise ParseError("Falta cerrar un bloque con '}'", open_line)
                return items
            if tok.text == "}" and not top:
                self.i += 1
                return items
            if tok.text == ";":
                self.i += 1
                continue
            node = self.statement(top)
            if node is not None:
                items.append(node)

    def statement(self, top: bool):
        start = self.i
        # $fn = 64; en el nivel superior se convierte en el ajuste global
        if top and self.text() == "$fn" and self.text(1) == "=" and self.peek(2) and \
                self.peek(2).type == "num" and self.text(3) == ";":
            self.doc.fn = int(float(self.text(2)))
            self.i += 4
            return None
        node = self.try_node()
        if node is not None:
            return node
        self.i = start
        return self.raw()

    def try_node(self) -> Optional[Node]:
        mod = ""
        while self.text() in MODIFIERS and self.peek(1) is not None:
            mod += self.text()
            self.i += 1
        if len(mod) > 1:
            return None
        tok = self.peek()
        if tok is not None and tok.text == "for":
            found = self.array_head()
            if found is None:
                return None
            spec = SPECS[found[0]]
            params = found[1]
        else:
            if tok is None or tok.type != "id" or tok.text not in SPECS or SPECS[tok.text].keyword \
                    or self.text(1) != "(":
                return None
            spec = SPECS[tok.text]
            self.i += 2
            params = self.arguments(spec)
            if params is None:
                return None
        node = Node(kind=spec.name, params=params, modifier=mod)
        nxt = self.text()
        if spec.container:
            if nxt == "{":
                brace = self.i
                self.i += 1
                node.name = self.name_comment(brace)
                node.children = self.block(top=False, open_line=self.toks[brace].line)
            elif nxt == ";":
                node.name = self.name_comment(self.i)
                self.i += 1
            elif nxt is None:
                return None
            else:
                child = self.statement(top=False)
                if child is None:
                    return None
                node.children = [child]
        else:
            if nxt != ";":
                return None
            node.name = self.name_comment(self.i)
            self.i += 1
        return node

    def array_head(self) -> Optional[tuple[str, dict]]:
        """Cabecera ``for (...) translate(...)`` de una matriz; None si es otro for."""
        start = self.peek().start
        for kind, pattern in _ARRAY_HEADS.items():
            m = pattern.match(self.src, start)
            if m is None:
                continue
            while self.peek() is not None and self.peek().start < m.end():
                self.i += 1
            return kind, _array_params(m)
        return None

    def arguments(self, spec) -> Optional[dict]:
        """Lee hasta el ')' correspondiente. Devuelve None si no encaja con el módulo."""
        args: list[list[Tok]] = [[]]
        depth = 0
        while True:
            tok = self.peek()
            if tok is None:
                return None
            self.i += 1
            if tok.text in "([{" and tok.type == "op":
                depth += 1
            elif tok.text in ")]}" and tok.type == "op":
                if depth == 0:
                    if tok.text != ")":
                        return None
                    break
                depth -= 1
            if depth == 0 and tok.text == "," and tok.type == "op":
                args.append([])
                continue
            args[-1].append(tok)
        if args == [[]]:
            return {}
        params: dict = {}
        positional_index = 0
        for arg in args:
            if not arg:
                return None
            if len(arg) >= 3 and arg[0].type == "id" and arg[1].text == "=":
                key = arg[0].text
                value_toks = arg[2:]
            else:
                if positional_index >= len(spec.positional):
                    return None
                key = spec.positional[positional_index]
                positional_index += 1
                value_toks = arg
            if key in params:
                return None
            params[key] = literal(self.src[value_toks[0].start:value_toks[-1].end])
        return params

    def raw(self) -> RawCode:
        """Guarda una sentencia completa como texto literal."""
        start = self.i
        first = self.peek()
        if first.text in ("include", "use"):
            # include <archivo.scad> no lleva punto y coma: llega hasta el final de la línea
            while self.peek() is not None and self.peek().line == first.line:
                self.i += 1
        else:
            depth = 0
            while self.peek() is not None:
                tok = self.peek()
                if tok.type == "op" and tok.text in "([{":
                    depth += 1
                elif tok.type == "op" and tok.text in ")]}":
                    if depth == 0:
                        break
                    depth -= 1
                    if tok.text == "}" and depth == 0:
                        self.i += 1
                        if self.text() == "else":
                            continue
                        break
                elif tok.text == ";" and depth == 0:
                    self.i += 1
                    if self.text() == "else":
                        continue
                    break
                self.i += 1
            if self.i == start:  # símbolo suelto, p. ej. una '}' de más
                self.i += 1
        last = self.toks[self.i - 1]
        end = last.end
        c = self.trailing.get(last.end_line)
        if c is not None and c.start >= end and self.next_line_after(self.i - 1) != last.end_line:
            end = c.end
            self.used_comments.add(c.start)
        # los comentarios que quedaron dentro del bloque ya van en el texto literal
        while self.ci < len(self.standalone) and self.standalone[self.ci].start < end:
            self.ci += 1
        return RawCode(self._dedent(self.src[first.start:end], first.start))


def parse(src: str) -> Document:
    return _Parser(src).parse()
