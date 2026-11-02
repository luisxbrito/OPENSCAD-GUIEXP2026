"""Ayudas del editor de código sin dependencias de Qt.

* Plantillas de operaciones booleanas y fragmentos de código para el menú «Insertar».
* Ayuda de parámetros (firma de la función bajo el cursor), como en los IDE.
"""

from __future__ import annotations

import re
from typing import Optional

from .catalog import SPECS, openscad_modules
from .i18n import tr


BOOLEAN_TEMPLATES = {
    "difference": (
        "difference() {\n"
        "    // SÓLIDO BASE (al que se le resta):\n"
        "    \n"
        "    // SÓLIDO(S) A RESTAR (cortes / huecos):\n"
        "    \n"
        "}"
    ),
    "union": (
        "union() {\n"
        "    // Sólidos a unir (fusión continua):\n"
        "    \n"
        "}"
    ),
    "intersection": (
        "intersection() {\n"
        "    // Sólidos a intersecar (volumen común):\n"
        "    \n"
        "}"
    ),
}

SNIPPETS_CATALOG = [
    ("Cubo (cube)", "cube([20, 20, 10], center = true); // Cubo"),
    ("Cilindro (cylinder)", "cylinder(h = 20, r = 5, center = true, $fn = 64); // Cilindro"),
    ("Esfera (sphere)", "sphere(r = 10, $fn = 64); // Esfera"),
    ("Restar (difference)", "difference() {\n    cube([30, 30, 10], center = true); // Base\n    cylinder(h = 12, r = 5, center = true); // Agujero\n}"),
    ("Unir (union)", "union() {\n    cube([20, 20, 10], center = true);\n    cylinder(h = 25, r = 3, center = true);\n}"),
    ("Mover (translate)", "translate([10, 0, 0]) {\n    \n}"),
    ("Rotar (rotate)", "rotate([0, 0, 45]) {\n    \n}"),
    ("Extruir 2D (linear_extrude)", "linear_extrude(height = 10, center = true) {\n    circle(r = 8, $fn = 32);\n}"),
    ("Módulo de usuario", "module mi_pieza(ancho = 20, alto = 10) {\n    cube([ancho, ancho, alto], center = true);\n}"),
    ("Bucle for", "for (i = [0:3]) {\n    translate([i * 15, 0, 0]) cylinder(h = 10, r = 3);\n}"),
]


# Nombres de ejemplo de los fragmentos: se traducen como los comentarios, pero tienen que seguir
# siendo identificadores válidos de OpenSCAD (sin acentos ni espacios).
SNIPPET_NAMES = ("mi_pieza", "ancho", "alto")
_SNIPPET_NAME = re.compile(r"\b(" + "|".join(SNIPPET_NAMES) + r")\b")
_CODE_COMMENT = re.compile(r"(//[ \t]*)(.+)$", re.MULTILINE)


def localized_code(code: str, lang: Optional[str] = None) -> str:
    """Una plantilla o un fragmento con sus comentarios y nombres en el idioma de la interfaz."""
    code = _SNIPPET_NAME.sub(lambda m: tr(m.group(1), lang), code)
    return _CODE_COMMENT.sub(lambda m: m.group(1) + tr(m.group(2), lang), code)


def code_texts() -> set:
    """Los textos de las plantillas y fragmentos que necesitan traducción."""
    codes = [*BOOLEAN_TEMPLATES.values(), *(code for _label, code in SNIPPETS_CATALOG)]
    return {m.group(2) for code in codes for m in _CODE_COMMENT.finditer(code)} | set(SNIPPET_NAMES)


