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

from PySide6.QtCore import QRect, QSize, QStringListModel, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QKeySequence, QPainter, QShortcut, QSyntaxHighlighter,
                           QTextCharFormat, QTextCursor, QTextFormat)
from PySide6.QtWidgets import (QCompleter, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QPlainTextEdit,
                               QPushButton, QTextEdit, QToolButton, QVBoxLayout, QWidget)

from ..catalog import CONTROL_KEYWORDS, openscad_modules
from ..code_assist import (BOOLEAN_TEMPLATES, OPENSCAD_BUILTINS, SNIPPETS_CATALOG, find_active_call,
                           format_signature_html, get_signature_info)
from ..i18n import tr
from .icons import icon


def mono_font(size: int = 10) -> QFont:
    f = QFont()
    f.setFamilies(["IBM Plex Mono", "Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono", "monospace"])
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setPointSize(size)
    return f


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

        modules = "|".join(sorted(openscad_modules(), key=len, reverse=True))
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
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
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

        self.lbl = QLabel(f"{tr('Buscar')}:")
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
        self.lbl.setText(f"{tr('Buscar')}:")
        self.input.setPlaceholderText(tr("Texto a buscar… (Enter para siguiente)"))
        self.btn_prev.setToolTip(tr("Coincidencia anterior (Shift+F3)"))
        self.btn_next.setToolTip(tr("Siguiente coincidencia (F3 o Enter)"))
        self.btn_close.setToolTip(tr("Cerrar búsqueda (Escape)"))


