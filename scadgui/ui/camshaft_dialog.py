"""Asistente de árbol de levas: eje, reparto de lóbulos, apoyos y extremos. La lógica está en camshaft.py."""

from __future__ import annotations

import html

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
                               QVBoxLayout, QWidget)

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
    """Eje, reparto (cilindros, lóbulos por cilindro, separaciones, desfases, orden), lóbulo común,
    muñones de apoyo y extremos del eje. La ficha lista dónde queda cada elemento y avisa de solapes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Árbol de levas"))
        self.resize(720, 780)
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        col_left = QVBoxLayout()
        col_right = QVBoxLayout()
        row.addLayout(col_left)
        row.addLayout(col_right)
        layout.addLayout(row)

        # Columna izquierda: Eje y reparto
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
        col_left.addWidget(shaft_box)

        # Extremos del árbol (delantero y trasero)
        end_box = QGroupBox(tr("Extremos del árbol"))
        end_lay = QVBoxLayout(end_box)

        self.check_front_end = QCheckBox(tr("Extremo delantero"))
        self.check_front_end.setChecked(True)
        end_lay.addWidget(self.check_front_end)
        self.widget_front = QWidget()
        front_f = QFormLayout(self.widget_front)
        front_f.setContentsMargins(16, 0, 0, 4)
        self.combo_front_type = QComboBox()
        for t in ("chavetero", "liso", "estriado", "plato"):
            self.combo_front_type.addItem(t, t)
        self.spin_front_d = _spin(20, 1, 500)
        self.spin_front_len = _spin(25, 1, 500)
        front_f.addRow(tr("Tipo:"), self.combo_front_type)
        front_f.addRow(tr("Ø del extremo:"), self.spin_front_d)
        front_f.addRow(tr("Longitud:"), self.spin_front_len)
        end_lay.addWidget(self.widget_front)

        self.check_rear_end = QCheckBox(tr("Extremo trasero"))
        self.check_rear_end.setChecked(False)
        end_lay.addWidget(self.check_rear_end)
        self.widget_rear = QWidget()
        rear_f = QFormLayout(self.widget_rear)
        rear_f.setContentsMargins(16, 0, 0, 4)
        self.combo_rear_type = QComboBox()
        for t in ("liso", "chavetero", "estriado", "plato"):
            self.combo_rear_type.addItem(t, t)
        self.spin_rear_d = _spin(20, 1, 500)
        self.spin_rear_len = _spin(25, 1, 500)
        rear_f.addRow(tr("Tipo:"), self.combo_rear_type)
        rear_f.addRow(tr("Ø del extremo:"), self.spin_rear_d)
        rear_f.addRow(tr("Longitud:"), self.spin_rear_len)
        end_lay.addWidget(self.widget_rear)
        col_left.addWidget(end_box)

        # Columna derecha: Lóbulo común
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
        col_right.addWidget(lobe_box)

        # Muñones de apoyo
        bearing_box = QGroupBox(tr("Muñones de apoyo"))
        b_lay = QVBoxLayout(bearing_box)
        self.check_bearings = QCheckBox(tr("Incluir muñones de apoyo"))
        self.check_bearings.setChecked(True)
        b_lay.addWidget(self.check_bearings)
        self.widget_bearing = QWidget()
        bf = QFormLayout(self.widget_bearing)
        bf.setContentsMargins(16, 0, 0, 0)
        self.spin_bearing_d = _spin(28, 1, 500)
        self.spin_bearing_w = _spin(15, 1, 500)
        self.combo_tunnel = QComboBox()
        self.combo_tunnel.addItem(tr("Cojinetes enteros (en túnel)"), True)
        self.combo_tunnel.addItem(tr("Cojinetes partidos (con tapa)"), False)
        bf.addRow(tr("Ø de los muñones:"), self.spin_bearing_d)
        bf.addRow(tr("Longitud de apoyo:"), self.spin_bearing_w)
        bf.addRow(tr("Tipo de cojinete:"), self.combo_tunnel)
        b_lay.addWidget(self.widget_bearing)
        col_right.addWidget(bearing_box)

        # Ficha de reparto y comprobaciones
        info_box = QGroupBox(tr("Reparto y comprobaciones"))
        info_lay = QVBoxLayout(info_box)
        info_scroll = QScrollArea()
        info_scroll.setWidgetResizable(True)
        info_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        info_scroll.setStyleSheet("background: transparent;")
        self.lbl_info = QLabel()
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet(themed("color: #3D4756; font-size: 11px;"))
        info_scroll.setWidget(self.lbl_info)
        info_lay.addWidget(info_scroll)
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
                  self.spin_dwell, self.spin_fall, self.spin_nose, self.spin_step,
                  self.spin_bearing_d, self.spin_bearing_w, self.spin_front_d, self.spin_front_len,
                  self.spin_rear_d, self.spin_rear_len):
            w.valueChanged.connect(self._update)
        for c in (self.combo_per, self.combo_profile, self.combo_motion, self.combo_tunnel,
                  self.combo_front_type, self.combo_rear_type):
            c.currentIndexChanged.connect(self._update)
        for chk in (self.check_bearings, self.check_front_end, self.check_rear_end):
            chk.toggled.connect(self._update)
        self.edit_order.textChanged.connect(self._update)
        self._update()

    def _on_cylinders(self, n: int) -> None:
        self.spin_offset.setValue(360.0 / max(1, n))
        self.edit_order.setPlaceholderText("-".join(str(i) for i in range(1, n + 1)))
        self._update()

    def bearings(self) -> list[dict]:
        """Muñones calculados según el reparto del eje."""
        if not self.check_bearings.isChecked():
            return []
        cyl = self.spin_cyl.value()
        per = int(self.combo_per.currentData() or 2)
        b_layout = camshaft.bearing_layout(
            cylinders=cyl,
            per_cylinder=per,
            first_z=self.spin_first.value(),
            pitch=self.spin_pitch.value(),
            pair_gap=self.spin_gap.value(),
            shaft_length=self.spin_length.value(),
            bearing_width=self.spin_bearing_w.value()
        )
        bd = self.spin_bearing_d.value()
        return [{"index": b["index"], "position": b["position"], "width": b["width"], "d": bd}
                for b in b_layout]

    def ends(self) -> list[dict]:
        """Extremos delantero y/o trasero seleccionados."""
        res = []
        if self.check_front_end.isChecked():
            l = self.spin_front_len.value()
            res.append({
                "kind": "front",
                "d": self.spin_front_d.value(),
                "length": l,
                "position": -l,
                "end_type": self.combo_front_type.currentData(),
            })
        if self.check_rear_end.isChecked():
            l = self.spin_rear_len.value()
            res.append({
                "kind": "rear",
                "d": self.spin_rear_d.value(),
                "length": l,
                "position": self.spin_length.value(),
                "end_type": self.combo_rear_type.currentData(),
            })
        return res

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
            "bearings": self.bearings(),
            "ends": self.ends(),
            "tunnel_bearings": bool(self.combo_tunnel.currentData()),
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
        self.widget_bearing.setVisible(self.check_bearings.isChecked())
        self.widget_front.setVisible(self.check_front_end.isChecked())
        self.widget_rear.setVisible(self.check_rear_end.isChecked())

        try:
            items = self.items()
        except ValueError as exc:
            self.lbl_info.setText(themed("<span style='color: #B42318;'>{}</span>".format(html.escape(str(exc)))))
            self.btn_insert.setEnabled(False)
            return

        r = self.get_result()
        lines = [tr("{name}: z = {z:g} mm, punta a {a:g}°").format(
            name=camshaft.lobe_name(i), z=round(i["position"], 3), a=round(i["angle"], 3)) for i in items]

        for b in r["bearings"]:
            lines.append(tr("{name}: z = {z:g} mm, Ø {d:g} mm, ancho {w:g} mm").format(
                name=camshaft.bearing_name(b["index"]), z=round(b["position"], 3),
                d=b["d"], w=b["width"]))

        for e in r["ends"]:
            lines.append(tr("{name} ({t}): z = {z:g} a {z1:g} mm, Ø {d:g} mm").format(
                name=camshaft.end_name(e["kind"]), t=e["end_type"],
                z=round(e["position"], 3), z1=round(e["position"] + e["length"], 3),
                d=e["d"]))

        lobes = [(camshaft.lobe_name(i), {**r["lobe"], "position": i["position"]}) for i in items]
        bearing_pairs = [(camshaft.bearing_name(b["index"]), b) for b in r["bearings"]]
        problems = camshaft.shaft_problems(r["shaft"], lobes, bearing_pairs, tunnel_bearings=r["tunnel_bearings"])

        txt = "<br>".join(html.escape(line) for line in lines)
        for text, data in problems:
            txt += "<br><span style='color: #B42318;'>{}</span>".format(html.escape(tr(text).format(**data)))
        self.lbl_info.setText(themed(txt))
        self.btn_insert.setEnabled(True)