# --------------------------------------------------------------------------- Catálogo de funciones matemáticas y utilidades
OPENSCAD_BUILTINS: dict[str, dict] = {
    # Matemáticas y trigonometría básica
    "sin": {"params": [("a", "num", "Ángulo en grados")], "doc": "Seno trigonométrico del ángulo 'a' (en grados).", "ret": "num"},
    "cos": {"params": [("a", "num", "Ángulo en grados")], "doc": "Coseno trigonométrico del ángulo 'a' (en grados).", "ret": "num"},
    "tan": {"params": [("a", "num", "Ángulo en grados")], "doc": "Tangente trigonométrica del ángulo 'a' (en grados).", "ret": "num"},
    "asin": {"params": [("x", "num", "Valor en el rango [-1, 1]")], "doc": "Arco seno: devuelve ángulo en grados [-90, 90].", "ret": "num"},
    "acos": {"params": [("x", "num", "Valor en el rango [-1, 1]")], "doc": "Arco coseno: devuelve ángulo en grados [0, 180].", "ret": "num"},
    "atan": {"params": [("x", "num", "Valor de la tangente")], "doc": "Arco tangente: devuelve ángulo en grados [-90, 90].", "ret": "num"},
    "atan2": {"params": [("y", "num", "Coordenada Y"), ("x", "num", "Coordenada X")], "doc": "Arco tangente de dos variables y/x en grados [-180, 180].", "ret": "num"},
    "sqrt": {"params": [("v", "num", "Valor no negativo")], "doc": "Calcula la raíz cuadrada de 'v'.", "ret": "num"},
    "pow": {"params": [("base", "num", "Base numérica"), ("exp", "num", "Exponente")], "doc": "Calcula la potencia: base elevado a exp.", "ret": "num"},
    "exp": {"params": [("x", "num", "Exponente")], "doc": "Función exponencial: e elevado a x.", "ret": "num"},
    "ln": {"params": [("x", "num", "Valor positivo")], "doc": "Logaritmo natural (en base e).", "ret": "num"},
    "log": {"params": [("x", "num", "Valor positivo")], "doc": "Logaritmo en base 10.", "ret": "num"},
    "abs": {"params": [("x", "num/vec", "Valor numérico o vector")], "doc": "Valor absoluto (|x|).", "ret": "num"},
    "sign": {"params": [("x", "num", "Valor numérico")], "doc": "Signo de x: retorna -1 si x < 0, 0 si x == 0, y 1 si x > 0.", "ret": "int"},
    "round": {"params": [("x", "num", "Valor numérico")], "doc": "Redondea 'x' al entero más cercano.", "ret": "int"},
    "floor": {"params": [("x", "num", "Valor numérico")], "doc": "Redondeo hacia abajo (mayor entero menor o igual a x).", "ret": "int"},
    "ceil": {"params": [("x", "num", "Valor numérico")], "doc": "Redondeo hacia arriba (menor entero mayor o igual a x).", "ret": "int"},
    "min": {"params": [("a", "num/vec", "Primer valor o vector"), ("b...", "num", "Valores adicionales opcionales")], "doc": "Valor mínimo entre los argumentos o vector.", "ret": "num"},
    "max": {"params": [("a", "num/vec", "Primer valor o vector"), ("b...", "num", "Valores adicionales opcionales")], "doc": "Valor máximo entre los argumentos o vector.", "ret": "num"},

    # Vectores, matrices y listas
    "norm": {"params": [("v", "vec2/vec3", "Vector [x, y] o [x, y, z]")], "doc": "Norma euclidiana (longitud o módulo) del vector.", "ret": "num"},
    "cross": {"params": [("u", "vec3", "Primer vector 3D"), ("v", "vec3", "Segundo vector 3D")], "doc": "Producto vectorial tridimensional u × v.", "ret": "vec3"},
    "concat": {"params": [("v1", "list", "Primera lista o elemento"), ("v2...", "list", "Listas o elementos adicionales")], "doc": "Concatena múltiples listas o vectores.", "ret": "list"},
    "len": {"params": [("v", "list/str", "Lista, vector o cadena de texto")], "doc": "Cantidad de elementos en una lista o longitud de cadena.", "ret": "int"},
    "str": {"params": [("a...", "any", "Valores o expresiones a convertir")], "doc": "Convierte y concatena argumentos como cadena de texto.", "ret": "str"},
    "chr": {"params": [("code", "int", "Código ASCII / Unicode")], "doc": "Carácter correspondiente al código numérico.", "ret": "str"},
    "ord": {"params": [("char", "str", "Carácter individual")], "doc": "Código numérico ASCII / Unicode del carácter.", "ret": "int"},
    "lookup": {"params": [("x", "num", "Valor a interpolar"), ("table", "list", "Tabla de pares [[x0, y0], ...]")], "doc": "Búsqueda e interpolación en tabla.", "ret": "num"},

    # Utilidades
    "echo": {"params": [("msg...", "any", "Valores a imprimir")], "doc": "Imprime valores en la consola durante la evaluación.", "ret": "void"},
    "assert": {"params": [("condition", "bool", "Condición booleana"), ("message", "str", "Mensaje si falla")], "doc": "Aserción que detiene la compilación si es falsa.", "ret": "void"},
}


