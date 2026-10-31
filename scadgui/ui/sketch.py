"""Diálogo del asistente de perfiles 2D (la geometría está en ``sketches.py``)."""

from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QGroupBox, QSpinBox,
                               QStackedWidget, QVBoxLayout, QWidget)

from ..i18n import tr
from ..sketches import PROFILES


class SketchDialog(QDialog):
    """Diálogo interactivo para parametrizar e insertar perfiles 2D."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Asistente de bocetos 2D y perfiles"))
        self.resize(440, 480)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. Selector de perfil
        top_group = QGroupBox(tr("Tipo de perfil 2D"))
        top_lay = QFormLayout(top_group)
        self.combo = QComboBox()
        for key, label in PROFILES:
            self.combo.addItem(tr(label), key)
        self.combo.currentIndexChanged.connect(self._on_profile_changed)
        top_lay.addRow(tr("Perfil:"), self.combo)
        layout.addWidget(top_group)

        # 2. Parámetros específicos por perfil
        param_group = QGroupBox(tr("Dimensiones del perfil"))
        param_lay = QVBoxLayout(param_group)
        self.stack = QStackedWidget()

        # Pagina 0: rounded_rect
        p0 = QWidget(); l0 = QFormLayout(p0)
        self.rr_w = QDoubleSpinBox(); self.rr_w.setRange(1, 10000); self.rr_w.setValue(40.0)
        self.rr_h = QDoubleSpinBox(); self.rr_h.setRange(1, 10000); self.rr_h.setValue(25.0)
        self.rr_r = QDoubleSpinBox(); self.rr_r.setRange(0, 1000); self.rr_r.setValue(3.0)
        self.rr_center = QCheckBox(tr("Centrado")); self.rr_center.setChecked(True)
        l0.addRow(tr("Ancho (X):"), self.rr_w)
        l0.addRow(tr("Alto (Y):"), self.rr_h)
        l0.addRow(tr("Radio esquinas:"), self.rr_r)
        l0.addRow("", self.rr_center)
        self.stack.addWidget(p0)

        # Pagina 1: slot
        p1 = QWidget(); l1 = QFormLayout(p1)
        self.sl_l = QDoubleSpinBox(); self.sl_l.setRange(1, 10000); self.sl_l.setValue(30.0)
        self.sl_r = QDoubleSpinBox(); self.sl_r.setRange(0.1, 1000); self.sl_r.setValue(5.0)
        l1.addRow(tr("Largo entre centros:"), self.sl_l)
        l1.addRow(tr("Radio (anchura / 2):"), self.sl_r)
        self.stack.addWidget(p1)

        # Pagina 2: regular_polygon
        p2 = QWidget(); l2 = QFormLayout(p2)
        self.poly_n = QSpinBox(); self.poly_n.setRange(3, 64); self.poly_n.setValue(6)
        self.poly_r = QDoubleSpinBox(); self.poly_r.setRange(0.5, 10000); self.poly_r.setValue(15.0)
        l2.addRow(tr("Número de lados:"), self.poly_n)
        l2.addRow(tr("Radio circunscrito:"), self.poly_r)
        self.stack.addWidget(p2)

        # Pagina 3: star
        p3 = QWidget(); l3 = QFormLayout(p3)
        self.star_p = QSpinBox(); self.star_p.setRange(3, 32); self.star_p.setValue(5)
        self.star_r1 = QDoubleSpinBox(); self.star_r1.setRange(0.5, 10000); self.star_r1.setValue(20.0)
        self.star_r2 = QDoubleSpinBox(); self.star_r2.setRange(0.1, 10000); self.star_r2.setValue(9.0)
        l3.addRow(tr("Puntas de la estrella:"), self.star_p)
        l3.addRow(tr("Radio exterior (R1):"), self.star_r1)
        l3.addRow(tr("Radio interior (R2):"), self.star_r2)
        self.stack.addWidget(p3)

        # Pagina 4: ring
        p4 = QWidget(); l4 = QFormLayout(p4)
        self.ring_rext = QDoubleSpinBox(); self.ring_rext.setRange(1, 10000); self.ring_rext.setValue(20.0)
        self.ring_rint = QDoubleSpinBox(); self.ring_rint.setRange(0.1, 10000); self.ring_rint.setValue(12.0)
        l4.addRow(tr("Radio exterior:"), self.ring_rext)
        l4.addRow(tr("Radio interior:"), self.ring_rint)
        self.stack.addWidget(p4)

        # Pagina 5: l_profile
        p5 = QWidget(); l5 = QFormLayout(p5)
        self.lp_w = QDoubleSpinBox(); self.lp_w.setRange(1, 10000); self.lp_w.setValue(30.0)
        self.lp_h = QDoubleSpinBox(); self.lp_h.setRange(1, 10000); self.lp_h.setValue(30.0)
        self.lp_t = QDoubleSpinBox(); self.lp_t.setRange(0.2, 1000); self.lp_t.setValue(4.0)
        l5.addRow(tr("Ancho total (W):"), self.lp_w)
        l5.addRow(tr("Alto total (H):"), self.lp_h)
        l5.addRow(tr("Espesor de pared (t):"), self.lp_t)
        self.stack.addWidget(p5)

        param_lay.addWidget(self.stack)
        layout.addWidget(param_group)

        # 3. Opciones de extrusión a 3D
        ext_group = QGroupBox(tr("Opciones 3D"))
        ext_lay = QFormLayout(ext_group)
        self.chk_extrude = QCheckBox(tr("Extruir a 3D directamente (linear_extrude)"))
        self.chk_extrude.setChecked(False)
        self.chk_extrude.toggled.connect(self._on_extrude_toggled)
        self.spin_height = QDoubleSpinBox()
        self.spin_height.setRange(0.1, 10000)
        self.spin_height.setValue(10.0)
        self.spin_height.setEnabled(False)
        ext_lay.addRow(self.chk_extrude)
        ext_lay.addRow(tr("Altura de extrusión (H):"), self.spin_height)
        layout.addWidget(ext_group)

        # 4. Botones Aceptar / Cancelar
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _on_profile_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)

    def _on_extrude_toggled(self, checked: bool) -> None:
        self.spin_height.setEnabled(checked)

    def get_result(self) -> tuple[str, dict, bool, float]:
        """Devuelve (profile_key, params_dict, extrude_3d, extrude_height)."""
        key = self.combo.currentData() or "rounded_rect"
        extrude_3d = bool(self.chk_extrude.isChecked())
        extrude_h = float(self.spin_height.value())

        if key == "rounded_rect":
            params = {
                "w": float(self.rr_w.value()),
                "h": float(self.rr_h.value()),
                "r": float(self.rr_r.value()),
                "center": self.rr_center.isChecked(),
            }
        elif key == "slot":
            params = {
                "l": float(self.sl_l.value()),
                "r": float(self.sl_r.value()),
            }
        elif key == "regular_polygon":
            params = {
                "n": int(self.poly_n.value()),
                "r": float(self.poly_r.value()),
            }
        elif key == "star":
            params = {
                "p": int(self.star_p.value()),
                "r1": float(self.star_r1.value()),
                "r2": float(self.star_r2.value()),
            }
        elif key == "ring":
            params = {
                "r_ext": float(self.ring_rext.value()),
                "r_int": float(self.ring_rint.value()),
            }
        elif key == "l_profile":
            params = {
                "w": float(self.lp_w.value()),
                "h": float(self.lp_h.value()),
                "t": float(self.lp_t.value()),
            }
        else:
            params = {}

        return key, params, extrude_3d, extrude_h
