"""Panel de propiedades: un formulario generado a partir de los parámetros del catálogo."""

from __future__ import annotations

import copy
import os
from typing import Any, Optional

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton,
                               QScrollArea, QSpinBox, QToolButton, QVBoxLayout, QWidget)

from ..catalog import Param
from ..i18n import tr
from ..model import Document, Expr, Node, RawCode, format_value
from ..parser import literal
from .editors import edit_faces, edit_matrix, edit_points
from .icons import icon

COLOR_NAMES = ["SteelBlue", "Gold", "Tomato", "SeaGreen", "SlateGray", "Orange", "Crimson",
               "RoyalBlue", "Purple", "Black", "White", "Silver", "Brown", "Pink", "Teal"]


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _rows_of(v: Any, n: Optional[int], ints: bool = False) -> bool:
    if not isinstance(v, list) or not v:
        return False
    for row in v:
        if not isinstance(row, list) or not row or not all(_is_num(x) for x in row):
            return False
        if n is not None and len(row) != n:
            return False
        if ints and not all(float(x).is_integer() for x in row):
            return False
    return True


def conforms(p: Param, v: Any) -> bool:
    """¿El valor actual se puede mostrar con el editor "bonito" de su tipo?"""
    k = p.kind
    if k in ("num",):
        return _is_num(v)
    if k == "int":
        return _is_num(v) and float(v).is_integer()
    if k == "bool":
        return isinstance(v, bool)
    if k in ("vec2", "vec3"):
        n = 2 if k == "vec2" else 3
        return isinstance(v, list) and len(v) == n and all(_is_num(x) for x in v)
    if k in ("str", "file", "color"):
        return isinstance(v, str)
    if k == "choice":
        return isinstance(v, str) and v in p.options
    if k == "points2":
        return _rows_of(v, 2)
    if k == "points3":
        return _rows_of(v, 3)
    if k == "faces":
        return _rows_of(v, None, ints=True)
    if k == "matrix":
        return _rows_of(v, 4) and len(v) in (3, 4)
    return False  # expr