def find_active_call(text: str, pos: int) -> Optional[tuple[str, int, Optional[str]]]:
    """Detecta la llamada de función/módulo activa y el parámetro donde está el cursor."""
    if pos <= 0 or pos > len(text):
        return None

    # Paso 1: Retroceder para encontrar el '(' del nivel actual
    paren_depth = 0
    in_str = False
    open_paren_pos = -1

    i = pos - 1
    while i >= 0:
        c = text[i]
        if c == '"' and (i == 0 or text[i - 1] != '\\'):
            in_str = not in_str
        elif not in_str:
            if c == ')':
                paren_depth += 1
            elif c == '(':
                if paren_depth > 0:
                    paren_depth -= 1
                else:
                    open_paren_pos = i
                    break
            elif c in ('{', '}'):
                if paren_depth == 0:
                    return None
        i -= 1

    if open_paren_pos == -1:
        return None

    # Obtener el nombre del identificador antes de '('
    j = open_paren_pos - 1
    while j >= 0 and text[j].isspace():
        j -= 1
    name_end = j + 1
    while j >= 0 and (text[j].isalnum() or text[j] in ('_', '$')):
        j -= 1
    func_name = text[j + 1:name_end]
    if not func_name:
        return None

    # Paso 2: Avanzar desde open_paren_pos + 1 hasta pos para contar comas reales
    param_index = 0
    bracket_depth = 0
    brace_depth = 0
    sub_paren_depth = 0
    in_quotes = False
    arg_start = open_paren_pos + 1

    k = open_paren_pos + 1
    while k < pos:
        c = text[k]
        if c == '"' and (k == 0 or text[k - 1] != '\\'):
            in_quotes = not in_quotes
        elif not in_quotes:
            if c == '(':
                sub_paren_depth += 1
            elif c == ')':
                if sub_paren_depth > 0:
                    sub_paren_depth -= 1
            elif c == '[':
                bracket_depth += 1
            elif c == ']':
                if bracket_depth > 0:
                    bracket_depth -= 1
            elif c == '{':
                brace_depth += 1
            elif c == '}':
                if brace_depth > 0:
                    brace_depth -= 1
            elif c == ',' and sub_paren_depth == 0 and bracket_depth == 0 and brace_depth == 0:
                param_index += 1
                arg_start = k + 1
        k += 1

    # Analizar si el argumento actual es explícito por nombre: `nombre = valor`
    # Buscar el final del argumento (siguiente coma o cierre de llamada)
    arg_end = pos
    f_sub_paren = sub_paren_depth
    f_bracket = bracket_depth
    f_brace = brace_depth
    f_quotes = in_quotes

    while arg_end < len(text):
        c = text[arg_end]
        if c == '"' and (arg_end == 0 or text[arg_end - 1] != '\\'):
            f_quotes = not f_quotes
        elif not f_quotes:
            if c == '(':
                f_sub_paren += 1
            elif c == ')':
                if f_sub_paren > 0:
                    f_sub_paren -= 1
                else:
                    break
            elif c == '[':
                f_bracket += 1
            elif c == ']':
                if f_bracket > 0:
                    f_bracket -= 1
            elif c == '{':
                f_brace += 1
            elif c == '}':
                if f_brace > 0:
                    f_brace -= 1
            elif c == ',' and f_sub_paren == 0 and f_bracket == 0 and f_brace == 0:
                break
            elif c in (';', '\n'):
                break
        arg_end += 1

    current_arg_snippet = text[arg_start:arg_end].strip()
    active_named_param = None
    if "=" in current_arg_snippet:
        candidate = current_arg_snippet.split("=")[0].strip()
        if candidate.isidentifier() or candidate.startswith("$"):
            active_named_param = candidate

    return func_name, param_index, active_named_param