class SignatureHelpPopup(QFrame):
    """Tarjeta flotante que muestra la firma y ayuda de parámetros (parameter hints) cerca del cursor."""

    def __init__(self, editor: "ScadEditor"):
        super().__init__(editor, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.code_editor = editor
        self.setObjectName("signatureHelpPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setStyleSheet(
            "QFrame#signatureHelpPopup { "
            "  background-color: #FFFFFF; "
            "  border: 1px solid #3B82F6; "
            "  border-radius: 6px; "
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
        sig_html, detail_html = format_signature_html(sig_info)
        self.lbl_category.setText(sig_info["category"])
        self.lbl_sig.setText(sig_html)
        self.lbl_detail.setText(detail_html)
        self.adjustSize()


        cr = self.code_editor.cursorRect()
        global_pt = self.code_editor.viewport().mapToGlobal(cr.topLeft())
        pop_h = self.sizeHint().height()

        # Posicionar por defecto arriba del cursor para no tapar lo que se escribe
        x = max(10, global_pt.x() - 15)
        y = global_pt.y() - pop_h - 6
        if y < 20:  # Si no hay espacio arriba, ubicar debajo
            y = global_pt.y() + cr.height() + 6

        self.move(x, y)
        self.show()

    def hide_signature(self) -> None:
        self.hide()

    def retranslate_ui(self) -> None:
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

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)

        self.cursorPositionChanged.connect(self._on_cursor_changed)
        self.textChanged.connect(self._on_text_changed)
        self.update_line_number_area_width(0)
        self._init_completer()

    def update_signature_help(self, force: bool = False) -> None:
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

    def toggle_signature_help(self) -> None:
        if self.sig_popup.isVisible():
            self.sig_popup.hide_signature()
            self._sig_popup_requested = False
        else:
            self._sig_popup_requested = True
            self.update_signature_help(force=True)


    def _init_completer(self) -> None:
        base = openscad_modules() + list(CONTROL_KEYWORDS) + list(OPENSCAD_BUILTINS.keys())
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
        digits = len(str(max(1, self.blockCount())))
        return max(36, 14 + self.fontMetrics().horizontalAdvance("9") * digits)

    def update_line_number_area_width(self, _=0) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event) -> None:
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
        selections = []

        # 1. Resaltado de la pieza seleccionada (span)
        selections.extend(self._span_selections)

        # 2. Resaltado de la línea actual
        if not self.isReadOnly() or not self._span_selections:
            line_sel = QTextEdit.ExtraSelection()
            line_fmt = QTextCharFormat()
            line_fmt.setBackground(QColor("#F8FAFC") if self.isReadOnly() else QColor("#F1F5F9"))
            line_fmt.setProperty(QTextFormat.Property.FullWidthSelection, True)
            line_sel.format = line_fmt
            line_sel.cursor = self.textCursor()
            line_sel.cursor.clearSelection()
            selections.append(line_sel)

        # 3. Resaltado de brackets
        selections.extend(self._bracket_selections)

        # 4. Resaltado de búsqueda
        selections.extend(self._search_selections)

        self.setExtraSelections(selections)

    def match_brackets(self) -> None:
        self._bracket_selections = []
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

    def _check_bracket_balance(self) -> None:
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
            self.balanceChanged.emit(False, tr("Llaves/paréntesis desbalanceados: ") + ", ".join(errs))
        else:
            self.balanceChanged.emit(True, "")

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

    def _indent_selection(self, reverse: bool = False) -> None:
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
        if e.key() == Qt.Key.Key_Escape and self.sig_popup.isVisible():
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
                elif self._completer.currentCompletion():
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

        tc = self.textCursor()

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
                user_mods = re.findall(r"\bmodule\s+([a-zA-Z0-9_]+)", self.toPlainText())
                all_words = sorted(set(self._words + self._solid_words + user_mods))
                if self._completer.model():
                    model = QStringListModel(all_words, self._completer)
                    self._completer.setModel(model)

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
        self.btn_search.setIcon(icon("search", "#3D4756"))
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
        self.title_lbl.setText(tr("CÓDIGO OPENSCAD"))
        self.btn_snippets.setText(tr("+ Insertar bloque"))
        self._build_snippets_menu()
        self.btn_search.setToolTip(tr("Buscar en el código (Ctrl+F)"))
        self.edit_btn.setText(tr("Editar"))
        self.edit_btn.setToolTip(tr("Entrar en modo edición manual (o pulsa F2)"))
        self.apply_btn.setText(tr("Aplicar"))
        self.apply_btn.setToolTip(tr("Leer el código y actualizar el árbol (Ctrl+Enter)"))
        self.cancel_btn.setText(tr("Descartar"))
        self.badge.setText(tr("Editando a mano") if self.editing else tr("Sincronizado"))
        self.foot.setText(tr("Ctrl+Enter: Aplicar · Ctrl+F: Buscar · Ctrl+Shift+Espacio: Parámetros · Ctrl+/: Comentar · Zoom: Ctrl+Rueda"))
        self.find_bar.retranslate_ui()
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
        if self.text.sig_popup.isVisible():
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

        sig_html, detail_html = format_signature_html(sig_info)
        self.sig_hint_bar.setText(f"{sig_html} &nbsp;·&nbsp; {detail_html}")
        self.sig_hint_bar.setVisible(True)


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
                tr("difference(): El 1er sólido es la BASE (+); todos los siguientes se le RESTAN (-) como cortes o huecos.")
            )
            self.bool_hint_bar.setStyleSheet(
                "QLabel#boolHintBar { background-color: #FEF2F2; border-top: 1px solid #FECACA; "
                "color: #991B1B; padding: 5px 10px; font-size: 11px; font-weight: 500; }"
            )
            self.bool_hint_bar.setVisible(True)
        elif detected == "union":
            self.bool_hint_bar.setText(
                tr("union(): Todos los sólidos hijos se unen y fusionan (∪) en un único cuerpo continuo.")
            )
            self.bool_hint_bar.setStyleSheet(
                "QLabel#boolHintBar { background-color: #F0FDF4; border-top: 1px solid #BBF7D0; "
                "color: #166534; padding: 5px 10px; font-size: 11px; font-weight: 500; }"
            )
            self.bool_hint_bar.setVisible(True)
        elif detected == "intersection":
            self.bool_hint_bar.setText(
                tr("intersection(): Conserva exclusivamente el volumen común donde coinciden todos los sólidos (∩).")
            )
            self.bool_hint_bar.setStyleSheet(
                "QLabel#boolHintBar { background-color: #FAF5FF; border-top: 1px solid #E9D5FF; "
                "color: #6B21A8; padding: 5px 10px; font-size: 11px; font-weight: 500; }"
            )
            self.bool_hint_bar.setVisible(True)
        else:
            self.bool_hint_bar.setVisible(False)
