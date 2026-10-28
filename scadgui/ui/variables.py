"""Panel de variables y parámetros globales del proyecto."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ..i18n import tr
from ..model import Document


class VariablesPanel(QWidget):
    """Tabla editable de variables globales del documento."""

    variableChanged = Signal(str, str, str)  # (name, value, comment)
    variableAdded = Signal(str, str, str)
    variableDeleted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("variablesPanel")
        self._doc: Document | None = None
        self._updating = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        t = QLabel(tr("PARÁMETROS GLOBALES"))
        t.setObjectName("sectionTitle")
        toolbar.addWidget(t)
        toolbar.addStretch(1)

        self.btn_add = QPushButton(tr("+ Variable"))
        self.btn_add.setToolTip("Añadir una nueva variable global al proyecto")
        self.btn_add.clicked.connect(self._add_variable)
        toolbar.addWidget(self.btn_add)

        self.btn_del = QPushButton(tr("− Eliminar"))
        self.btn_del.setToolTip("Eliminar la variable seleccionada")
        self.btn_del.clicked.connect(self._delete_variable)
        toolbar.addWidget(self.btn_del)

        lay.addLayout(toolbar)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([tr("Nombre"), tr("Valor"), tr("Descripción")])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(1, 90)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.cellChanged.connect(self._on_cell_changed)
        lay.addWidget(self.table)

    def update_doc(self, doc: Document) -> None:
        self._doc = doc
        self.refresh()

    def refresh(self) -> None:
        if self._doc is None:
            return
        self._updating = True
        self.table.setRowCount(0)
        vars_list = self._doc.get_variables()
        self.table.setRowCount(len(vars_list))

        for row, v in enumerate(vars_list):
            item_name = QTableWidgetItem(v["name"])
            item_val = QTableWidgetItem(v["value"])
            item_comm = QTableWidgetItem(v["comment"])

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_val)
            self.table.setItem(row, 2, item_comm)

        self._updating = False

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._updating or self._doc is None:
            return
        item_name = self.table.item(row, 0)
        item_val = self.table.item(row, 1)
        item_comm = self.table.item(row, 2)
        if not item_name or not item_val:
            return

        name = item_name.text().strip()
        val = item_val.text().strip()
        comm = item_comm.text().strip() if item_comm else ""
        if name and val:
            self.variableChanged.emit(name, val, comm)

    def _add_variable(self) -> None:
        if self._doc is None:
            return
        existing = {v["name"] for v in self._doc.get_variables()}
        idx = 1
        name = f"var_{idx}"
        while name in existing:
            idx += 1
            name = f"var_{idx}"

        self.variableAdded.emit(name, "10", "Parámetro")

    def _delete_variable(self) -> None:
        if self._doc is None:
            return
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item:
            name = item.text().strip()
            self.variableDeleted.emit(name)