def get_signature_info(func_name: str, param_index: int, named_param: Optional[str], doc_text: str = "") -> Optional[dict]:
    """Obtiene los metadatos y el parámetro activo para una función o módulo."""
    if not func_name:
        return None

    # 1. Comprobar catálogo oficial de OpenSCAD (SPECS)
    if func_name in openscad_modules():
        spec = SPECS[func_name]
        params_info = []
        active_idx = 0

        if named_param:
            for idx, p in enumerate(spec.params):
                if p.name == named_param:
                    active_idx = idx
                    break
        else:
            if spec.positional and param_index < len(spec.positional):
                pos_name = spec.positional[param_index]
                for idx, p in enumerate(spec.params):
                    if p.name == pos_name:
                        active_idx = idx
                        break
            elif param_index < len(spec.params):
                active_idx = param_index
            else:
                active_idx = len(spec.params) - 1 if spec.params else 0

        for i, p in enumerate(spec.params):
            default_str = f" = {p.default}" if p.default is not None and p.optional else ""
            params_info.append({
                "name": p.name,
                "kind": p.kind,
                "default": default_str,
                "label": tr(p.label) if p.label else p.name,
                "optional": p.optional,
                "is_active": (i == active_idx),
            })

        active_p = params_info[active_idx] if params_info else None
        return {
            "name": func_name,
            "category": f"{tr('Módulo OpenSCAD')} ({tr(spec.label)})",
            "params": params_info,
            "active_idx": active_idx,
            "active_param": active_p,
            "doc": tr(spec.hint or spec.label),
        }

    # 2. Comprobar funciones matemáticas y utilitarias de OpenSCAD
    if func_name in OPENSCAD_BUILTINS:
        b_info = OPENSCAD_BUILTINS[func_name]
        raw_params = b_info["params"]
        active_idx = min(param_index, len(raw_params) - 1) if raw_params else 0
        if named_param:
            for idx, (p_name, _, _) in enumerate(raw_params):
                if p_name.rstrip(".").split("=")[0] == named_param:
                    active_idx = idx
                    break

        params_info = []
        for i, (p_name, p_kind, p_doc) in enumerate(raw_params):
            params_info.append({
                "name": p_name,
                "kind": p_kind,
                "default": "",
                "label": tr(p_doc),
                "optional": "..." in p_name,
                "is_active": (i == active_idx),
            })

        active_p = params_info[active_idx] if params_info else None
        return {
            "name": func_name,
            "category": tr("Función matemática / utilitaria"),
            "params": params_info,
            "active_idx": active_idx,
            "active_param": active_p,
            "doc": tr(b_info["doc"]),
        }

    # 3. Comprobar módulos definidos por el usuario en el documento
    if doc_text:
        pattern = rf"\bmodule\s+{re.escape(func_name)}\s*\(([^)]*)\)"
        m = re.search(pattern, doc_text)
        if m:
            raw_args = [a.strip() for a in m.group(1).split(",") if a.strip()]
            active_idx = min(param_index, len(raw_args) - 1) if raw_args else 0
            if named_param:
                for idx, a in enumerate(raw_args):
                    if a.split("=")[0].strip() == named_param:
                        active_idx = idx
                        break

            params_info = []
            for i, a in enumerate(raw_args):
                if "=" in a:
                    p_name, p_def = a.split("=", 1)
                    p_name = p_name.strip()
                    default_str = f" = {p_def.strip()}"
                    is_opt = True
                else:
                    p_name = a.strip()
                    default_str = ""
                    is_opt = False
                params_info.append({
                    "name": p_name,
                    "kind": "any",
                    "default": default_str,
                    "label": f"{tr('Parámetro')} '{p_name}'",
                    "optional": is_opt,
                    "is_active": (i == active_idx),
                })

            active_p = params_info[active_idx] if params_info else None
            return {
                "name": func_name,
                "category": tr("Módulo personalizado (Usuario)"),
                "params": params_info,
                "active_idx": active_idx,
                "active_param": active_p,
                "doc": f"{tr('Módulo de usuario definido en este script')}: {func_name}(...)",
            }

    return None


def format_signature_html(sig: dict) -> tuple[str, str]:
    """Genera el HTML resaltado para la firma completa y el detalle del parámetro activo."""
    parts = []
    for p in sig["params"]:
        p_text = f"{p['name']}: {p['kind']}{p['default']}"
        if p["is_active"]:
            parts.append(
                f'<span style="color: #1D4ED8; background-color: #DBEAFE; font-weight: bold; '
                f'border-radius: 3px; padding: 1px 4px;">{p_text}</span>'
            )
        else:
            parts.append(f'<span style="color: #64748B;">{p_text}</span>')

    sig_html = f"<b>{sig['name']}</b>( " + ", ".join(parts) + " )"

    act = sig.get("active_param")
    if act:
        req_str = tr("Opcional") if act["optional"] else tr("Obligatorio")
        detail_html = (
            f"▸ <b style='color: #1E40AF;'>{act['name']}</b>: {tr(act['label'])} "
            f"<span style='color: #64748B;'>({act['kind']}, {req_str})</span>"
        )
    else:
        detail_html = f"<span style='color: #64748B;'>{tr(sig['doc'])}</span>"

    return sig_html, detail_html