class _WheelGuard(QObject):
    """La rueda del ratón no cambia valores de un campo que no tiene el foco."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and not obj.hasFocus():
            event.ignore()
            return True
        return False


class PropertyPanel(QScrollArea):
    changed = Signal(int, str, object)    # id del nodo, parámetro, valor (None = quitar)
    renamed = Signal(int, str)
    editCode = Signal(int)
    fnChanged = Signal(object)
    selectNode = Signal(int)
    openBooleanWizard = Signal(int)
    setDifferenceBase = Signal(int, int)
    openOperationHelper = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.node = None
        self.doc: Optional[Document] = None
        self.base_dir = ""
        self._guard = _WheelGuard(self)
        self._body = QWidget()
        self.setWidget(self._body)
        self.show_node(None, Document())

    # ----------------------------------------------------------------- construcción
    def show_node(self, node, doc: Document) -> None:
        self.node = node
        self.doc = doc
        body = QWidget()
        body.setObjectName("propsBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(10)
        self._lay = lay

        if node is None:
            self._document_form(doc)
        elif isinstance(node, RawCode):
            self._raw_form(node)
        else:
            self._node_form(node)
        lay.addStretch(1)
        old = self.takeWidget()
        if old is not None:
            old.deleteLater()
        self.setWidget(body)

    def refresh(self) -> None:
        QTimer.singleShot(0, lambda: self.show_node(self.node, self.doc))

    def _title(self, text: str, mono: str = "") -> None:
        row = QHBoxLayout()
        t = QLabel(text)
        t.setObjectName("sectionTitle")
        row.addWidget(t)
        row.addStretch(1)
        if mono:
            m = QLabel(mono)
            m.setObjectName("accentMono")
            row.addWidget(m)
        self._lay.addLayout(row)

    def _hint(self, text: str, kind: str = "hint") -> QLabel:
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setObjectName(kind)
        self._lay.addWidget(lab)
        return lab

    def _caption(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("caption")
        return lab

    # ----- sin selección: ajustes del documento
    def _document_form(self, doc: Document) -> None:
        self._title(tr("Documento"))
        self._hint(tr("Selecciona una pieza en el árbol para editar sus propiedades, o crea una con la cinta de arriba."))
        row = QHBoxLayout()
        check = QCheckBox(tr("Resolución global ($fn)"))
        spin = QSpinBox()
        spin.setRange(3, 512)
        spin.setValue(doc.fn or 64)
        spin.setEnabled(bool(doc.fn))
        check.setChecked(bool(doc.fn))
        self._guarded(spin)
        check.toggled.connect(lambda on: (spin.setEnabled(on), self.fnChanged.emit(spin.value() if on else None)))
        spin.valueChanged.connect(lambda v: self.fnChanged.emit(v) if check.isChecked() else None)
        row.addWidget(check)
        row.addWidget(spin)
        self._lay.addLayout(row)
        self._hint(tr("Más segmentos = curvas más suaves y vista previa más lenta."), "caption")

    # ----- código literal
    def _raw_form(self, node: RawCode) -> None:
        self._title(tr("Comentario") if node.is_comment else tr("Código"), tr("solo código"))
        box = QLabel(tr("<b>Bloque programado</b><br>Este fragmento usa lógica de OpenSCAD (variables, "
                        "bucles, módulos…). Se conserva tal cual y se edita en el panel de código "
                        "para no romperlo.") if not node.is_comment else
                     tr("Comentario del archivo. Se conserva al guardar."))
        box.setWordWrap(True)
        box.setObjectName("warnBox")
        self._lay.addWidget(box)
        view = QPlainTextEdit(node.text)
        view.setReadOnly(True)
        view.setObjectName("rawView")
        view.setMinimumHeight(120)
        self._lay.addWidget(view)
        btn = QPushButton(tr("Editar en el código"))
        btn.clicked.connect(lambda: self.editCode.emit(node.id))
        self._lay.addWidget(btn)

    # ----- nodo normal
    def _node_form(self, node: Node) -> None:
        spec = node.spec
        self._title(tr("Propiedades"), f"{node.kind}()")
        self._lay.addWidget(self._caption(tr("Nombre")))
        name = QLineEdit(node.name)
        name.setPlaceholderText(tr(spec.label) if spec else node.kind)
        name.editingFinished.connect(lambda: self.renamed.emit(node.id, name.text()))
        self._lay.addWidget(name)

        for p in (spec.params if spec else ()):
            self._param_row(node, p)

        extras = [k for k in node.params if not spec or not spec.param(k)]
        for key in extras:
            self._extra_row(node, key)

        if spec and spec.hint:
            self._hint(tr(spec.hint))
        if spec and spec.container and not node.children:
            self._hint(tr("Está vacío: selecciónalo y añade piezas desde la cinta, o usa "
                          "“Meter en el de arriba” en el árbol."), "warnText")
        if spec and spec.level == "experimental":
            self._hint(tr("Función experimental: OpenSCAD la ejecuta con --enable=roof."), "warnText")

        if node.kind in ("difference", "union", "intersection"):
            self._boolean_form(node)
        self._operation_helper_form(node)

    def _operation_helper_form(self, node: Node) -> None:
        """Añade el widget helper interactivo si la operación tiene guía o presets disponibles."""
        from .operation_helper import OPERATION_HELPERS, OperationHelperWidget
        if node.kind in OPERATION_HELPERS and node.kind not in ("difference", "union", "intersection"):
            helper_w = OperationHelperWidget(node.kind, node.params, self)
            helper_w.presetApplied.connect(lambda param_name, new_val: self.changed.emit(node.id, param_name, new_val))
            helper_w.openFullGuideRequested.connect(self.openOperationHelper.emit)
            self._lay.addWidget(helper_w)

    def _boolean_form(self, node: Node) -> None:
        """Muestra un panel visual interactivo sobre la operación booleana y los roles de sus piezas."""
        box = QFrame()
        box.setObjectName("booleanPanelBox")
        box.setStyleSheet(
            "QFrame#booleanPanelBox { background-color: #F8FAFC; border: 1px solid #CBD5E1; "
            "border-radius: 6px; padding: 10px; margin-top: 8px; }"
        )
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        if node.kind == "difference":
            title = QLabel(f"✂️ <b>{tr('Operación Restar (difference)')}</b>")
            title.setStyleSheet("color: #991B1B; font-size: 13px;")
            lay.addWidget(title)

            desc = QLabel(tr("El primer sólido es la Base (+); los siguientes se le restan (-) como cortes o huecos."))
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #475569; font-size: 11px;")
            lay.addWidget(desc)

            if node.children:
                # 1er hijo: Base
                base_child = node.children[0]
                base_row = QHBoxLayout()
                base_lbl = QLabel(f"⭐ <b>{tr('Base (+)')}:</b> {base_child.label}")
                base_lbl.setStyleSheet("color: #166534; font-size: 12px;")
                base_row.addWidget(base_lbl, 1)
                btn_view_base = QPushButton(tr("Ver"))
                btn_view_base.setMaximumWidth(50)
                btn_view_base.clicked.connect(lambda: self.selectNode.emit(base_child.id))
                base_row.addWidget(btn_view_base)
                lay.addLayout(base_row)

                # Siguientes hijos: Restas
                restas = node.children[1:]
                if restas:
                    lbl_restas = QLabel(f"✂️ <b>{tr('Sólidos que se restan (-)')}:</b>")
                    lbl_restas.setStyleSheet("color: #991B1B; font-size: 12px; margin-top: 4px;")
                    lay.addWidget(lbl_restas)

                    for r in restas:
                        r_row = QHBoxLayout()
                        r_lbl = QLabel(f"  • {r.label}")
                        r_lbl.setStyleSheet("color: #334155; font-size: 11px;")
                        r_row.addWidget(r_lbl, 1)

                        btn_make_base = QPushButton(tr("Hacer Base"))
                        btn_make_base.setToolTip(tr("Mover esta pieza al 1er lugar para que sea la base a la que se resta"))
                        btn_make_base.setMaximumWidth(80)
                        btn_make_base.clicked.connect(lambda _=False, cid=r.id: self.setDifferenceBase.emit(node.id, cid))
                        r_row.addWidget(btn_make_base)

                        btn_view_r = QPushButton(tr("Ver"))
                        btn_view_r.setMaximumWidth(50)
                        btn_view_r.clicked.connect(lambda _=False, cid=r.id: self.selectNode.emit(cid))
                        r_row.addWidget(btn_view_r)
                        lay.addLayout(r_row)
                else:
                    lay.addWidget(QLabel(f"<i>{tr('(Aún no hay piezas para restar. Añade otra pieza a este grupo)')}</i>"))
            else:
                lay.addWidget(QLabel(f"<i>{tr('(difference vacío. Añade una base y piezas para restar)')}</i>"))

        elif node.kind == "union":
            title = QLabel(f"➕ <b>{tr('Operación Unir (union)')}</b>")
            title.setStyleSheet("color: #15803D; font-size: 13px;")
            lay.addWidget(title)

            desc = QLabel(tr("Fusiona todos los sólidos hijos en un único cuerpo sólido continuo."))
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #475569; font-size: 11px;")
            lay.addWidget(desc)

            for c in node.children:
                row = QHBoxLayout()
                lbl = QLabel(f"  • {c.label}")
                lbl.setStyleSheet("color: #334155; font-size: 11px;")
                row.addWidget(lbl, 1)
                btn = QPushButton(tr("Ver"))
                btn.setMaximumWidth(50)
                btn.clicked.connect(lambda _=False, cid=c.id: self.selectNode.emit(cid))
                row.addWidget(btn)
                lay.addLayout(row)

        else:  # intersection
            title = QLabel(f"🔍 <b>{tr('Operación Intersecar (intersection)')}</b>")
            title.setStyleSheet("color: #6B21A8; font-size: 13px;")
            lay.addWidget(title)

            desc = QLabel(tr("Conserva exclusivamente el volumen común compartido por todos los sólidos hijos."))
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #475569; font-size: 11px;")
            lay.addWidget(desc)

            for c in node.children:
                row = QHBoxLayout()
                lbl = QLabel(f"  • {c.label}")
                lbl.setStyleSheet("color: #334155; font-size: 11px;")
                row.addWidget(lbl, 1)
                btn = QPushButton(tr("Ver"))
                btn.setMaximumWidth(50)
                btn.clicked.connect(lambda _=False, cid=c.id: self.selectNode.emit(cid))
                row.addWidget(btn)
                lay.addLayout(row)

        btn_wizard = QPushButton(f"⚡ {tr('Abrir Asistente Booleano...')}")
        btn_wizard.setStyleSheet("margin-top: 6px; font-weight: 500;")
        btn_wizard.clicked.connect(lambda: self.openBooleanWizard.emit(node.id))
        lay.addWidget(btn_wizard)

        self._lay.addWidget(box)

    def _param_row(self, node: Node, p: Param) -> None:
        present = p.name in node.params
        value = node.params.get(p.name, copy.deepcopy(p.default))
        head = QHBoxLayout()
        head.setSpacing(6)
        if p.optional:
            check = QCheckBox(tr(p.title))
            check.setObjectName("captionCheck")
            check.setChecked(present)
            check.toggled.connect(lambda on, p=p: self._toggle_optional(node, p, on))
            head.addWidget(check)
        else:
            head.addWidget(self._caption(tr(p.title)))
        head.addStretch(1)
        self._lay.addLayout(head)

        if p.optional and not present:
            return  # parámetro no usado: solo se muestra la casilla

        editor = self._editor(node, p, value)
        self._lay.addWidget(editor)

    def _toggle_optional(self, node: Node, p: Param, on: bool) -> None:
        self.changed.emit(node.id, p.name, copy.deepcopy(p.default) if on else None)
        self.refresh()

    def _extra_row(self, node: Node, key: str) -> None:
        head = QHBoxLayout()
        head.addWidget(self._caption(key))
        head.addStretch(1)
        remove = QToolButton()
        remove.setText(tr("Quitar"))
        remove.clicked.connect(lambda: (self.changed.emit(node.id, key, None), self.refresh()))
        head.addWidget(remove)
        self._lay.addLayout(head)
        self._lay.addWidget(self._expr_editor(node, key, node.params[key]))

    # ----------------------------------------------------------------- editores
    def _emit(self, node: Node, key: str, value: Any) -> None:
        self.changed.emit(node.id, key, value)

    def _guarded(self, w: QWidget) -> QWidget:
        w.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        w.installEventFilter(self._guard)
        return w

    def _num_spin(self, p: Param, value: float, integer: bool = False):
        spin = QSpinBox() if integer else QDoubleSpinBox()
        if integer:
            spin.setRange(int(max(p.minimum, -10 ** 9)), int(min(p.maximum, 10 ** 9)))
        else:
            spin.setDecimals(4)
            spin.setRange(max(p.minimum, -1e7), min(p.maximum, 1e7))
            spin.setSingleStep(p.step)
        spin.setKeyboardTracking(False)
        spin.setValue(int(value) if integer else float(value))
        return self._guarded(spin)

    def _editor(self, node: Node, p: Param, value: Any) -> QWidget:
        if not conforms(p, value):
            return self._expr_editor(node, p.name, value)
        k = p.kind
        if k in ("num", "int"):
            box = QWidget()
            row = QHBoxLayout(box)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            spin = self._num_spin(p, value, integer=(k == "int"))
            spin.valueChanged.connect(lambda v: self._emit(node, p.name, v))
            row.addWidget(spin, 1)

            vars_list = self.doc.get_variables() if self.doc is not None else []
            if vars_list:
                fx = QPushButton("ƒx")
                fx.setObjectName("fxButton")
                fx.setFixedWidth(28)
                fx.setToolTip(tr("Asignar variable global"))
                menu = QMenu(self)
                for v in vars_list:
                    a = menu.addAction(f"{v['name']}  (= {v['value']})")
                    a.triggered.connect(lambda _=False, n=v['name']: (self._emit(node, p.name, Expr(n)), self.refresh()))
                fx.setMenu(menu)
                row.addWidget(fx)
            return box
        if k == "bool":
            check = QCheckBox(tr("Sí"))
            check.setChecked(bool(value))
            check.toggled.connect(lambda on: self._emit(node, p.name, on))
            return check
        if k in ("vec2", "vec3"):
            return self._vector_editor(node, p, value)
        if k == "str":
            edit = QLineEdit(value)
            edit.editingFinished.connect(lambda: self._emit(node, p.name, edit.text()))
            return edit
        if k == "choice":
            combo = self._guarded(QComboBox())
            combo.addItems(list(p.options))
            combo.setCurrentText(value)
            combo.currentTextChanged.connect(lambda t: self._emit(node, p.name, t))
            return combo
        if k == "color":
            return self._color_editor(node, p, value)
        if k == "file":
            return self._file_editor(node, p, value)
        if k in ("points2", "points3", "faces", "matrix"):
            return self._table_button(node, p, value)
        return self._expr_editor(node, p.name, value)

    def _vector_editor(self, node: Node, p: Param, value: list) -> QWidget:
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        spins = []
        for i, axis in enumerate("XYZ"[:len(value)]):
            lab = QLabel(axis)
            lab.setObjectName("axis" + axis)
            spin = self._num_spin(p, value[i])
            spin.setRange(-1e7, 1e7)
            grid.addWidget(lab, 0, i * 2)
            grid.addWidget(spin, 0, i * 2 + 1)
            grid.setColumnStretch(i * 2 + 1, 1)
            spins.append(spin)
        for spin in spins:
            spin.valueChanged.connect(lambda _=None: self._emit(node, p.name, [s.value() for s in spins]))
        return box

    def _color_editor(self, node: Node, p: Param, value: str) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        combo = self._guarded(QComboBox())
        combo.setEditable(True)
        combo.addItems(COLOR_NAMES)
        combo.setCurrentText(value)
        swatch = QPushButton()
        swatch.setFixedSize(30, 28)
        swatch.setToolTip(tr("Elegir color…"))

        def paint(text):
            c = QColor(text)
            swatch.setStyleSheet(f"background:{c.name() if c.isValid() else '#ffffff'};"
                                 "border:1px solid #CBD1DA;border-radius:6px")

        def pick():
            c = QColorDialog.getColor(QColor(combo.currentText()), self, tr("Color"))
            if c.isValid():
                combo.setCurrentText(c.name())

        paint(value)
        combo.currentTextChanged.connect(paint)
        combo.currentTextChanged.connect(lambda t: self._emit(node, p.name, t) if QColor(t).isValid() else None)
        swatch.clicked.connect(pick)
        row.addWidget(combo, 1)
        row.addWidget(swatch)
        return box

    def _file_editor(self, node: Node, p: Param, value: str) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit(value)
        edit.setPlaceholderText("pieza.stl")
        button = QPushButton("…")
        button.setFixedWidth(34)

        def browse():
            path = choose_import_file(self, node.kind, self.base_dir)
            if path:
                edit.setText(path)
                self._emit(node, p.name, path)

        edit.editingFinished.connect(lambda: self._emit(node, p.name, edit.text()))
        button.clicked.connect(browse)
        row.addWidget(edit, 1)
        row.addWidget(button)
        return box

    def _table_button(self, node: Node, p: Param, value: list) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        names = {"points2": tr("puntos"), "points3": tr("vértices"), "faces": tr("caras"), "matrix": tr("filas")}
        summary = QLabel(f"{len(value)} {names[p.kind]}")
        summary.setObjectName("caption")
        button = QPushButton(tr("Editar…"))

        def open_editor():
            current = node.params.get(p.name, value)
            if p.kind == "points2":
                res = edit_points(self, tr("Puntos del polígono"), current, 2)
            elif p.kind == "points3":
                res = edit_points(self, tr("Vértices del poliedro"), current, 3)
            elif p.kind == "faces":
                res = edit_faces(self, current)
            else:
                res = edit_matrix(self, current if len(current) == 4 else current + [[0, 0, 0, 1]])
            if res is not None:
                self._emit(node, p.name, res)
                self.refresh()

        button.clicked.connect(open_editor)
        row.addWidget(summary, 1)
        row.addWidget(button)
        return box

    def _expr_editor(self, node: Node, key: str, value: Any) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        edit = QLineEdit(format_value(value))
        edit.setObjectName("exprEdit")
        edit.setToolTip(tr("Expresión OpenSCAD. Escribe un valor literal (10, [1, 2, 3], true, \"texto\") "
                           "para volver al editor normal."))

        def commit():
            new = literal(edit.text()) if edit.text().strip() else None
            if new is None:
                return
            old = node.params.get(key)
            if new != old:
                self._emit(node, key, new)
                if not isinstance(new, Expr):
                    self.refresh()

        edit.editingFinished.connect(commit)
        row.addWidget(edit, 1)

        vars_list = self.doc.get_variables() if self.doc is not None else []
        if vars_list:
            fx = QPushButton("ƒx")
            fx.setObjectName("fxButton")
            fx.setFixedWidth(28)
            fx.setToolTip(tr("Vincular con una variable global del proyecto"))
            menu = QMenu(self)
            for v in vars_list:
                a = menu.addAction(f"{v['name']}  (= {v['value']})")
                a.triggered.connect(lambda _=False, n=v['name']: (edit.setText(n), commit()))
            fx.setMenu(menu)
            row.addWidget(fx)

        return box


def choose_import_file(parent, kind: str, base_dir: str) -> str:
    if kind == "surface":
        filt = tr("Mapas de altura (*.png *.dat);;Todos (*)")
    else:
        filt = tr("Modelos y dibujos (*.stl *.off *.3mf *.amf *.obj *.svg *.dxf *.csg);;"
                  "Mallas 3D (*.stl *.off *.3mf *.amf *.obj);;Dibujos 2D (*.svg *.dxf);;Todos (*)")
    path, _ = QFileDialog.getOpenFileName(parent, tr("Elegir archivo"), base_dir or "", filt)
    if not path:
        return ""
    if base_dir:
        try:
            rel = os.path.relpath(path, base_dir)
            if not rel.startswith(".."):
                path = rel
        except ValueError:  # otra unidad en Windows
            pass
    return path.replace("\\", "/")
