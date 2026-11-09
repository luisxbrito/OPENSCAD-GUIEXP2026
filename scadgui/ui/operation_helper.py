"""Ventanas de ayuda de cada operación (los textos y ajustes rápidos están en ``operations.py``)."""

from __future__ import annotations

import html
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPlainTextEdit, QPushButton,
                               QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget)

from ..catalog import SPECS
from ..i18n import tr
from ..operations import OPERATION_HELPERS
from ..model import Document
from .icons import icon
from .style import themed


class OperationHelperWidget(QFrame):
    """Widget compacto que se inserta en el panel de propiedades con explicaciones y presets rápidos."""
    presetApplied = Signal(str, object)  # (param_name, new_value)
    openFullGuideRequested = Signal(str)  # kind

    def __init__(self, kind: str, current_params: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.kind = kind
        self.params = current_params
        self.setObjectName("operationHelperBox")
        self.setStyleSheet(
            themed("QFrame#operationHelperBox { background-color: #F8FAFC; border: 1px solid #CBD5E1; "
            "border-radius: 8px; padding: 10px; margin-top: 6px; }")
        )
        self._build_ui()

    def _build_ui(self) -> None:
        info = OPERATION_HELPERS.get(self.kind)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        if not info:
            # Helper genérico si no está en la lista detallada
            spec = SPECS.get(self.kind)
            label = tr(spec.label) if spec else self.kind
            lay.addWidget(QLabel(f"<b>{html.escape(label)}</b> <code>{self.kind}</code>"))
            if spec and spec.hint:
                lay.addWidget(QLabel(tr(spec.hint)))
            return

        # Encabezado
        head = QHBoxLayout()
        icon_w = QLabel()
        ico = icon(info.get("icon", self.kind), "#1E293B")
        if callable(getattr(ico, "pixmap", None)):
            icon_w.setPixmap(ico.pixmap(18, 18))
        title = QLabel(f"<b>{tr(info['title'])}</b>")
        title.setStyleSheet(themed("color: #0F172A; font-size: 12px;"))
        head.addWidget(icon_w)
        head.addWidget(title)
        head.addStretch(1)
        lay.addLayout(head)

        # Resumen conciso
        summary = QLabel(tr(info["summary"]))
        summary.setWordWrap(True)
        summary.setStyleSheet(themed("color: #475569; font-size: 11px;"))
        lay.addWidget(summary)

        # Pro-tip si existe
        if "pro_tip" in info:
            tip = QLabel(tr(info["pro_tip"]))
            tip.setWordWrap(True)
            tip.setStyleSheet(
                themed("background-color: #EFF6FF; border-left: 3px solid #3B82F6; color: #1E40AF; "
                "padding: 5px 8px; font-size: 10px; border-radius: 3px;")
            )
            lay.addWidget(tip)

        # Botones de presets / acciones rápidas si tiene
        presets = info.get("presets", [])
        if presets:
            lbl_actions = QLabel(f"<b>{tr('Acciones rápidas (1 clic)')}:</b>")
            lbl_actions.setStyleSheet(themed("color: #334155; font-size: 11px; margin-top: 4px;"))
            lay.addWidget(lbl_actions)

            grid = QGridLayout()
            grid.setSpacing(4)
            for idx, (btn_text, fn, param_key) in enumerate(presets):
                b = QPushButton(tr(btn_text))
                b.setStyleSheet(
                    themed("QPushButton { background: #FFFFFF; border: 1px solid #CBD5E1; "
                    "border-radius: 4px; padding: 4px 6px; font-size: 10px; color: #1E293B; } "
                    "QPushButton:hover { background: #F1F5F9; border-color: #94A3B8; }")
                )
                b.clicked.connect(lambda _=False, f=fn, k=param_key: self._on_preset_clicked(f, k))
                grid.addWidget(b, idx // 2, idx % 2)
            lay.addLayout(grid)

        # Botón para abrir la guía completa
        btn_guide = QPushButton(f"{tr('Ver guía completa y ejemplos…')}")
        btn_guide.setStyleSheet(
            themed("QPushButton { background: transparent; border: none; color: #2563EB; "
            "font-size: 11px; text-decoration: underline; text-align: left; padding: 2px 0px; margin-top: 4px; } "
            "QPushButton:hover { color: #1D4ED8; }")
        )
        btn_guide.clicked.connect(lambda: self.openFullGuideRequested.emit(self.kind))
        lay.addWidget(btn_guide)

    def _on_preset_clicked(self, fn: Callable[[dict], Any], param_key: str) -> None:
        new_val = fn(self.params)
        self.presetApplied.emit(param_key, new_val)


class OperationHelperDialog(QDialog):
    """Diálogo completo que actúa como centro de ayuda y documentación interactiva de todas las operaciones."""

    def __init__(self, current_kind: str = "translate", doc: Optional[Document] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle(tr("Guía y Helper de Operaciones OpenSCAD"))
        self.resize(880, 600)
        self.setMinimumSize(720, 480)
        self.current_kind = current_kind
        self._build_ui()

    def _build_ui(self) -> None:
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(14, 12, 14, 12)
        main_lay.setSpacing(10)

        # Barra superior con buscador
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        lbl_search = QLabel(f"{tr('Buscar operación')}:")
        lbl_search.setStyleSheet(themed("font-weight: 500;"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(tr("Ej: translate, rotate, difference, extrude..."))
        self.search_box.textChanged.connect(self._filter_list)
        top_bar.addWidget(lbl_search)
        top_bar.addWidget(self.search_box, 1)
        main_lay.addLayout(top_bar)

        # Splitter central: lista a la izquierda, detalles a la derecha
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet(themed("QSplitter::handle { background-color: #E2E8F0; width: 3px; } QSplitter::handle:hover { background-color: #3B82F6; }"))

        # Panel izquierdo: lista de operaciones
        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(220)
        self.list_widget.setMaximumWidth(340)
        self.list_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._populate_list()
        self.list_widget.currentItemChanged.connect(self._on_item_changed)
        splitter.addWidget(self.list_widget)

        # Panel derecho: scroll area con explicación detallada
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_widget = QWidget()
        self.detail_lay = QVBoxLayout(self.detail_widget)
        self.detail_lay.setContentsMargins(18, 12, 18, 12)
        self.detail_lay.setSpacing(12)
        scroll.setWidget(self.detail_widget)
        splitter.addWidget(scroll)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([270, 580])
        main_lay.addWidget(splitter, 1)

        # Botones inferiores
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.button(QDialogButtonBox.StandardButton.Close).setText(tr("Cerrar"))
        btn_box.rejected.connect(self.reject)
        main_lay.addWidget(btn_box)

        # Seleccionar el ítem inicial
        self._select_kind(self.current_kind)

    def _populate_list(self) -> None:
        self.list_widget.clear()
        for k, info in OPERATION_HELPERS.items():
            item = QListWidgetItem()
            item.setIcon(icon(info.get("icon", k), "#1E293B"))
            item.setText(f"{tr(info['title'])}  [{tr(info.get('category', ''))}]")
            item.setData(Qt.ItemDataRole.UserRole, k)
            self.list_widget.addItem(item)

    def _filter_list(self, text: str) -> None:
        q = text.lower().strip()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            k = item.data(Qt.ItemDataRole.UserRole)
            info = OPERATION_HELPERS.get(k, {})
            texts = (k, tr(info.get("title", "")), tr(info.get("summary", "")), tr(info.get("category", "")))
            visible = any(q in t.lower() for t in texts)
            item.setHidden(not visible)

    def _select_kind(self, kind: str) -> None:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == kind:
                self.list_widget.setCurrentItem(item)
                break

    def _on_item_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        if current is None:
            return
        kind = current.data(Qt.ItemDataRole.UserRole)
        self._show_details(kind)

    def _show_details(self, kind: str) -> None:
        # Limpiar layout
        while self.detail_lay.count():
            item = self.detail_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        info = OPERATION_HELPERS.get(kind, {})
        if not info:
            return

        # Título e icono
        head = QHBoxLayout()
        ic = QLabel()
        ico = icon(info.get("icon", kind), "#1E293B")
        if callable(getattr(ico, "pixmap", None)):
            ic.setPixmap(ico.pixmap(28, 28))
        t = QLabel(f"<h2>{tr(info['title'])}</h2>")
        head.addWidget(ic)
        head.addWidget(t)
        head.addStretch(1)
        self.detail_lay.addLayout(head)

        cat_badge = QLabel(f"<b>{tr('Categoría')}:</b> {tr(info.get('category', 'General'))}")
        cat_badge.setStyleSheet(themed("color: #64748B; font-size: 11px;"))
        self.detail_lay.addWidget(cat_badge)

        # Resumen
        sum_box = QLabel(tr(info.get("summary", "")))
        sum_box.setWordWrap(True)
        sum_box.setStyleSheet(themed("font-size: 13px; font-weight: 500; color: #1E293B;"))
        self.detail_lay.addWidget(sum_box)

        # ¿Cómo funciona?
        self.detail_lay.addWidget(QLabel(f"<h3>{tr('¿Cómo funciona?')}</h3>"))
        how = QLabel(tr(info.get("how_it_works", "")))
        how.setWordWrap(True)
        how.setStyleSheet(themed("line-height: 1.4; color: #334155;"))
        self.detail_lay.addWidget(how)

        # Pro-tip
        if "pro_tip" in info:
            tip = QLabel(tr(info["pro_tip"]))
            tip.setWordWrap(True)
            tip.setStyleSheet(
                themed("background-color: #FEF3C7; border-left: 4px solid #F59E0B; "
                "color: #92400E; padding: 8px 12px; font-size: 11px; border-radius: 4px;")
            )
            self.detail_lay.addWidget(tip)

        # Código de ejemplo
        if "example_code" in info:
            self.detail_lay.addWidget(QLabel(f"<h3>{tr('Ejemplo en OpenSCAD:')}</h3>"))
            code_view = QPlainTextEdit(info["example_code"])
            code_view.setReadOnly(True)
            code_view.setStyleSheet(themed(
                "font-family: monospace; font-size: 11px; background: #F1F5F9; "
                "border: 1px solid #CBD5E1; border-radius: 6px; padding: 6px;"
            ))
            lines = max(3, info["example_code"].count("\n") + 1)
            code_view.setFixedHeight(min(160, max(65, lines * 19 + 20)))
            self.detail_lay.addWidget(code_view)

        self.detail_lay.addStretch(1)
