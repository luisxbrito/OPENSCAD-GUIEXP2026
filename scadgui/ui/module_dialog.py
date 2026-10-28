"""Diálogo para convertir una selección en un módulo de usuario de OpenSCAD."""

from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QScrollArea, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..i18n import tr
from ..model import format_value


class ModuleDialog(QDialog):
    """Diálogo interactivo para nombrar el módulo y elegir qué parámetros exponer."""

    def __init__(self, candidates: list[dict], default_name: str = "mi_modulo", parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Convertir selección en módulo"))
        self.resize(560, 480)
        self.candidates = candidates

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. Nombre del módulo
        top_group = QGroupBox(tr("Definición del módulo"))
        top_lay = QFormLayout(top_group)
        self.name_edit = QLineEdit(default_name)
        self.name_edit.setPlaceholderText("nombre_del_modulo")
        top_lay.addRow(tr("Nombre del módulo:"), self.name_edit)
        layout.addWidget(top_group)

        # 2. Explicación
        hint = QLabel(
            tr("Selecciona los parámetros que deseas convertir en argumentos configurables del módulo. "
               "Las piezas seleccionadas se reemplazarán en el modelo por la llamada a este módulo.")
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #5A6474; font-size: 11px;")
        layout.addWidget(hint)

        # 3. Tabla de parámetros candidatos
        table_group = QGroupBox(f"{tr('Parámetros detectados')} ({len(candidates)})")
        table_lay = QVBoxLayout(table_group)

        self.table = QTableWidget(len(candidates), 4)
        self.table.setHorizontalHeaderLabels([tr("Incluir"), tr("Nombre de argumento"), tr("Valor por defecto"), tr("Pieza")])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self.checkboxes: list[QCheckBox] = []
        self.var_edits: list[QLineEdit] = []

        for row, c in enumerate(candidates):
            # Columna 0: Checkbox
            chk = QCheckBox()
            chk.setChecked(c.get("enabled", True))
            chk_widget = QWidget()
            chk_lay = QHBoxLayout(chk_widget)
            chk_lay.addWidget(chk)
            chk_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_lay.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, chk_widget)
            self.checkboxes.append(chk)

            # Columna 1: Nombre de variable editable
            var_edit = QLineEdit(c.get("suggested_name", ""))
            self.table.setCellWidget(row, 1, var_edit)
            self.var_edits.append(var_edit)

            # Columna 2: Valor actual
            val_str = format_value(c.get("current_value"))
            item_val = QTableWidgetItem(val_str)
            item_val.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 2, item_val)

            # Columna 3: Pieza y propiedad
            node_info = f"{c.get('node_name')} · {c.get('param_key')}"
            item_node = QTableWidgetItem(node_info)
            item_node.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 3, item_node)

        table_lay.addWidget(self.table)
        layout.addWidget(table_group)

        # 4. Botones
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _on_accept(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.setText("mi_modulo")
        self.accept()

    def get_result(self) -> tuple[str, list[dict]]:
        """Devuelve (nombre_del_modulo, lista_de_bindings)."""
        text = self.name_edit.text() if hasattr(self.name_edit, "text") else ""
        mod_name = text.strip() if isinstance(text, str) else ""
        mod_name = mod_name or "mi_modulo"
        bindings = []
        for i, c in enumerate(self.candidates):
            chk = self.checkboxes[i] if i < len(self.checkboxes) else None
            is_enabled = chk.isChecked() if chk is not None and hasattr(chk, "isChecked") else True
            if not isinstance(is_enabled, bool):
                is_enabled = True
            v_edit = self.var_edits[i] if i < len(self.var_edits) else None
            var_text = v_edit.text() if v_edit is not None and hasattr(v_edit, "text") else ""
            var_name = var_text.strip() if isinstance(var_text, str) else ""
            var_name = var_name or c.get("suggested_name", "param")
            bindings.append({
                "node_id": c["node_id"],
                "param_key": c["param_key"],
                "var_name": var_name,
                "default_value": c["current_value"],
                "enabled": is_enabled,
            })
        return mod_name, bindings
