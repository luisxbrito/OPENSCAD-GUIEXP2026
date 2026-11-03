"""Asistente de árbol de levas: eje y reparto inicial de los lóbulos. La lógica está en camshaft.py."""

from __future__ import annotations

import html

from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QSpinBox, QVBoxLayout)

from .. import camshaft
from ..catalog import SPECS
from ..i18n import tr
from .style import themed


def _spin(value: float, low: float, high: float, step: float = 1.0, suffix: str = " mm") -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(low, high)
    s.setDecimals(2)
    s.setSingleStep(step)
    s.setValue(value)
    s.setSuffix(suffix)
    return s


class CamshaftDialog(QDialog):
    """Eje, reparto (cilindros, lóbulos por cilindro, separaciones, desfases, orden) y lóbulo común.
    La ficha lista dónde queda cada lóbulo y avisa de solapes antes de insertar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Árbol de levas"))
        self.resize(620, 720)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        layout.addLayout(row)

        shaft_box = QGroupBox(tr("Eje y reparto"))
        f = QFormLayout(shaft_box)
        self.spin_length = _spin(220, 1, 5000, 5)
        self.spin_d = _spin(25, 1, 500)
        self.spin_cyl = QSpinBox()
        self.spin_cyl.setRange(1, 16)
        self.spin_cyl.setValue(4)
        self.combo_per = QComboBox()
        self.combo_per.addItem(tr("Uno"), 1)
        self.combo_per.addItem(tr("Dos (admisión y escape)"), 2)
        self.combo_per.setCurrentIndex(1)
        self.spin_first = _spin(20, -5000, 5000, 5)
        self.spin_pitch = _spin(50, 0, 5000, 5)
        self.spin_gap = _spin(20, -5000, 5000, 1)
        self.spin_offset = _spin(90, -360, 360, 5, "°")
        self.spin_pair = _spin(110, -360, 360, 5, "°")
        self.spin_start = _spin(0, -360, 360, 5, "°")
        self.edit_order = QLineEdit()
        self.edit_order.setPlaceholderText("1-2-3-4")
        f.addRow(tr("Longitud"), self.spin_length)
        f.addRow(tr("Ø del eje"), self.spin_d)
        f.addRow(tr("Cilindros:"), self.spin_cyl)
        f.addRow(tr("Lóbulos por cilindro:"), self.combo_per)
        f.addRow(tr("Primer lóbulo en z ="), self.spin_first)
        f.addRow(tr("Separación entre cilindros:"), self.spin_pitch)
        self.label_gap = QLabel(tr("De admisión a escape, en el eje:"))
        f.addRow(self.label_gap, self.spin_gap)
        f.addRow(tr("Desfase entre cilindros:"), self.spin_offset)
        f.addRow(tr("Orden de los desfases:"), self.edit_order)
        self.label_pair = QLabel(tr("De admisión a escape, en ángulo:"))
        f.addRow(self.label_pair, self.spin_pair)
        f.addRow(tr("Ángulo del primero:"), self.spin_start)
        row.addWidget(shaft_box)

        lobe_box = QGroupBox(tr("Lóbulo (igual para todos)"))
        g = QFormLayout(lobe_box)
        spec = SPECS["cam_lobe"]
        self.combo_profile = QComboBox()
        for option in spec.param("profile").options:
            self.combo_profile.addItem(option, option)
        self.combo_motion = QComboBox()
        for option in spec.param("motion").options:
            self.combo_motion.addItem(option, option)
        self.spin_base = _spin(15, 0.1, 500)
        self.spin_lift = _spin(8, 0, 500)
        self.spin_width = _spin(12, 0.1, 500)
        self.spin_rise = _spin(110, 1, 358, 5, "°")
        self.spin_dwell = _spin(20, 0, 358, 5, "°")
        self.spin_fall = _spin(110, 1, 358, 5, "°")
        self.spin_nose = _spin(6, 0.1, 500)
        self.spin_step = _spin(1, 0.1, 10, 0.5, "°")
        g.addRow(tr("Perfil"), self.combo_profile)
        g.addRow(tr("Radio base"), self.spin_base)
        g.addRow(tr("Alzada"), self.spin_lift)
        g.addRow(tr("Ancho"), self.spin_width)
        g.addRow(tr("Ley de movimiento"), self.combo_motion)
        g.addRow(tr("Ángulo de subida (°)"), self.spin_rise)
        g.addRow(tr("Reposo en la punta (°)"), self.spin_dwell)
        g.addRow(tr("Ángulo de bajada (°)"), self.spin_fall)
        g.addRow(tr("Radio de la punta (periforme)"), self.spin_nose)
        g.addRow(tr("Resolución (° por punto)"), self.spin_step)
        row.addWidget(lobe_box)

        info_box = QGroupBox(tr("Reparto"))
        info_lay = QVBoxLayout(info_box)
        self.lbl_info = QLabel()
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet(themed("color: #3D4756; font-size: 11px;"))
        info_lay.addWidget(self.lbl_info)
        layout.addWidget(info_box, 1)

        buttons = QHBoxLayout()
        self.btn_insert = QPushButton(tr("Insertar árbol de levas"))
        self.btn_insert.setObjectName("primary")
        self.btn_insert.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("Cancelar"))
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_insert)
        layout.addLayout(buttons)

        self.spin_cyl.valueChanged.connect(self._on_cylinders)
        for w in (self.spin_length, self.spin_d, self.spin_first, self.spin_pitch, self.spin_gap, self.spin_offset,
                  self.spin_pair, self.spin_start, self.spin_base, self.spin_lift, self.spin_width, self.spin_rise,
                  self.spin_dwell, self.spin_fall, self.spin_nose, self.spin_step):
            w.valueChanged.connect(self._update)
        for c in (self.combo_per, self.combo_profile, self.combo_motion):
            c.currentIndexChanged.connect(self._update)
        self.edit_order.textChanged.connect(self._update)
        self._update()

    def _on_cylinders(self, n: int) -> None:
        # Propuesta: los cilindros repartidos por igual en una vuelta del árbol; se puede cambiar.
        self.spin_offset.setValue(360.0 / max(1, n))
        self.edit_order.setPlaceholderText("-".join(str(i) for i in range(1, n + 1)))
        self._update()

    def get_result(self) -> dict:
        per = int(self.combo_per.currentData() or 2)
        return {
            "shaft": {"length": self.spin_length.value(), "d": self.spin_d.value()},
            "lobe": {"profile": self.combo_profile.currentData(), "base_r": self.spin_base.value(),
                     "lift": self.spin_lift.value(), "width": self.spin_width.value(),
                     "motion": self.combo_motion.currentData(), "rise_angle": self.spin_rise.value(),
                     "dwell_angle": self.spin_dwell.value(), "fall_angle": self.spin_fall.value(),
                     "nose_r": self.spin_nose.value(), "step": self.spin_step.value()},
            "cylinders": self.spin_cyl.value(), "per_cylinder": per, "first_z": self.spin_first.value(),
            "pitch": self.spin_pitch.value(), "pair_gap": self.spin_gap.value(),
            "cylinder_offset": self.spin_offset.value(), "pair_angle": self.spin_pair.value(),
            "start_angle": self.spin_start.value(), "order": self.edit_order.text(),
        }

    def items(self) -> list[dict]:
        """Lóbulos del reparto; ValueError si el orden no vale."""
        r = self.get_result()
        order = camshaft.parse_order(r["order"], r["cylinders"])
        return camshaft.layout(r["cylinders"], r["per_cylinder"], r["first_z"], r["pitch"], r["pair_gap"],
                               r["cylinder_offset"], r["pair_angle"], order, r["start_angle"])

    def _update(self) -> None:
        pair = self.combo_per.currentData() == 2
        for w in (self.label_gap, self.spin_gap, self.label_pair, self.spin_pair):
            w.setVisible(pair)
        self.spin_nose.setEnabled(self.combo_profile.currentData() == "periforme")
        try:
            items = self.items()
        except ValueError as exc:
            self.lbl_info.setText(themed("<span style='color: #B42318;'>{}</span>".format(html.escape(str(exc)))))
            self.btn_insert.setEnabled(False)
            return
        r = self.get_result()
        lines = [tr("{name}: z = {z:g} mm, punta a {a:g}°").format(name=camshaft.lobe_name(i), z=round(i["position"], 3),
                                                                   a=round(i["angle"], 3)) for i in items]
        lobes = [(camshaft.lobe_name(i), {**r["lobe"], "position": i["position"]}) for i in items]
        problems = camshaft.shaft_problems(r["shaft"], lobes)
        txt = "<br>".join(html.escape(line) for line in lines)
        for text, data in problems:
            txt += "<br><span style='color: #B42318;'>{}</span>".format(html.escape(tr(text).format(**data)))
        self.lbl_info.setText(themed(txt))
        self.btn_insert.setEnabled(True)
