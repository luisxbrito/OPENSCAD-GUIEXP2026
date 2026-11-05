"""Diálogo de configuración para planos técnicos 2D."""

from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QPlainTextEdit, QPushButton, QRadioButton, QVBoxLayout)

from ..drawing_sheet import MATERIALS
from ..i18n import tr

SCALES = (("1:1", 1.0), ("1:2", 0.5), ("1:5", 0.2), ("1:10", 0.1), ("1:20", 0.05), ("2:1", 2.0), ("5:1", 5.0))
TOLERANCES = ("ISO 2768-f", "ISO 2768-m", "ISO 2768-c", "ISO 2768-mK")


class DrawingDialog(QDialog):
    """Datos del cajetín, vistas, escala y opciones del plano técnico 2D."""

    def __init__(self, has_selection: bool = False, default_title: str = "",
                 default_author: str = "", default_sheet: str = "A4", parent=None, defaults: dict = None):
        super().__init__(parent)
        d = defaults or {}
        self.setWindowTitle(tr("Generar plano técnico 2D"))
        self.action = "export"  # "export", "insert"

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        columns = QHBoxLayout()
        layout.addLayout(columns)
        left, right = QVBoxLayout(), QVBoxLayout()
        columns.addLayout(left, 3)
        columns.addLayout(right, 2)

        # Cajetín
        meta_group = QGroupBox(tr("Datos del cajetín"))
        meta = QFormLayout(meta_group)
        self.title_edit = QLineEdit(default_title or tr("Plano técnico"))
        self.desc_edit = QLineEdit(d.get("description", ""))
        self.desc_edit.setPlaceholderText(tr("Una línea bajo el título (opcional)"))
        self.company_edit = QLineEdit(d.get("company", ""))
        self.number_edit = QLineEdit(d.get("number", ""))
        self.number_edit.setPlaceholderText(tr("p. ej. PZ-001"))
        self.revision_edit = QLineEdit(d.get("revision", "A"))
        self.revision_edit.setMaximumWidth(60)
        self.material_combo = QComboBox()
        self.material_combo.setEditable(True)
        self.material_combo.addItem(tr("Sin especificar"), None)
        for name, density in MATERIALS:
            self.material_combo.addItem(tr(name), density)
        material = d.get("material", "")
        if material:
            idx = self.material_combo.findText(material)
            if idx >= 0:
                self.material_combo.setCurrentIndex(idx)
            else:
                self.material_combo.setEditText(material)
        self.author_edit = QLineEdit(default_author or "")
        self.checker_edit = QLineEdit(d.get("checker", ""))
        self.tolerance_combo = QComboBox()
        self.tolerance_combo.setEditable(True)
        self.tolerance_combo.addItems(TOLERANCES)
        self.tolerance_combo.setCurrentText(d.get("tolerance", "ISO 2768-m"))
        number_row = QHBoxLayout()
        number_row.addWidget(self.number_edit, 1)
        number_row.addWidget(QLabel(tr("Rev.")))
        number_row.addWidget(self.revision_edit)
        meta.addRow(tr("Título del plano:"), self.title_edit)
        meta.addRow(tr("Descripción:"), self.desc_edit)
        meta.addRow(tr("Empresa:"), self.company_edit)
        meta.addRow(tr("Nº de plano:"), number_row)
        meta.addRow(tr("Material:"), self.material_combo)
        meta.addRow(tr("Diseñador:"), self.author_edit)
        meta.addRow(tr("Revisado por:"), self.checker_edit)
        meta.addRow(tr("Tolerancias generales:"), self.tolerance_combo)
        left.addWidget(meta_group)

        notes_group = QGroupBox(tr("Notas (una por línea)"))
        notes_lay = QVBoxLayout(notes_group)
        self.notes_edit = QPlainTextEdit(d.get("notes", tr("Cotas en milímetros.")))
        self.notes_edit.setFixedHeight(70)
        notes_lay.addWidget(self.notes_edit)
        left.addWidget(notes_group)

        # Alcance
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
        right.addWidget(scope_group)

        # Formato
        sheet_group = QGroupBox(tr("Formato"))
        sheet_lay = QFormLayout(sheet_group)
        self.sheet_combo = QComboBox()
        self.sheet_combo.addItem(tr("A4 Horizontal (297 × 210 mm)"), "A4")
        self.sheet_combo.addItem(tr("A3 Horizontal (420 × 297 mm)"), "A3")
        idx_sh = self.sheet_combo.findData(default_sheet)
        if idx_sh >= 0:
            self.sheet_combo.setCurrentIndex(idx_sh)
        self.scale_combo = QComboBox()
        self.scale_combo.addItem(tr("Automática (la mayor que cabe)"), 0.0)
        for label, val in SCALES:
            self.scale_combo.addItem(label, val)
        sheet_lay.addRow(tr("Tamaño de hoja:"), self.sheet_combo)
        sheet_lay.addRow(tr("Escala:"), self.scale_combo)
        right.addWidget(sheet_group)

        # Vistas y opciones
        views_group = QGroupBox(tr("Vistas y opciones"))
        views_lay = QGridLayout(views_group)
        self.chk_front = QCheckBox(tr("Alzado"))
        self.chk_top = QCheckBox(tr("Planta"))
        self.chk_side = QCheckBox(tr("Perfil izquierdo"))
        self.chk_iso = QCheckBox(tr("Isométrica"))
        for i, chk in enumerate((self.chk_front, self.chk_top, self.chk_side, self.chk_iso)):
            chk.setChecked(True)
            views_lay.addWidget(chk, i // 2, i % 2)
        self.chk_hidden = QCheckBox(tr("Líneas ocultas (discontinuas)"))
        self.chk_hidden.setChecked(bool(d.get("hidden", True)))
        self.chk_dims = QCheckBox(tr("Cotas generales"))
        self.chk_dims.setChecked(bool(d.get("dims", True)))
        self.chk_border = QCheckBox(tr("Incluir marco perimetral y cajetín técnico"))
        self.chk_border.setChecked(True)
        self.chk_border.setToolTip(tr("Solo para «Insertar en modelo»: el archivo exportado siempre lleva "
                                      "marco y cajetín"))
        views_lay.addWidget(self.chk_hidden, 2, 0, 1, 2)
        views_lay.addWidget(self.chk_dims, 3, 0, 1, 2)
        views_lay.addWidget(self.chk_border, 4, 0, 1, 2)
        right.addWidget(views_group)
        right.addStretch(1)

        # Botones
        btn_box = QHBoxLayout()
        self.btn_export = QPushButton(tr("Exportar archivo…"))
        self.btn_export.setObjectName("primary")
        self.btn_export.setToolTip(tr("Exporta la lámina con las aristas de la pieza a SVG, DXF o PDF"))
        self.btn_export.clicked.connect(self._on_export)
        self.btn_insert = QPushButton(tr("Insertar en modelo"))
        self.btn_insert.setToolTip(tr("Inserta las proyecciones 2D en el modelo actual (solo siluetas)"))
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

    def material(self) -> tuple[str, object]:
        """(nombre, densidad en g/cm³ o None). Un material escrito a mano no tiene densidad."""
        text = self.material_combo.currentText().strip()
        idx = self.material_combo.findText(text)
        if idx == 0 or not text:
            return "", None
        return text, (self.material_combo.itemData(idx) if idx > 0 else None)

    def get_config(self) -> dict:
        material, density = self.material()
        return {
            "action": self.action,
            "use_selection": bool(self.rb_selected.isChecked()),
            "title": str(self.title_edit.text() or "").strip() or tr("Plano técnico"),
            "description": self.desc_edit.text().strip(),
            "company": self.company_edit.text().strip(),
            "number": self.number_edit.text().strip(),
            "revision": self.revision_edit.text().strip(),
            "material": material,
            "density": density,
            "author": str(self.author_edit.text() or "").strip(),
            "checker": self.checker_edit.text().strip(),
            "tolerance": self.tolerance_combo.currentText().strip(),
            "notes": [n.strip() for n in self.notes_edit.toPlainText().splitlines() if n.strip()],
            "sheet_size": str(self.sheet_combo.currentData() or "A4"),
            "scale": float(self.scale_combo.currentData() or 0.0),
            "include_border": bool(self.chk_border.isChecked()),
            "hidden": bool(self.chk_hidden.isChecked()),
            "dims": bool(self.chk_dims.isChecked()),
            "views": {
                "front": bool(self.chk_front.isChecked()),
                "top": bool(self.chk_top.isChecked()),
                "side": bool(self.chk_side.isChecked()),
                "isometric": bool(self.chk_iso.isChecked()),
            },
        }
