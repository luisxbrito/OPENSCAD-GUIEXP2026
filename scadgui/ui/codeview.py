"""Panel de código accesible y ergonómico para OpenSCAD.

Incluye:
1. Accesibilidad visual:
   - Margen lateral con números de línea (LineNumberArea).
   - Resaltado de la línea activa (Current Line Highlight).
   - Zoom accesible con teclado y ratón (Ctrl + Plus/Minus/0/Rueda).
   - Resaltado de parejas de llaves, corchetes y paréntesis (Bracket Matching).
2. Ergonomía y asistencia de edición:
   - Auto-cierre de llaves, corchetes, paréntesis y comillas ({}, (), [], "").
   - Auto-indentación inteligente al pulsar Enter.
   - Tabulación y des-tabulación de bloques con Tab y Shift+Tab.
   - Comentar / descomentar rápido con Ctrl+/ o Ctrl+7.
   - Detección en tiempo real de llaves/paréntesis desbalanceados.
3. Navegación y búsqueda:
   - Barra de búsqueda rápida integrada (Ctrl+F) con contador y navegación.
   - Menú de inserción rápida de bloques y snippets habituales.
4. Sincronización sin fricción:
   - Activación automática del modo edición al teclear o con F2 / doble clic.
   - Ayuda contextual para operaciones booleanas y autocompletado del proyecto.
"""

from __future__ import annotations

import re
from typing import Optional

from PySide6.QtCore import QPoint, QRect, QSize, QStringListModel, Qt, Signal
from PySide6.QtGui import (QAction, QColor, QFont, QKeySequence, QPainter, QPen,
                           QShortcut, QSyntaxHighlighter, QTextCharFormat,
                           QTextCursor, QTextDocument, QTextFormat)
from PySide6.QtWidgets import (QAbstractItemView, QCompleter, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QMenu, QPlainTextEdit,
                               QPushButton, QTextEdit, QToolButton, QVBoxLayout,
                               QWidget)

from ..catalog import CONTROL_KEYWORDS, SPECS
from ..i18n import tr


def mono_font(size: int = 10) -> QFont:
    f = QFont()
    f.setFamilies(["IBM Plex Mono", "Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono", "monospace"])
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setPointSize(size)
    return f


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


class ScadHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)

        def fmt(color, bold=False, italic=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.DemiBold)
            f.setFontItalic(italic)
            return f

        modules = "|".join(sorted(SPECS, key=len, reverse=True))
        control = "|".join(CONTROL_KEYWORDS + ("else", "true", "false", "undef"))
        self.rules = [
            (re.compile(r"\$\w+"), fmt("#7A3E9D")),
            (re.compile(rf"\b(?:{modules})\b"), fmt("#1F5FBF", bold=True)),
            (re.compile(rf"\b(?:{control})\b"), fmt("#7A3E9D", bold=True)),
            (re.compile(r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b"), fmt("#9A5B00")),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), fmt("#1E6B34")),
            (re.compile(r"^\s*[#%!*]"), fmt("#C2410C", bold=True)),
        ]
        self.comment = fmt("#5F7A54", italic=True)

    def highlightBlock(self, text):
        for rx, f in self.rules:
            for m in rx.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), f)
        self.setCurrentBlockState(0)
        inside = self.previousBlockState() == 1
        start = 0 if inside else text.find("/*")
        while start >= 0:
            end = text.find("*/", start if inside else start + 2)
            inside = False
            if end < 0:
                self.setCurrentBlockState(1)
                self.setFormat(start, len(text) - start, self.comment)
                return
            self.setFormat(start, end + 2 - start, self.comment)
            start = text.find("/*", end + 2)
        m = re.search(r"//.*$", text)
        if m and text[:m.start()].count('"') % 2 == 0:
            self.setFormat(m.start(), m.end() - m.start(), self.comment)


class LineNumberArea(QWidget):
    """Margen lateral que dibuja los números de línea."""

    def __init__(self, editor: "ScadEditor"):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self) -> QSize:
        if hasattr(self.code_editor, "line_number_area_width"):
            return QSize(self.code_editor.line_number_area_width(), 0)
        return QSize(36, 0)

    def paintEvent(self, event) -> None:
        if hasattr(self.code_editor, "line_number_area_paint_event"):
            self.code_editor.line_number_area_paint_event(event)


