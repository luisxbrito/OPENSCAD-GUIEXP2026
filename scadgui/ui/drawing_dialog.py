"""Diálogo de configuración para planos técnicos 2D."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QRadioButton, QVBoxLayout,
                               QWidget)

from ..i18n import tr


class DrawingDialog(QDialog):
    """Diálogo para configurar vistas, escala y cajetín para un plano técnico 2D."""

    def __init__(self, has_selection: bool = False, default_title: str = "Plano Técnico",
                 default_author: str = "", default_sheet: str = "A4", parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Generar plano técnico 2D"))
        self.resize(460, 520)

        self.action = "export"  # "export", "insert", "cancel"

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. Alcance / Objeto del plano
        scope_group = QGroupBox(tr("Alcance del plano"))
        scope_lay = QVBoxLayout(scope_group)
        self.rb_selected = QRadioButton(tr("Solo las piezas seleccionadas"))
        self.rb_all = QRadioButton(tr("Todo el modelo"))
        if has_selection:
            self.rb_selected.setChecked(True)
        else:
            self.rb_selected.setEnabled(False)
            self.rb_all.setChecked(True)
        scope_lay.addWidget(self.rb_selected)
        scope_lay.addWidget(self.rb_all)
        layout.addWidget(scope_group)

        # 2. Metadatos del plano
        meta_group = QGroupBox(tr("Datos del cajetín y formato"))
        meta_lay = QFormLayout(meta_group)
        self.title_edit = QLineEdit(default_title)
        self.author_edit = QLineEdit(default_author or "Diseñador CAD")
        self.sheet_combo = QComboBox()
        self.sheet_combo.addItem("A4 Horizontal (297 × 210 mm)", "A4")
        self.sheet_combo.addItem("A3 Horizontal (420 × 297 mm)", "A3")
        idx_sh = self.sheet_combo.findData(default_sheet)
        if idx_sh >= 0:
            self.sheet_combo.setCurrentIndex(idx_sh)
        self.scale_combo = QComboBox()
        for label, val in (("1:1 (Real)", 1.0), ("1:2 (Reducción 50%)", 0.5),
                           ("1:5 (Reducción 20%)", 0.2), ("2:1 (Ampliación 2x)", 2.0)):
            self.scale_combo.addItem(label, val)
        meta_lay.addRow(tr("Título del plano:"), self.title_edit)
        meta_lay.addRow(tr("Diseñador:"), self.author_edit)
        meta_lay.addRow(tr("Tamaño de hoja:"), self.sheet_combo)
        meta_lay.addRow(tr("Escala:"), self.scale_combo)
        layout.addWidget(meta_group)

        # 3. Vistas a incluir
        views_group = QGroupBox(tr("Vistas ortogonales y proyecciones"))
        views_lay = QVBoxLayout(views_group)
        self.chk_top = QCheckBox(tr("Planta (Vista superior XY)"))
        self.chk_top.setChecked(True)
        self.chk_front = QCheckBox(tr("Alzado (Vista frontal XZ)"))
        self.chk_front.setChecked(True)
        self.chk_side = QCheckBox(tr("Perfil (Vista lateral YZ)"))
        self.chk_side.setChecked(True)
        self.chk_iso = QCheckBox(tr("Isométrica 3D"))
        self.chk_iso.setChecked(True)
        self.chk_border = QCheckBox(tr("Incluir marco perimetral y cajetín técnico"))
        self.chk_border.setChecked(True)

        views_lay.addWidget(self.chk_front)
        views_lay.addWidget(self.chk_top)
        views_lay.addWidget(self.chk_side)
        views_lay.addWidget(self.chk_iso)
        views_lay.addWidget(self.chk_border)
        layout.addWidget(views_group)

        # 4. Botones de acción
        btn_box = QHBoxLayout()
        self.btn_export = QPushButton(tr("Exportar archivo…"))
        self.btn_export.setObjectName("primary")
        self.btn_export.setToolTip("Exporta la lámina técnica directamente a SVG, DXF o PDF")
        self.btn_export.clicked.connect(self._on_export)

        self.btn_insert = QPushButton(tr("Insertar en modelo"))
        self.btn_insert.setToolTip("Inserta las proyecciones 2D en el modelo actual")
        self.btn_insert.clicked.connect(self._on_insert)

        self.btn_cancel = QPushButton(tr("Cancelar"))
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addWidget(self.btn_cancel)
        btn_box.addStretch(1)
        btn_box.addWidget(self.btn_insert)
        btn_box.addWidget(self.btn_export)
        layout.addLayout(btn_box)

    def _on_export(self) -> None:
        self.action = "export"
        self.accept()

    def _on_insert(self) -> None:
        self.action = "insert"
        self.accept()

    def get_config(self) -> dict:
        scale_val = float(self.scale_combo.currentData() or 1.0)
        sheet_key = str(self.sheet_combo.currentData() or "A4")
        return {
            "action": self.action,
            "use_selection": bool(self.rb_selected.isChecked()),
            "title": str(self.title_edit.text() or "").strip() or "Plano Técnico",
            "author": str(self.author_edit.text() or "").strip(),
            "sheet_size": sheet_key,
            "scale": scale_val,
            "include_border": bool(self.chk_border.isChecked()),
            "views": {
                "front": bool(self.chk_front.isChecked()),
                "top": bool(self.chk_top.isChecked()),
                "side": bool(self.chk_side.isChecked()),
                "isometric": bool(self.chk_iso.isChecked()),
            },
        }
