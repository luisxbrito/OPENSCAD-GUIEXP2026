"""Diálogo de selección e inserción de componentes estándar industriales."""

from __future__ import annotations

import html


from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QPushButton, QRadioButton, QVBoxLayout)

from ..hardware import BEARINGS_ISO, STANDARD_LENGTHS, available_sizes, describe
from ..i18n import tr
from .style import themed

GROOVES = ("ring_groove", "oring_groove")   # solo existen como máscara de resta

CATEGORIES = [
    ("screw_allen", "Tornillo Allen cilíndrico (ISO 4762 / DIN 912)", "screw", "iso4762"),
    ("screw_hex", "Tornillo Cabeza Hexagonal (DIN 933 / ISO 4017)", "screw", "din933"),
    ("screw_csk", "Tornillo Avellanado 90° (DIN 7991)", "screw", "iso10642"),
    ("screw_btn", "Tornillo Cabeza Botón (ISO 7380)", "screw", "iso7380"),
    ("nut_hex", "Tuerca Hexagonal Estándar (DIN 934 / ISO 4032)", "nut", "din934"),
    ("nut_lock", "Tuerca Autoblocante (DIN 985)", "nut", "din985"),
    ("heat_set", "Inserto Roscado de Latón (Impresión 3D FDM)", "insert", "heat_set"),
    ("washer", "Arandela Plana (DIN 125 / ISO 7089)", "washer", "din125"),
    ("bearing", "Rodamiento Radial de Bolas (ISO 15 / DIN 625)", "bearing", "bearing"),
    ("profile", "Perfil de Aluminio 2020 / 2040", "profile", "profile"),
    ("ring_shaft", "Ranura de anillo de retención en eje (3AM1, ANSI B27.7)", "ring_groove", "3am1"),
    ("ring_bore", "Ranura de anillo de retención en agujero (3BM1, ANSI B27.7)", "ring_groove", "3bm1"),
    ("oring_shaft", "Ranura de o-ring en eje o pistón", "oring_groove", "shaft"),
    ("oring_bore", "Ranura de o-ring en agujero", "oring_groove", "bore"),
    ("oring_face", "Ranura de o-ring en cara plana", "oring_groove", "face"),
]