class FindBar(QFrame):
    """Barra de búsqueda integrada (Ctrl+F) con contador de coincidencias y navegación."""
    findNext = Signal(str)
    findPrev = Signal(str)
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("findBar")
        self.setStyleSheet(
            "QFrame#findBar { background-color: #F8FAFC; border-bottom: 1px solid #CBD5E1; "
            "padding: 4px 8px; }"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(6)

        self.lbl = QLabel(f"🔍 {tr('Buscar')}:")
        self.lbl.setStyleSheet("font-size: 11px; font-weight: 500; color: #475569;")
        lay.addWidget(self.lbl)

        self.input = QLineEdit()
        self.input.setPlaceholderText(tr("Texto a buscar… (Enter para siguiente)"))
        self.input.setStyleSheet(
            "QLineEdit { background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 4px; "
            "padding: 3px 6px; font-size: 11px; } QLineEdit:focus { border-color: #3B82F6; }"
        )
        self.input.returnPressed.connect(lambda: self.findNext.emit(self.input.text()))
        lay.addWidget(self.input, 1)

        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("font-size: 10px; color: #64748B; min-width: 65px;")
        lay.addWidget(self.lbl_count)

        self.btn_prev = QToolButton()
        self.btn_prev.setText("▲")
        self.btn_prev.setToolTip(tr("Coincidencia anterior (Shift+F3)"))
        self.btn_prev.clicked.connect(lambda: self.findPrev.emit(self.input.text()))
        lay.addWidget(self.btn_prev)

        self.btn_next = QToolButton()
        self.btn_next.setText("▼")
        self.btn_next.setToolTip(tr("Siguiente coincidencia (F3 o Enter)"))
        self.btn_next.clicked.connect(lambda: self.findNext.emit(self.input.text()))
        lay.addWidget(self.btn_next)

        self.btn_close = QToolButton()
        self.btn_close.setText("✕")
        self.btn_close.setToolTip(tr("Cerrar búsqueda (Escape)"))
        self.btn_close.clicked.connect(self.closed.emit)
        lay.addWidget(self.btn_close)

    def set_count(self, current: int, total: int) -> None:
        if total == 0:
            self.lbl_count.setText(tr("Sin resultados"))
            self.lbl_count.setStyleSheet("font-size: 10px; color: #DC2626; min-width: 65px;")
        else:
            self.lbl_count.setText(f"{current} {tr('de')} {total}")
            self.lbl_count.setStyleSheet("font-size: 10px; color: #166534; min-width: 65px;")

    def retranslate_ui(self) -> None:
        if hasattr(self, "lbl"):
            self.lbl.setText(f"🔍 {tr('Buscar')}:")
        if hasattr(self, "input"):
            self.input.setPlaceholderText(tr("Texto a buscar… (Enter para siguiente)"))
        if hasattr(self, "btn_prev"):
            self.btn_prev.setToolTip(tr("Coincidencia anterior (Shift+F3)"))
        if hasattr(self, "btn_next"):
            self.btn_next.setToolTip(tr("Siguiente coincidencia (F3 o Enter)"))
        if hasattr(self, "btn_close"):
            self.btn_close.setToolTip(tr("Cerrar búsqueda (Escape)"))



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
    if func_name in SPECS:
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



class SignatureHelpPopup(QFrame):
    """Tarjeta flotante que muestra la firma y ayuda de parámetros (parameter hints) cerca del cursor."""

    def __init__(self, editor: "ScadEditor"):
        super().__init__(editor, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.code_editor = editor
        self.setObjectName("signatureHelpPopup")
        if hasattr(self, "setAttribute"):
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        if hasattr(self, "setFocusPolicy"):
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setStyleSheet(
            "QFrame#signatureHelpPopup { "
            "  background-color: #FFFFFF; "
            "  border: 1px solid #3B82F6; "
            "  border-radius: 6px; "
            "  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15); "
            "}"
            "QLabel { color: #1E293B; font-size: 11px; }"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        self.lbl_category = QLabel()
        self.lbl_category.setStyleSheet("color: #64748B; font-size: 10px; font-weight: bold;")
        lay.addWidget(self.lbl_category)

        self.lbl_sig = QLabel()
        self.lbl_sig.setFont(mono_font(10))
        lay.addWidget(self.lbl_sig)

        self.lbl_detail = QLabel()
        self.lbl_detail.setStyleSheet("color: #0F172A; font-size: 11px;")
        lay.addWidget(self.lbl_detail)

        self.lbl_tip = QLabel(tr("Ctrl+Shift+Espacio: alternar · Esc: cerrar"))
        self.lbl_tip.setStyleSheet("color: #94A3B8; font-size: 9px; font-style: italic;")
        lay.addWidget(self.lbl_tip)

    def show_signature(self, sig_info: dict) -> None:
        try:
            sig_html, detail_html = format_signature_html(sig_info)
            self.lbl_category.setText(sig_info["category"])
            self.lbl_sig.setText(sig_html)
            self.lbl_detail.setText(detail_html)
            self.adjustSize()

            if not hasattr(self.code_editor, "cursorRect") or not hasattr(self.code_editor, "viewport"):
                self.show()
                return

            cr = self.code_editor.cursorRect()
            global_pt = self.code_editor.viewport().mapToGlobal(cr.topLeft())
            pop_w = self.sizeHint().width()
            pop_h = self.sizeHint().height()

            # Posicionar por defecto arriba del cursor para no tapar lo que se escribe
            x = max(10, global_pt.x() - 15)
            y = global_pt.y() - pop_h - 6
            if y < 20:  # Si no hay espacio arriba, ubicar debajo
                y = global_pt.y() + cr.height() + 6

            self.move(x, y)
            self.show()
        except Exception:
            pass

    def hide_signature(self) -> None:
        try:
            self.hide()
        except Exception:
            pass

    def retranslate_ui(self) -> None:
        if hasattr(self, "lbl_tip"):
            self.lbl_tip.setText(tr("Ctrl+Shift+Espacio: alternar · Esc: cerrar"))



class ScadEditor(QPlainTextEdit):
    """Editor de código con accesibilidad total: numeración de líneas, zoom, auto-cierre, búsqueda y parameter hints."""
    autoStartEditingRequested = Signal()
    balanceChanged = Signal(bool, str)
    signatureHelpChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._completer = None
        self._words: list[str] = []
        self._templates: dict[str, str] = dict(BOOLEAN_TEMPLATES)
        self._solid_words: list[str] = []
        self._span_selections: list[QTextEdit.ExtraSelection] = []
        self._bracket_selections: list[QTextEdit.ExtraSelection] = []
        self._search_selections: list[QTextEdit.ExtraSelection] = []

        # Margen de números de línea
        self.line_number_area = LineNumberArea(self)

        # Tarjeta flotante de ayuda de parámetros (Signature Help)
        self.sig_popup = SignatureHelpPopup(self)
        self._sig_popup_requested = False

        if hasattr(self, "blockCountChanged"):
            try:
                self.blockCountChanged.connect(self.update_line_number_area_width)
                self.updateRequest.connect(self.update_line_number_area)
            except Exception:
                pass

        self.cursorPositionChanged.connect(self._on_cursor_changed)
        self.textChanged.connect(self._on_text_changed)
        self.update_line_number_area_width(0)
        self._init_completer()

    def update_signature_help(self, force: bool = False) -> None:
        if not hasattr(self, "textCursor") or not hasattr(self, "toPlainText"):
            return
        try:
            pos = self.textCursor().position()
            text = self.toPlainText()
            call_ctx = find_active_call(text, pos)
            if call_ctx is None:
                self.sig_popup.hide_signature()
                self._sig_popup_requested = False
                self.signatureHelpChanged.emit(None)
                return

            func_name, param_index, named_param = call_ctx
            sig_info = get_signature_info(func_name, param_index, named_param, text)
            if sig_info is None:
                self.sig_popup.hide_signature()
                self._sig_popup_requested = False
                self.signatureHelpChanged.emit(None)
                return

            self.signatureHelpChanged.emit(sig_info)
            if force or self._sig_popup_requested:
                self.sig_popup.show_signature(sig_info)
        except Exception:
            pass

    def toggle_signature_help(self) -> None:
        if hasattr(self, "sig_popup") and self.sig_popup.isVisible():
            self.sig_popup.hide_signature()
            self._sig_popup_requested = False
        else:
            self._sig_popup_requested = True
            self.update_signature_help(force=True)


    def _init_completer(self) -> None:
        base = list(SPECS.keys()) + list(CONTROL_KEYWORDS) + list(OPENSCAD_BUILTINS.keys())
        bool_words = ["difference", "union", "intersection"]
        self._words = sorted(set(base + bool_words))

        self._completer = QCompleter(self._words, self)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.activated.connect(self._insert_completion)

    def set_solids_completions(self, solids: list[tuple[int, str, str]]) -> None:
        solid_items = []
        for _, label, kind in solids:
            clean = label.strip()
            if clean:
                solid_items.append(f"{kind}(); // {clean}")
                solid_items.append(clean)
        self._solid_words = solid_items
        all_words = sorted(set(self._words + self._solid_words))
        if hasattr(self._completer, "setModel"):
            model = QStringListModel(all_words, self._completer)
            self._completer.setModel(model)

    def _insert_completion(self, completion: str) -> None:
        tc = self.textCursor()
        clean_word = completion.split()[0].replace("();", "").replace("()", "")
        if clean_word in self._templates and ("//" not in completion):
            tc.select(QTextCursor.SelectionType.WordUnderCursor)
            template_code = self._templates[clean_word]
            tc.insertText(template_code)
            self.setTextCursor(tc)
            self.update_signature_help(force=False)
            return

        tc.select(QTextCursor.SelectionType.WordUnderCursor)
        tc.insertText(completion)
        self.setTextCursor(tc)
        self.update_signature_help(force=False)


    def _text_under_cursor(self) -> str:
        tc = self.textCursor()
        tc.select(QTextCursor.SelectionType.WordUnderCursor)
        return tc.selectedText()

    # ------------------------------------------------------------- Margen números de línea
    def line_number_area_width(self) -> int:
        if not hasattr(self, "blockCount"):
            return 36
        try:
            digits = max(1, len(str(max(1, self.blockCount()))))
            space = 14 + self.fontMetrics().horizontalAdvance("9") * digits
            return max(36, space)
        except Exception:
            return 36

    def update_line_number_area_width(self, _=0) -> None:
        if hasattr(self, "setViewportMargins"):
            try:
                self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
            except Exception:
                pass

    def update_line_number_area(self, rect, dy) -> None:
        if not hasattr(self, "line_number_area"):
            return
        try:
            if dy:
                self.line_number_area.scroll(0, dy)
            else:
                self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
            if rect.contains(self.viewport().rect()):
                self.update_line_number_area_width(0)
        except Exception:
            pass

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "line_number_area"):
            try:
                cr = self.contentsRect()
                self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))
            except Exception:
                pass

    def line_number_area_paint_event(self, event) -> None:
        if not hasattr(self, "firstVisibleBlock") or not hasattr(self, "viewport"):
            return
        try:
            painter = QPainter(self.line_number_area)
            painter.fillRect(event.rect(), QColor("#F8FAFC"))
            painter.setPen(QColor("#CBD5E1"))
            w = self.line_number_area.width()
            painter.drawLine(w - 1, event.rect().top(), w - 1, event.rect().bottom())

            block = self.firstVisibleBlock()
            block_number = block.blockNumber()
            top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
            bottom = top + int(self.blockBoundingRect(block).height())
            current_line = self.textCursor().blockNumber()
            painter.setFont(self.font())

            while block.isValid() and top <= event.rect().bottom():
                if block.isVisible() and bottom >= event.rect().top():
                    number = str(block_number + 1)
                    if block_number == current_line:
                        painter.setPen(QColor("#1E40AF"))
                        f = painter.font()
                        f.setBold(True)
                        painter.setFont(f)
                    else:
                        painter.setPen(QColor("#94A3B8"))
                        f = painter.font()
                        f.setBold(False)
                        painter.setFont(f)
                    painter.drawText(0, top, w - 8, self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, number)

                block = block.next()
                top = bottom
                bottom = top + int(self.blockBoundingRect(block).height())
                block_number += 1
        except Exception:
            pass

    # ------------------------------------------------------------- Resaltados (Línea activa, Brackets y Parameter Hints)
    def _on_cursor_changed(self) -> None:
        self.match_brackets()
        self.update_extra_selections()
        self.update_signature_help(force=False)

    def _on_text_changed(self) -> None:
        self.match_brackets()
        self.update_extra_selections()
        self._check_bracket_balance()
        self.update_signature_help(force=False)


    def update_extra_selections(self) -> None:
        if not hasattr(self, "setExtraSelections"):
            return
        selections = []

        # 1. Resaltado de la pieza seleccionada (span)
        if hasattr(self, "_span_selections"):
            selections.extend(self._span_selections)

        # 2. Resaltado de la línea actual
        if hasattr(self, "textCursor") and (not self.isReadOnly() or not self._span_selections):
            try:
                line_sel = QTextEdit.ExtraSelection()
                line_fmt = QTextCharFormat()
                line_fmt.setBackground(QColor("#F8FAFC") if self.isReadOnly() else QColor("#F1F5F9"))
                line_fmt.setProperty(QTextFormat.Property.FullWidthSelection, True)
                line_sel.format = line_fmt
                line_sel.cursor = self.textCursor()
                line_sel.cursor.clearSelection()
                selections.append(line_sel)
            except Exception:
                pass

        # 3. Resaltado de brackets
        if hasattr(self, "_bracket_selections"):
            selections.extend(self._bracket_selections)

        # 4. Resaltado de búsqueda
        if hasattr(self, "_search_selections"):
            selections.extend(self._search_selections)

        try:
            self.setExtraSelections(selections)
        except Exception:
            pass

    def match_brackets(self) -> None:
        self._bracket_selections = []
        if not hasattr(self, "document"):
            return
        try:
            tc = self.textCursor()
            doc = self.document()
            pos = tc.position()
            text = doc.toPlainText()
            if not text:
                return

            pairs = {
                "{": ("}", 1), "(": (")", 1), "[": ("]", 1),
                "}": ("{", -1), ")": ("(", -1), "]": ("[", -1),
            }

            check_pos = None
            char = None
            if pos < len(text) and text[pos] in pairs:
                check_pos = pos
                char = text[pos]
            elif pos > 0 and text[pos - 1] in pairs:
                check_pos = pos - 1
                char = text[pos - 1]

            if check_pos is None or char is None:
                return

            target_char, direction = pairs[char]
            depth = 0
            match_pos = -1

            i = check_pos
            while 0 <= i < len(text):
                c = text[i]
                if c == char:
                    depth += 1
                elif c == target_char:
                    depth -= 1
                    if depth == 0:
                        match_pos = i
                        break
                i += direction

            if match_pos != -1:
                fmt = QTextCharFormat()
                fmt.setBackground(QColor("#BAE6FD"))  # Celeste suave indicador
                fmt.setFontWeight(QFont.Weight.Bold)

                for p in (check_pos, match_pos):
                    sel = QTextEdit.ExtraSelection()
                    sel.format = fmt
                    c = QTextCursor(doc)
                    c.setPosition(p)
                    c.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
                    sel.cursor = c
                    self._bracket_selections.append(sel)
        except Exception:
            pass

    def _check_bracket_balance(self) -> None:
        try:
            text = self.toPlainText()
            o_brace, c_brace = text.count("{"), text.count("}")
            o_paren, c_paren = text.count("("), text.count(")")
            o_brack, c_brack = text.count("["), text.count("]")

            errs = []
            if o_brace != c_brace:
                diff = abs(o_brace - c_brace)
                errs.append(f"{{}} ({diff} {tr('sin cerrar') if o_brace > c_brace else tr('sobrantes')})")
            if o_paren != c_paren:
                diff = abs(o_paren - c_paren)
                errs.append(f"() ({diff} {tr('sin cerrar') if o_paren > c_paren else tr('sobrantes')})")
            if o_brack != c_brack:
                diff = abs(o_brack - c_brack)
                errs.append(f"[] ({diff} {tr('sin cerrar') if o_brack > c_brack else tr('sobrantes')})")


            if errs:
                self.balanceChanged.emit(False, tr("⚠️ Llaves/paréntesis desbalanceados: ") + ", ".join(errs))
            else:
                self.balanceChanged.emit(True, "")
        except Exception:
            pass

    # ------------------------------------------------------------- Zoom accesible
    def zoom_in(self, delta: int = 1) -> None:
        f = self.font()
        new_size = min(32, f.pointSize() + delta)
        f.setPointSize(new_size)
        self.setFont(f)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 2)
        self.update_line_number_area_width()

    def zoom_out(self, delta: int = 1) -> None:
        f = self.font()
        new_size = max(7, f.pointSize() - delta)
        f.setPointSize(new_size)
        self.setFont(f)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 2)
        self.update_line_number_area_width()

    def zoom_reset(self) -> None:
        f = self.font()
        f.setPointSize(10)
        self.setFont(f)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 2)
        self.update_line_number_area_width()

    def wheelEvent(self, e) -> None:
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = e.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            e.accept()
            return
        super().wheelEvent(e)

    # ------------------------------------------------------------- Edición ergonómica
    def mouseDoubleClickEvent(self, e) -> None:
        if self.isReadOnly():
            self.autoStartEditingRequested.emit()
        super().mouseDoubleClickEvent(e)

    def toggle_comment(self) -> None:
        try:
            tc = self.textCursor()
            doc = self.document()
            start = tc.selectionStart()
            end = tc.selectionEnd()

            start_block = doc.findBlock(start)
            end_block = doc.findBlock(end)

            blocks = []
            b = start_block
            while b.isValid():
                blocks.append(b)
                if b == end_block:
                    break
                b = b.next()

            all_commented = True
            for b in blocks:
                txt = b.text().strip()
                if txt and not txt.startswith("//"):
                    all_commented = False
                    break

            tc.beginEditBlock()
            for b in blocks:
                txt = b.text()
                cur = QTextCursor(b)
                if all_commented:
                    idx = txt.find("//")
                    if idx != -1:
                        cur.setPosition(b.position() + idx)
                        chars = 3 if txt[idx:idx+3] == "// " else 2
                        cur.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, chars)
                        cur.removeSelectedText()
                else:
                    cur.setPosition(b.position())
                    cur.insertText("// ")
            tc.endEditBlock()
        except Exception:
            pass

    def _indent_selection(self, reverse: bool = False) -> None:
        try:
            tc = self.textCursor()
            doc = self.document()
            start = tc.selectionStart()
            end = tc.selectionEnd()

            start_block = doc.findBlock(start)
            end_block = doc.findBlock(end)

            blocks = []
            b = start_block
            while b.isValid():
                blocks.append(b)
                if b == end_block:
                    break
                b = b.next()

            tc.beginEditBlock()
            for b in blocks:
                txt = b.text()
                cur = QTextCursor(b)
                cur.setPosition(b.position())
                if reverse:
                    if txt.startswith("  "):
                        cur.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 2)
                        cur.removeSelectedText()
                    elif txt.startswith(" "):
                        cur.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
                        cur.removeSelectedText()
                else:
                    cur.insertText("  ")
            tc.endEditBlock()
        except Exception:
            pass

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_F2:
            self.autoStartEditingRequested.emit()
            return

        # Atajo Ctrl+Shift+Espacio o Ctrl+P para Signature Help (Ayuda de parámetros)
        is_ctrl_shift_space = (
            (e.modifiers() & Qt.KeyboardModifier.ControlModifier)
            and (e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            and e.key() == Qt.Key.Key_Space
        )
        is_ctrl_p = (
            (e.modifiers() & Qt.KeyboardModifier.ControlModifier)
            and not (e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            and e.key() == Qt.Key.Key_P
        )
        if is_ctrl_shift_space or is_ctrl_p:
            self.toggle_signature_help()
            return

        # Esc cierra la tarjeta flotante de ayuda si está visible
        if e.key() == Qt.Key.Key_Escape and hasattr(self, "sig_popup") and self.sig_popup.isVisible():
            self.sig_popup.hide_signature()
            self._sig_popup_requested = False
            e.accept()
            return

        # Si está en modo sincronizado y escribe una letra imprimible, iniciar edición al vuelo
        if self.isReadOnly() and not (e.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            if e.text() and e.text().isprintable():
                self.autoStartEditingRequested.emit()

        # Manejo de autocompletado rápido con teclado (Estilo VS Code: Tab / Enter aceptan la sugerencia)
        if self._completer and self._completer.popup().isVisible():
            if e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Tab):
                popup = self._completer.popup()
                idx = popup.currentIndex()
                completion = ""
                if idx.isValid():
                    completion = idx.data()
                elif hasattr(self._completer, "currentCompletion") and self._completer.currentCompletion():
                    completion = self._completer.currentCompletion()
                elif popup.model() and popup.model().rowCount() > 0:
                    completion = popup.model().index(0, 0).data()

                if completion:
                    self._insert_completion(completion)
                    popup.hide()
                    e.accept()
                    return

            elif e.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Backtab):
                self._completer.popup().hide()
                e.accept()
                return


        is_ctrl_space = (e.modifiers() & Qt.KeyboardModifier.ControlModifier) and e.key() == Qt.Key.Key_Space
        is_ctrl_slash = (e.modifiers() & Qt.KeyboardModifier.ControlModifier) and e.key() in (
            Qt.Key.Key_Slash, Qt.Key.Key_Question, Qt.Key.Key_7
        )

        if is_ctrl_slash:
            self.toggle_comment()
            return

        try:
            tc = self.textCursor()
        except Exception:
            super().keyPressEvent(e)
            return

        # Tab y Shift+Tab en bloques
        if e.key() == Qt.Key.Key_Backtab or (e.key() == Qt.Key.Key_Tab and (e.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
            self._indent_selection(reverse=True)
            return
        elif e.key() == Qt.Key.Key_Tab:
            if tc.hasSelection():
                self._indent_selection(reverse=False)
                return
            else:
                tc.insertText("  ")
                return

        typed_char = e.text()
        trigger_sig_on_char = typed_char in ("(", ",")

        # Auto-cierre y formateo inteligente
        if not self.isReadOnly() and not tc.hasSelection():
            char = e.text()
            auto_pairs = {"{": "}", "(": ")", "[": "]", '"': '"'}
            if char in auto_pairs:
                close_char = auto_pairs[char]
                doc_text = self.toPlainText()
                pos = tc.position()
                if char == '"' and pos < len(doc_text) and doc_text[pos] == '"':
                    tc.movePosition(QTextCursor.MoveOperation.Right)
                    self.setTextCursor(tc)
                    return
                tc.insertText(char + close_char)
                tc.movePosition(QTextCursor.MoveOperation.Left)
                self.setTextCursor(tc)
                if char == "(":
                    self._sig_popup_requested = True
                    self.update_signature_help(force=True)
                return
            elif char in ("}", ")", "]"):
                doc_text = self.toPlainText()
                pos = tc.position()
                if pos < len(doc_text) and doc_text[pos] == char:
                    tc.movePosition(QTextCursor.MoveOperation.Right)
                    self.setTextCursor(tc)
                    if char == ")":
                        self.update_signature_help(force=False)
                    return


            if e.key() == Qt.Key.Key_Backspace:
                pos = tc.position()
                doc_text = self.toPlainText()
                if 0 < pos < len(doc_text):
                    b_char = doc_text[pos - 1]
                    a_char = doc_text[pos]
                    if (b_char, a_char) in [("{", "}"), ("(", ")"), ("[", "]"), ('"', '"')]:
                        tc.deletePreviousChar()
                        tc.deleteChar()
                        self.setTextCursor(tc)
                        return

            if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                line_text = tc.block().text()
                indent = line_text[:len(line_text) - len(line_text.lstrip())]
                pos_in_block = tc.positionInBlock()
                before_c = line_text[pos_in_block - 1] if pos_in_block > 0 else ""
                after_c = line_text[pos_in_block] if pos_in_block < len(line_text) else ""

                if before_c == "{" and after_c == "}":
                    tc.beginEditBlock()
                    tc.insertText("\n" + indent + "  \n" + indent)
                    tc.movePosition(QTextCursor.MoveOperation.PreviousBlock)
                    tc.movePosition(QTextCursor.MoveOperation.EndOfBlock)
                    tc.endEditBlock()
                    self.setTextCursor(tc)
                    return
                elif before_c == "{":
                    tc.insertText("\n" + indent + "  ")
                    self.setTextCursor(tc)
                    return
                else:
                    tc.insertText("\n" + indent)
                    self.setTextCursor(tc)
                    return

        super().keyPressEvent(e)

        if trigger_sig_on_char:
            self._sig_popup_requested = True
            self.update_signature_help(force=True)

        if not self.isReadOnly() and self._completer:
            ctrl_or_shift = e.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
            if not is_ctrl_space and (ctrl_or_shift and e.text() == ""):
                return

            prefix = self._text_under_cursor()
            if is_ctrl_space or (len(prefix) >= 2 and e.text().isalnum()):
                try:
                    user_mods = re.findall(r"\bmodule\s+([a-zA-Z0-9_]+)", self.toPlainText())
                    all_words = sorted(set(self._words + self._solid_words + user_mods))
                    if hasattr(self._completer, "model") and self._completer.model():
                        model = QStringListModel(all_words, self._completer)
                        self._completer.setModel(model)
                except Exception:
                    pass

                self._completer.setCompletionPrefix(prefix)
                cr = self.cursorRect()
                cr.setWidth(self._completer.popup().sizeHintForColumn(0)
                            + self._completer.popup().verticalScrollBar().sizeHint().width())
                self._completer.complete(cr)
                popup = self._completer.popup()
                if popup and popup.model() and popup.model().rowCount() > 0:
                    popup.setCurrentIndex(popup.model().index(0, 0))
            else:
                if self._completer.popup().isVisible():
                    self._completer.popup().hide()



class CodeView(QWidget):
    lineClicked = Signal(int)          # línea (base 0) en modo sincronizado
    applyRequested = Signal(str)       # texto editado a mano
    editingChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.editing = False
        self._silent = False
        self._span = None
        self._find_matches: list[int] = []
        self._current_match_idx = -1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Cabecera
        head = QWidget()
        head.setObjectName("panelHead")
        row = QHBoxLayout(head)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)

        self.title_lbl = QLabel(tr("CÓDIGO OPENSCAD"))
        self.title_lbl.setObjectName("sectionTitle")
        row.addWidget(self.title_lbl)


        # Menú de snippets rápidos
        self.btn_snippets = QToolButton()
        self.btn_snippets.setText(tr("+ Insertar bloque"))
        self.btn_snippets.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_snippets.setStyleSheet(
            "QToolButton { background: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 4px; "
            "padding: 3px 8px; font-size: 11px; } QToolButton:hover { background: #E2E8F0; }"
        )
        self._build_snippets_menu()
        row.addWidget(self.btn_snippets)

        # Botón de buscar Ctrl+F
        self.btn_search = QToolButton()
        self.btn_search.setText("🔍")
        self.btn_search.setToolTip(tr("Buscar en el código (Ctrl+F)"))
        self.btn_search.clicked.connect(self.toggle_find_bar)
        row.addWidget(self.btn_search)

        row.addStretch(1)

        self.badge = QLabel(tr("Sincronizado"))
        self.badge.setObjectName("okBadge")
        row.addWidget(self.badge)

        self.edit_btn = QPushButton(tr("Editar"))
        self.edit_btn.setToolTip(tr("Entrar en modo edición manual (o pulsa F2)"))
        self.edit_btn.clicked.connect(self.start_editing)
        row.addWidget(self.edit_btn)

        self.apply_btn = QPushButton(tr("Aplicar"))
        self.apply_btn.setObjectName("primary")
        self.apply_btn.setToolTip(tr("Leer el código y actualizar el árbol (Ctrl+Enter)"))
        self.apply_btn.clicked.connect(lambda: self.applyRequested.emit(self.text.toPlainText()))
        row.addWidget(self.apply_btn)

        self.cancel_btn = QPushButton(tr("Descartar"))
        self.cancel_btn.clicked.connect(lambda: self.stop_editing(discard=True))
        row.addWidget(self.cancel_btn)

        layout.addWidget(head)

        # Barra de búsqueda desplegable
        self.find_bar = FindBar()
        self.find_bar.setVisible(False)
        self.find_bar.findNext.connect(lambda text: self.find_text(text, forward=True))
        self.find_bar.findPrev.connect(lambda text: self.find_text(text, forward=False))
        self.find_bar.closed.connect(self.hide_find_bar)
        layout.addWidget(self.find_bar)

        # Editor de código accesible
        self.text = ScadEditor()
        self.text.setObjectName("codeText")
        self.text.setFont(mono_font(10))
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setTabStopDistance(self.text.fontMetrics().horizontalAdvance(" ") * 2)
        self.highlighter = ScadHighlighter(self.text.document())
        self.text.cursorPositionChanged.connect(self._cursor_moved)
        self.text.autoStartEditingRequested.connect(self.start_editing)
        self.text.balanceChanged.connect(self._on_balance_changed)
        self.text.signatureHelpChanged.connect(self._on_signature_help_changed)
        layout.addWidget(self.text, 1)

        # Barra de aviso de llaves desbalanceadas
        self.balance_bar = QLabel()
        self.balance_bar.setStyleSheet(
            "background-color: #FEF3C7; border-top: 1px solid #F59E0B; color: #92400E; "
            "padding: 4px 8px; font-size: 11px; font-weight: 500;"
        )
        self.balance_bar.setVisible(False)
        layout.addWidget(self.balance_bar)

        # Barra de ayuda contextual didáctica para booleanas
        self.bool_hint_bar = QLabel()
        self.bool_hint_bar.setObjectName("boolHintBar")
        self.bool_hint_bar.setWordWrap(True)
        self.bool_hint_bar.setStyleSheet(
            "QLabel#boolHintBar { background-color: #EFF6FF; border-top: 1px solid #BFDBFE; "
            "color: #1E40AF; padding: 5px 10px; font-size: 11px; font-weight: 500; }"
        )
        self.bool_hint_bar.setVisible(False)
        layout.addWidget(self.bool_hint_bar)

        # Barra de ayuda de parámetros / firma de funciones
        self.sig_hint_bar = QLabel()
        self.sig_hint_bar.setObjectName("sigHintBar")
        self.sig_hint_bar.setWordWrap(True)
        self.sig_hint_bar.setStyleSheet(
            "QLabel#sigHintBar { background-color: #F0F9FF; border-top: 1px solid #BAE6FD; "
            "color: #0369A1; padding: 4px 10px; font-size: 11px; font-weight: 500; }"
        )
        self.sig_hint_bar.setVisible(False)
        layout.addWidget(self.sig_hint_bar)

        # Pie informativo con atajos accesibles
        self.foot = QLabel(tr("Ctrl+Enter: Aplicar · Ctrl+F: Buscar · Ctrl+Shift+Espacio: Parámetros · Ctrl+/: Comentar · Zoom: Ctrl+Rueda"))
        self.foot.setWordWrap(True)
        self.foot.setObjectName("panelFoot")
        layout.addWidget(self.foot)



        # Atajos de teclado
        apply_sc = QShortcut(QKeySequence("Ctrl+Return"), self.text)
        apply_sc.activated.connect(lambda: self.applyRequested.emit(self.text.toPlainText()) if self.editing else None)

        esc_sc = QShortcut(QKeySequence("Escape"), self)
        esc_sc.activated.connect(self._on_escape)

        find_sc = QShortcut(QKeySequence("Ctrl+F"), self)
        find_sc.activated.connect(self.show_find_bar)

        zoom_in_sc = QShortcut(QKeySequence.StandardKey.ZoomIn, self.text)
        zoom_in_sc.activated.connect(self.text.zoom_in)

        zoom_out_sc = QShortcut(QKeySequence.StandardKey.ZoomOut, self.text)
        zoom_out_sc.activated.connect(self.text.zoom_out)

        zoom_reset_sc = QShortcut(QKeySequence("Ctrl+0"), self.text)
        zoom_reset_sc.activated.connect(self.text.zoom_reset)

        self._update_mode()
        self._saved = ""

    def _build_snippets_menu(self) -> None:
        menu = QMenu(self)
        for label, snippet in SNIPPETS_CATALOG:
            action = menu.addAction(tr(label))
            action.triggered.connect(lambda _=False, s=snippet: self.insert_snippet(s))
        self.btn_snippets.setMenu(menu)

    def retranslate_ui(self) -> None:
        """Actualiza todos los textos del panel de código al cambiar el idioma de la aplicación."""
        if hasattr(self, "title_lbl"):
            self.title_lbl.setText(tr("CÓDIGO OPENSCAD"))
        if hasattr(self, "btn_snippets"):
            self.btn_snippets.setText(tr("+ Insertar bloque"))
            self._build_snippets_menu()
        if hasattr(self, "btn_search"):
            self.btn_search.setToolTip(tr("Buscar en el código (Ctrl+F)"))
        if hasattr(self, "edit_btn"):
            self.edit_btn.setText(tr("Editar"))
            self.edit_btn.setToolTip(tr("Entrar en modo edición manual (o pulsa F2)"))
        if hasattr(self, "apply_btn"):
            self.apply_btn.setText(tr("Aplicar"))
            self.apply_btn.setToolTip(tr("Leer el código y actualizar el árbol (Ctrl+Enter)"))
        if hasattr(self, "cancel_btn"):
            self.cancel_btn.setText(tr("Descartar"))
        if hasattr(self, "badge"):
            self.badge.setText(tr("Editando a mano") if self.editing else tr("Sincronizado"))
        if hasattr(self, "foot"):
            self.foot.setText(tr("Ctrl+Enter: Aplicar · Ctrl+F: Buscar · Ctrl+Shift+Espacio: Parámetros · Ctrl+/: Comentar · Zoom: Ctrl+Rueda"))
        if hasattr(self, "find_bar") and hasattr(self.find_bar, "retranslate_ui"):
            self.find_bar.retranslate_ui()
        if hasattr(self.text, "sig_popup") and hasattr(self.text.sig_popup, "retranslate_ui"):
            self.text.sig_popup.retranslate_ui()
        self._update_boolean_context_tip()
        self.text.update_signature_help(force=False)


    def insert_snippet(self, code: str) -> None:
        if not self.editing:
            self.start_editing()
        tc = self.text.textCursor()
        tc.insertText(code + "\n")
        self.text.setTextCursor(tc)
        self.text.setFocus()

    # ------------------------------------------------------------- Búsqueda Ctrl+F
    def toggle_find_bar(self) -> None:
        if self.find_bar.isVisible():
            self.hide_find_bar()
        else:
            self.show_find_bar()

    def show_find_bar(self) -> None:
        self.find_bar.setVisible(True)
        tc = self.text.textCursor()
        if tc.hasSelection():
            sel_text = tc.selectedText().strip()
            if "\u2029" not in sel_text and len(sel_text) < 40:
                self.find_bar.input.setText(sel_text)
        self.find_bar.input.selectAll()
        self.find_bar.input.setFocus()
        if self.find_bar.input.text():
            self.find_text(self.find_bar.input.text(), forward=True)

    def hide_find_bar(self) -> None:
        self.find_bar.setVisible(False)
        self.text._search_selections = []
        self.text.update_extra_selections()
        self.text.setFocus()

    def find_text(self, pattern: str, forward: bool = True) -> None:
        if not pattern:
            self.text._search_selections = []
            self.text.update_extra_selections()
            self.find_bar.set_count(0, 0)
            return

        doc = self.text.document()
        text = doc.toPlainText()
        pat_lower = pattern.lower()
        text_lower = text.lower()

        # Encontrar todas las ocurrencias
        indices = []
        start = 0
        while True:
            idx = text_lower.find(pat_lower, start)
            if idx == -1:
                break
            indices.append(idx)
            start = idx + len(pattern)

        self._find_matches = indices
        total = len(indices)

        if total == 0:
            self.find_bar.set_count(0, 0)
            self.text._search_selections = []
            self.text.update_extra_selections()
            return

        # Determinar cuál es la siguiente o anterior
        curr_pos = self.text.textCursor().position()
        if forward:
            next_indices = [i for i in indices if i > curr_pos]
            target_idx = next_indices[0] if next_indices else indices[0]
        else:
            prev_indices = [i for i in indices if i < curr_pos - len(pattern)]
            target_idx = prev_indices[-1] if prev_indices else indices[-1]

        self._current_match_idx = indices.index(target_idx)
        self.find_bar.set_count(self._current_match_idx + 1, total)

        # Mover el cursor al resultado
        cur = QTextCursor(doc)
        cur.setPosition(target_idx)
        cur.setPosition(target_idx + len(pattern), QTextCursor.MoveMode.KeepAnchor)
        self.text.setTextCursor(cur)
        self.text.centerCursor()

        # Resaltar todas las ocurrencias
        selections = []
        fmt_all = QTextCharFormat()
        fmt_all.setBackground(QColor("#FEF08A"))  # Amarillo suave

        fmt_current = QTextCharFormat()
        fmt_current.setBackground(QColor("#FDE047"))  # Amarillo intenso
        fmt_current.setFontWeight(QFont.Weight.Bold)

        for i, idx in enumerate(indices):
            sel = QTextEdit.ExtraSelection()
            c = QTextCursor(doc)
            c.setPosition(idx)
            c.setPosition(idx + len(pattern), QTextCursor.MoveMode.KeepAnchor)
            sel.cursor = c
            sel.format = fmt_current if i == self._current_match_idx else fmt_all
            selections.append(sel)

        self.text._search_selections = selections
        self.text.update_extra_selections()

    def _on_escape(self) -> None:
        if hasattr(self.text, "sig_popup") and self.text.sig_popup.isVisible():
            self.text.sig_popup.hide_signature()
            self.text._sig_popup_requested = False
        elif self.find_bar.isVisible():
            self.hide_find_bar()
        elif self.editing:
            self.stop_editing(discard=True)

    def _on_signature_help_changed(self, sig_info: dict | None) -> None:
        if not sig_info:
            self.sig_hint_bar.setVisible(False)
            return

        try:
            sig_html, detail_html = format_signature_html(sig_info)
            self.sig_hint_bar.setText(f"📘 {sig_html} &nbsp;·&nbsp; {detail_html}")
            self.sig_hint_bar.setVisible(True)
        except Exception:
            self.sig_hint_bar.setVisible(False)


    def _on_balance_changed(self, balanced: bool, msg: str) -> None:
        if not balanced:
            self.balance_bar.setText(msg)
            self.balance_bar.setVisible(True)
        else:
            self.balance_bar.setVisible(False)

    # ------------------------------------------------------------- Modo edición / sincronizado
    def _update_mode(self) -> None:
        self.text.setReadOnly(not self.editing)
        self.edit_btn.setVisible(not self.editing)
        self.apply_btn.setVisible(self.editing)
        self.cancel_btn.setVisible(self.editing)
        self.badge.setText(tr("Editando a mano") if self.editing else tr("Sincronizado"))
        self.badge.setObjectName("warnBadge" if self.editing else "okBadge")
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
        self.text.setProperty("editing", self.editing)
        self.text.style().unpolish(self.text)
        self.text.style().polish(self.text)
        self.text.update_extra_selections()

    def start_editing(self, line: int | None = None) -> None:
        if not self.editing:
            self._saved = self.text.toPlainText()
            self.editing = True
            self._span = None
            self.text._span_selections = []
            self._update_mode()
            self.editingChanged.emit(True)
        self.text.setFocus()
        if line is not None:
            self._goto(line)

    def stop_editing(self, discard: bool = False) -> None:
        if not self.editing:
            return
        self.editing = False
        if discard:
            self.set_code(self._saved)
        self._update_mode()
        self.editingChanged.emit(False)

    def set_code(self, code: str) -> None:
        if self.editing:
            return
        if code == self.text.toPlainText():
            return
        bar = self.text.verticalScrollBar().value()
        self._silent = True
        self.text.setPlainText(code)
        self._silent = False
        self.text.verticalScrollBar().setValue(bar)
        self.highlight_span(self._span, scroll=False)

    def set_document_solids(self, solids: list[tuple[int, str, str]]) -> None:
        self.text.set_solids_completions(solids)

    def highlight_span(self, span, scroll: bool = True) -> None:
        self._span = span
        if self.editing:
            return
        sels = []
        if span:
            a, b = span
            doc = self.text.document()
            for line in range(a, b + 1):
                block = doc.findBlockByNumber(line)
                if not block.isValid():
                    break
                sel = QTextEdit.ExtraSelection()
                fmt = QTextCharFormat()
                fmt.setBackground(QColor("#E3ECFA"))
                fmt.setProperty(QTextFormat.Property.FullWidthSelection, True)
                sel.format = fmt
                sel.cursor = QTextCursor(block)
                sels.append(sel)
            if scroll:
                self._goto(a, select=False)
        self.text._span_selections = sels
        self.text.update_extra_selections()

    def _goto(self, line: int, select: bool = True) -> None:
        block = self.text.document().findBlockByNumber(line)
        if not block.isValid():
            return
        self._silent = True
        cur = QTextCursor(block)
        self.text.setTextCursor(cur)
        self.text.centerCursor()
        self._silent = False

    def _cursor_moved(self) -> None:
        self._update_boolean_context_tip()
        if self._silent or self.editing:
            return
        self.lineClicked.emit(self.text.textCursor().blockNumber())

    def _update_boolean_context_tip(self) -> None:
        cursor = self.text.textCursor()
        block_text = cursor.block().text()

        detected = None
        for k in ("difference", "union", "intersection"):
            if re.search(rf"\b{k}\b", block_text):
                detected = k
                break

        if detected is None:
            doc = self.text.document()
            curr = cursor.blockNumber()
            depth = 0
            for l in range(curr, max(-1, curr - 15), -1):
                txt = doc.findBlockByNumber(l).text()
                depth += txt.count("}") - txt.count("{")
                if depth <= 0:
                    for k in ("difference", "union", "intersection"):
                        if re.search(rf"\b{k}\s*\(", txt):
                            detected = k
                            break
                if detected is not None:
                    break

        if detected == "difference":
            self.bool_hint_bar.setText(
                tr("💡 difference(): El 1er sólido es la BASE (+); todos los siguientes se le RESTAN (-) como cortes o huecos.")
            )
            self.bool_hint_bar.setStyleSheet(
                "QLabel#boolHintBar { background-color: #FEF2F2; border-top: 1px solid #FECACA; "
                "color: #991B1B; padding: 5px 10px; font-size: 11px; font-weight: 500; }"
            )
            self.bool_hint_bar.setVisible(True)
        elif detected == "union":
            self.bool_hint_bar.setText(
                tr("💡 union(): Todos los sólidos hijos se unen y fusionan (∪) en un único cuerpo continuo.")
            )
            self.bool_hint_bar.setStyleSheet(
                "QLabel#boolHintBar { background-color: #F0FDF4; border-top: 1px solid #BBF7D0; "
                "color: #166534; padding: 5px 10px; font-size: 11px; font-weight: 500; }"
            )
            self.bool_hint_bar.setVisible(True)
        elif detected == "intersection":
            self.bool_hint_bar.setText(
                tr("💡 intersection(): Conserva exclusivamente el volumen común donde coinciden todos los sólidos (∩).")
            )
            self.bool_hint_bar.setStyleSheet(
                "QLabel#boolHintBar { background-color: #FAF5FF; border-top: 1px solid #E9D5FF; "
                "color: #6B21A8; padding: 5px 10px; font-size: 11px; font-weight: 500; }"
            )
            self.bool_hint_bar.setVisible(True)
        else:
            self.bool_hint_bar.setVisible(False)
