"""Diálogos para los parámetros que no caben en un campo: listas de puntos, caras y matrices."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..i18n import tr
from ..model import format_number


class TableDialog(QDialog):
    """Edita una lista de filas numéricas.

    ``columns`` fija el número de columnas (3 para puntos 3D, 4 para la matriz).
    Si ``columns`` es None, cada fila puede tener cualquier cantidad de valores
    (caras de un poliedro) y se escribe como texto "0, 1, 4".
    """

    def __init__(self, title: str, rows: list, headers: list[str] | None, columns: int | None,
                 fixed_rows: bool = False, integer: bool = False, help_text: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(460, 420)
        self.columns = columns
        self.integer = integer
        self.result_rows: list = rows

        layout = QVBoxLayout(self)
        if help_text:
            hint = QLabel(help_text)
            hint.setWordWrap(True)
            hint.setObjectName("hint")
            layout.addWidget(hint)

        ncols = columns or 1
        self.table = QTableWidget(len(rows), ncols)
        self.table.setHorizontalHeaderLabels(headers or [tr("Índices de vértices (separados por comas)")])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(26)
        for r, row in enumerate(rows):
            if columns:
                for c in range(columns):
                    value = row[c] if c < len(row) else 0
                    self.table.setItem(r, c, QTableWidgetItem(format_number(value)))
            else:
                self.table.setItem(r, 0, QTableWidgetItem(", ".join(format_number(v) for v in row)))
        if columns:
            for c in range(columns):
                self.table.setColumnWidth(c, 90)
        layout.addWidget(self.table)

        if not fixed_rows:
            row_buttons = QHBoxLayout()
            add = QPushButton(tr("Añadir fila"))
            add.clicked.connect(self._add_row)
            remove = QPushButton(tr("Quitar fila"))
            remove.clicked.connect(self._remove_row)
            row_buttons.addWidget(add)
            row_buttons.addWidget(remove)
            row_buttons.addStretch(1)
            layout.addLayout(row_buttons)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_row(self) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c in range(self.table.columnCount()):
            self.table.setItem(r, c, QTableWidgetItem("0" if self.columns else ""))
        self.table.setCurrentCell(r, 0)

    def _remove_row(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows and self.table.rowCount():
            rows = [self.table.rowCount() - 1]
        for r in rows:
            self.table.removeRow(r)

    def _num(self, text: str):
        text = text.strip().replace(",", ".") if self.columns else text.strip()
        value = float(text)
        if self.integer or value.is_integer():
            return int(value)
        return value

    def _accept(self) -> None:
        rows = []
        try:
            for r in range(self.table.rowCount()):
                if self.columns:
                    rows.append([self._num((self.table.item(r, c) or QTableWidgetItem("0")).text() or "0")
                                 for c in range(self.columns)])
                else:
                    text = (self.table.item(r, 0) or QTableWidgetItem("")).text()
                    values = [self._num(v) for v in text.replace(";", ",").split(",") if v.strip()]
                    if len(values) < 3:
                        raise ValueError(f"La cara {r + 1} necesita al menos 3 vértices")
                    rows.append(values)
        except ValueError as exc:
            QMessageBox.warning(self, tr("Valor no válido"), f"{tr('Revisa la fila')} {r + 1}.\n\n{exc}")
            return
        self.result_rows = rows
        self.accept()


def edit_points(parent, title: str, rows: list, dims: int):
    headers = ["X", "Y", "Z"][:dims]
    dlg = TableDialog(title, rows, headers, dims, parent=parent,
                      help_text=tr("Cada fila es un vértice. Su número de fila (empezando en 0) "
                                   "es el índice que usan las caras."))
    return dlg.result_rows if dlg.exec() == QDialog.DialogCode.Accepted else None


def edit_faces(parent, rows: list):
    dlg = TableDialog(tr("Caras del poliedro"), rows, None, None, integer=True, parent=parent,
                      help_text=tr("Cada fila es una cara: índices de vértices en sentido horario "
                                   "mirando la cara desde fuera, p. ej. 0, 1, 4."))
    return dlg.result_rows if dlg.exec() == QDialog.DialogCode.Accepted else None


def edit_matrix(parent, rows: list):
    dlg = TableDialog(tr("Matriz de transformación 4×4"), rows, ["c1", "c2", "c3", tr("c4 (traslación)")], 4,
                      fixed_rows=True, parent=parent,
                      help_text=tr("Las tres primeras columnas giran/escalan/inclinan; la cuarta mueve. "
                                   "La última fila suele ser 0, 0, 0, 1."))
    return dlg.result_rows if dlg.exec() == QDialog.DialogCode.Accepted else None