class HardwareDialog(QDialog):
    """Diálogo para configurar e insertar componentes mecánicos normalizados."""

    def __init__(self, has_selection: bool = False, default_metric: str = "M3",
                 default_fit: str = "medium", parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Insertar componente estándar industrial"))
        self.resize(500, 520)
        self.has_selection = has_selection
        self.default_metric = default_metric
        self.default_fit = default_fit

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. Tipo de componente
        type_group = QGroupBox(tr("Tipo de componente normalizado"))
        type_lay = QVBoxLayout(type_group)
        self.combo_type = QComboBox()
        for _key, label, cat, std in CATEGORIES:
            self.combo_type.addItem(tr(label), (cat, std))
        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        type_lay.addWidget(self.combo_type)
        layout.addWidget(type_group)

        # 2. Parámetros del componente
        dim_group = QGroupBox(tr("Dimensiones y métrica"))
        dim_lay = QFormLayout(dim_group)

        self.combo_size = QComboBox()
        self.combo_size.currentIndexChanged.connect(self._update_info)
        dim_lay.addRow(tr("Métrica / Modelo:"), self.combo_size)

        self.combo_len = QComboBox()
        for length in STANDARD_LENGTHS:
            self.combo_len.addItem(f"{int(length)} mm", length)
        self.combo_len.setCurrentIndex(5)  # 16 mm por defecto
        self.combo_len.currentIndexChanged.connect(self._update_info)
        self.label_len = QLabel(tr("Longitud del vástago (L):"))
        dim_lay.addRow(self.label_len, self.combo_len)

        self.spin_diameter = QDoubleSpinBox()
        self.spin_diameter.setRange(0.5, 2000.0)
        self.spin_diameter.setDecimals(2)
        self.spin_diameter.setValue(20.0)
        self.spin_diameter.setSuffix(" mm")
        self.spin_diameter.valueChanged.connect(self._update_info)
        self.label_diameter = QLabel()
        dim_lay.addRow(self.label_diameter, self.spin_diameter)

        self.combo_seal = QComboBox()
        self.combo_seal.addItem(tr("Estática (sin movimiento)"), "static")
        self.combo_seal.addItem(tr("Con movimiento alternativo"), "moving")
        self.combo_seal.currentIndexChanged.connect(self._update_info)
        self.label_seal = QLabel(tr("Tipo de junta:"))
        dim_lay.addRow(self.label_seal, self.combo_seal)

        layout.addWidget(dim_group)

        # 3. Modo de inserción: Sólido vs Taladro/Cajeado
        mode_group = QGroupBox(tr("Modo de inserción"))
        mode_lay = QVBoxLayout(mode_group)
        self.rb_solid = QRadioButton(tr("Componente sólido (físico / ensamblaje)"))
        self.rb_hole = QRadioButton(tr("Taladro de paso / Cajeado de resta (Máscara negativa)"))
        self.rb_solid.setChecked(True)
        self.rb_solid.toggled.connect(self._on_mode_toggled)
        mode_lay.addWidget(self.rb_solid)
        mode_lay.addWidget(self.rb_hole)

        fit_row = QHBoxLayout()
        fit_lbl = QLabel(tr("Tolerancia / Ajuste (ISO 273):"))
        self.combo_fit = QComboBox()
        self.combo_fit.addItem(tr("Media / FDM 3D (+0.4 mm paso)"), "medium")
        self.combo_fit.addItem(tr("Fina / Mecanizado (+0.2 mm paso)"), "fine")
        self.combo_fit.addItem(tr("Gruesa / Holgada (+0.6 mm paso)"), "coarse")
        idx_fit = self.combo_fit.findData(self.default_fit)
        if idx_fit >= 0:
            self.combo_fit.setCurrentIndex(idx_fit)
        self.combo_fit.setEnabled(False)
        self.combo_fit.currentIndexChanged.connect(self._update_info)
        fit_row.addWidget(fit_lbl)
        fit_row.addWidget(self.combo_fit)
        mode_lay.addLayout(fit_row)

        self.chk_subtract = QCheckBox(tr("Restar automáticamente de la pieza seleccionada (difference)"))
        self.chk_subtract.setEnabled(False)
        mode_lay.addWidget(self.chk_subtract)

        layout.addWidget(mode_group)

        # 4. Ficha técnica en vivo
        info_group = QGroupBox(tr("Ficha técnica y cotas normalizadas"))
        info_lay = QVBoxLayout(info_group)
        self.lbl_info = QLabel()
        self.lbl_info.setStyleSheet(themed("color: #3D4756; font-size: 11px;"))
        self.lbl_info.setWordWrap(True)
        info_lay.addWidget(self.lbl_info)
        layout.addWidget(info_group)

        # 5. Botones de acción
        btn_box = QHBoxLayout()
        self.btn_insert = QPushButton(tr("Insertar componente"))
        self.btn_insert.setObjectName("primary")
        self.btn_insert.clicked.connect(self.accept)

        self.btn_cancel = QPushButton(tr("Cancelar"))
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addStretch(1)
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_insert)
        layout.addLayout(btn_box)

        # Inicialización
        self._on_type_changed(0)

    def _on_type_changed(self, idx: int) -> None:
        cat, std = self.combo_type.currentData() or ("screw", "iso4762")
        self.combo_size.blockSignals(True)
        self.combo_size.clear()

        if cat in ("screw", "nut", "washer", "insert"):
            # Solo las métricas que existen en la tabla de esta norma (p. ej. ISO 7380 empieza en M3).
            for size in available_sizes(cat, std):
                self.combo_size.addItem(size, size)
            # Seleccionar métrica por defecto
            m_idx = self.combo_size.findData(self.default_metric)
            if m_idx >= 0:
                self.combo_size.setCurrentIndex(m_idx)
        elif cat == "bearing":
            for b_id, b_info in BEARINGS_ISO.items():
                self.combo_size.addItem(f"{b_id} (Ø{b_info['d']}xØ{b_info['D']}x{b_info['B']} mm)", b_id)
        elif cat == "profile":
            self.combo_size.addItem(tr("Perfil 2020 (20×20 mm)"), "2020")
            self.combo_size.addItem(tr("Perfil 2040 (20×40 mm)"), "2040")
        elif cat == "ring_groove":
            for size in available_sizes(cat, std):
                self.combo_size.addItem(f"Ø{size} mm", size)
            self.combo_size.setCurrentIndex(max(0, self.combo_size.findData("20")))
        elif cat == "oring_groove":
            for size in available_sizes(cat, std):
                self.combo_size.addItem(f"{size} mm", size)
            self.combo_size.setCurrentIndex(max(0, self.combo_size.findData("2.62")))

        self.combo_size.blockSignals(False)

        # Longitud sólo relevante para tornillos y perfiles
        is_length_applicable = cat in ("screw", "profile")
        self.label_len.setVisible(is_length_applicable)
        self.combo_len.setVisible(is_length_applicable)
        if cat == "profile":
            self.label_len.setText(tr("Longitud del perfil:"))
        else:
            self.label_len.setText(tr("Longitud del vástago (L):"))

        is_oring = cat == "oring_groove"
        self.label_diameter.setVisible(is_oring)
        self.spin_diameter.setVisible(is_oring)
        self.label_diameter.setText({"shaft": tr("Ø del agujero contra el que sella:"),
                                     "bore": tr("Ø del eje contra el que sella:")}.get(
                                         std, tr("Ø exterior de la ranura:")))
        self.label_seal.setVisible(is_oring and std != "face")
        self.combo_seal.setVisible(is_oring and std != "face")

        # El modo negativo solo aplica a tornillos, tuercas, insertos y rodamientos; las ranuras
        # no tienen otro.
        can_hole = cat in ("screw", "nut", "insert", "bearing") or cat in GROOVES
        self.rb_hole.setEnabled(can_hole)
        self.rb_solid.setEnabled(cat not in GROOVES)
        if cat in GROOVES:
            self.rb_hole.setChecked(True)
        elif not can_hole and self.rb_hole.isChecked():
            self.rb_solid.setChecked(True)
        self._on_mode_toggled(self.rb_solid.isChecked())

        self._update_info()

    def _on_mode_toggled(self, solid_checked: bool) -> None:
        cat = (self.combo_type.currentData() or ("screw", "iso4762"))[0]
        self.combo_fit.setEnabled(not solid_checked and cat not in GROOVES)  # las ranuras son de tabla
        self.chk_subtract.setEnabled(not solid_checked and self.has_selection)
        if not solid_checked and self.has_selection:
            self.chk_subtract.setChecked(True)
        else:
            self.chk_subtract.setChecked(False)
        self._update_info()

    def _update_info(self) -> None:
        cat, std = self.combo_type.currentData() or ("screw", "iso4762")
        size = str(self.combo_size.currentData() or "M3")
        length = float(self.combo_len.currentData() or 16.0)
        fit = str(self.combo_fit.currentData() or "medium")
        is_hole = self.rb_hole.isChecked()

        try:
            lines = describe(cat, std, size, length, fit, self.spin_diameter.value(),
                             str(self.combo_seal.currentData() or "static"))
        except (ValueError, KeyError):
            lines = []
        txt = "<br>".join([f"<b>{html.escape(lines[0])}</b>", *map(html.escape, lines[1:])]) if lines else ""
        if is_hole:
            txt += "<br><span style='color: #B42318;'>{}</span>".format(html.escape(
                tr("Modo taladro: se crea la forma que hay que restar (paso y cajeado), no la pieza.")))

        self.lbl_info.setText(themed(txt))

    def get_result(self) -> dict:
        cat, std = self.combo_type.currentData() or ("screw", "iso4762")
        size = str(self.combo_size.currentData() or "M3")
        length = float(self.combo_len.currentData() or 16.0)
        mode = "hole" if self.rb_hole.isChecked() else "solid"
        fit = str(self.combo_fit.currentData() or "medium")
        subtract = bool(self.chk_subtract.isChecked())
        return {
            "category": cat,
            "standard": std,
            "size": size,
            "length": length,
            "mode": mode,
            "fit": fit,
            "subtract": subtract,
            "diameter": self.spin_diameter.value(),
            "seal": str(self.combo_seal.currentData() or "static"),
        }
