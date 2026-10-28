"""Diálogo de selección e inserción de componentes estándar industriales."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QPushButton, QRadioButton,
                               QVBoxLayout, QWidget)

from ..hardware import (BEARINGS_ISO, CLEARANCE_HOLES_ISO_273, HEAT_SET_INSERTS,
                         NUTS_DIN_934, NUTS_DIN_985, SCREWS_DIN_933,
                         SCREWS_ISO_4762, SCREWS_ISO_7380, SCREWS_ISO_10642,
                         STANDARD_LENGTHS, WASHERS_DIN_125)
from ..i18n import tr

CATEGORIES = [
    ("screw_allen", "Tornillo Allen cilíndrico (ISO 4762 / DIN 912)", "screw", "iso4762"),
    ("screw_hex", "Tornillo Cabeza Hexagonal (DIN 933 / ISO 4017)", "screw", "din933"),
    ("screw_csk", "Tornillo Avellanado 90° (ISO 10642 / DIN 7991)", "screw", "iso10642"),
    ("screw_btn", "Tornillo Cabeza Botón (ISO 7380)", "screw", "iso7380"),
    ("nut_hex", "Tuerca Hexagonal Estándar (DIN 934 / ISO 4032)", "nut", "din934"),
    ("nut_lock", "Tuerca Autoblocante (DIN 985)", "nut", "din985"),
    ("heat_set", "Inserto Roscado de Latón (Impresión 3D FDM)", "insert", "heat_set"),
    ("washer", "Arandela Plana (DIN 125 / ISO 7089)", "washer", "din125"),
    ("bearing", "Rodamiento Radial de Bolas (ISO 15 / DIN 625)", "bearing", "bearing"),
    ("profile", "Perfil de Aluminio Estructural (Ranura T 6mm)", "profile", "profile"),
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
        for key, label, cat, std in CATEGORIES:
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
        self.lbl_info.setStyleSheet("color: #3D4756; font-size: 11px;")
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
            sizes = ["M2", "M2.5", "M3", "M4", "M5", "M6", "M8"]
            if cat != "insert":
                sizes.append("M10")
            for s in sizes:
                self.combo_size.addItem(s, s)
            # Seleccionar métrica por defecto
            m_idx = self.combo_size.findData(self.default_metric)
            if m_idx >= 0:
                self.combo_size.setCurrentIndex(m_idx)
        elif cat == "bearing":
            for b_id, b_info in BEARINGS_ISO.items():
                self.combo_size.addItem(f"{b_id} (Ø{b_info['d']}xØ{b_info['D']}x{b_info['B']} mm)", b_id)
        elif cat == "profile":
            self.combo_size.addItem("Perfil 2020 (20×20 mm)", "2020")
            self.combo_size.addItem("Perfil 2040 (20×40 mm)", "2040")

        self.combo_size.blockSignals(False)

        # Longitud sólo relevante para tornillos y perfiles
        is_length_applicable = cat in ("screw", "profile")
        self.label_len.setVisible(is_length_applicable)
        self.combo_len.setVisible(is_length_applicable)
        if cat == "profile":
            self.label_len.setText("Longitud del perfil:")
        else:
            self.label_len.setText("Longitud del vástago (L):")

        # El modo negativo solo aplica a tornillos, tuercas, insertos y rodamientos
        can_hole = cat in ("screw", "nut", "insert", "bearing")
        self.rb_hole.setEnabled(can_hole)
        if not can_hole and self.rb_hole.isChecked():
            self.rb_solid.setChecked(True)

        self._update_info()

    def _on_mode_toggled(self, solid_checked: bool) -> None:
        self.combo_fit.setEnabled(not solid_checked)
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

        txt = ""
        if cat == "screw":
            clr = CLEARANCE_HOLES_ISO_273.get(size, {}).get(fit, 3.4)
            if std == "iso4762":
                spec = SCREWS_ISO_4762.get(size, SCREWS_ISO_4762["M3"])
                txt = (f"<b>Tornillo Allen cilíndrico {size}×{int(length)} (ISO 4762 / DIN 912)</b><br>"
                       f"• Diámetro nominal: d = {spec['d']} mm  |  Longitud: L = {length} mm<br>"
                       f"• Cabeza: dk = {spec['dk']} mm  |  Altura cabeza: k = {spec['k']} mm<br>"
                       f"• Llave hex: s = {spec['s']} mm  |  Profundidad: t = {spec['t']} mm<br>"
                       f"• <b>Paso pasante recomendado (ISO 273):</b> Ø {clr} mm  |  Cajeado: Ø {spec['dk'] + 0.6:.1f} mm")
            elif std == "din933":
                spec = SCREWS_DIN_933.get(size, SCREWS_DIN_933["M3"])
                txt = (f"<b>Tornillo Cabeza Hexagonal {size}×{int(length)} (DIN 933 / ISO 4017)</b><br>"
                       f"• Diámetro nominal: d = {spec['d']} mm  |  Longitud: L = {length} mm<br>"
                       f"• Ancho entre caras: s = {spec['s']} mm  |  Altura cabeza: k = {spec['k']} mm<br>"
                       f"• <b>Paso pasante recomendado (ISO 273):</b> Ø {clr} mm")
            elif std == "iso10642":
                spec = SCREWS_ISO_10642.get(size, SCREWS_ISO_10642["M3"])
                txt = (f"<b>Tornillo Avellanado 90° {size}×{int(length)} (ISO 10642 / DIN 7991)</b><br>"
                       f"• Diámetro nominal: d = {spec['d']} mm  |  Longitud total: L = {length} mm<br>"
                       f"• Diámetro cono exterior: dk = {spec['dk']} mm  |  Profundidad cono: k = {spec['k']} mm<br>"
                       f"• <b>Paso pasante y avellanado:</b> Ø {clr} mm a 90° hasta Ø {spec['dk'] + 0.5:.1f} mm")
            elif std == "iso7380":
                spec = SCREWS_ISO_7380.get(size, SCREWS_ISO_7380["M3"])
                txt = (f"<b>Tornillo Cabeza Botón {size}×{int(length)} (ISO 7380)</b><br>"
                       f"• Diámetro nominal: d = {spec['d']} mm  |  Longitud: L = {length} mm<br>"
                       f"• Cabeza abombada: dk = {spec['dk']} mm  |  Altura: k = {spec['k']} mm")
        elif cat == "nut":
            spec = (NUTS_DIN_985 if std == "din985" else NUTS_DIN_934).get(size, NUTS_DIN_934["M3"])
            txt = (f"<b>Tuerca Hexagonal {size} ({'DIN 985 Autoblocante' if std == 'din985' else 'DIN 934 Estándar'})</b><br>"
                   f"• Métrica: M{spec['d']}  |  Ancho entre caras: s = {spec['s']} mm<br>"
                   f"• Espesor / Altura: m = {spec['m']} mm<br>"
                   f"• <b>Cajeado recomendado para embutir en FDM:</b> s = {spec['s'] + 0.4:.1f} mm, prof = {spec['m'] + 0.3:.1f} mm")
        elif cat == "insert":
            spec = HEAT_SET_INSERTS.get(size, HEAT_SET_INSERTS["M3"])
            txt = (f"<b>Inserto roscado de latón {size} (FDM 3D Heat-set)</b><br>"
                   f"• Roscado interior: M{spec['d']}  |  Diámetro exterior estriado: Ø {spec['d_ext']} mm<br>"
                   f"• Longitud: L = {spec['L']} mm<br>"
                   f"• <b>Taladro térmico recomendado en la pieza:</b> Ø {spec['d_hole']} mm × {spec['L'] + 1.0:.1f} mm de profundidad")
        elif cat == "washer":
            spec = WASHERS_DIN_125.get(size, WASHERS_DIN_125["M3"])
            txt = (f"<b>Arandela plana {size} (DIN 125 / ISO 7089)</b><br>"
                   f"• Paso interior: d1 = {spec['d1']} mm  |  Exterior: d2 = {spec['d2']} mm<br>"
                   f"• Espesor nominal: h = {spec['h']} mm")
        elif cat == "bearing":
            spec = BEARINGS_ISO.get(size, BEARINGS_ISO["608"])
            txt = (f"<b>{spec['name']} (Norma ISO 15 / DIN 625)</b><br>"
                   f"• Eje interior: d = {spec['d']} mm  |  Diámetro exterior: D = {spec['D']} mm<br>"
                   f"• Ancho / Espesor: B = {spec['B']} mm<br>"
                   f"• <b>Alojamiento en pared:</b> Cajeado Ø {spec['D'] + 0.35:.2f} mm × {spec['B'] + 0.2:.1f} mm")
        elif cat == "profile":
            txt = (f"<b>Perfil de aluminio extruido {size} (Ranura en T estándar de 6 mm)</b><br>"
                   f"• Sección: {'20×20 mm' if size == '2020' else '20×40 mm'}  |  Longitud: {length} mm<br>"
                   f"• Taladros centrales de Ø 4.2 mm preparados para roscar a métrica M5.")

        if is_hole:
            txt += "<br><span style='color: #B42318;'><b>Modo resta activo:</b> Genera la geometría negativa para taladro de paso y cajeados.</span>"

        self.lbl_info.setText(txt)

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
        }
