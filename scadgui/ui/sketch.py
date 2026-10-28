"""Asistente de bocetos y perfiles 2D para extrusión."""

from __future__ import annotations

import math
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QGroupBox, QLabel,
                               QLineEdit, QSpinBox, QStackedWidget, QVBoxLayout,
                               QWidget)

from ..i18n import tr
from ..model import Node, make_node


PROFILES = (
    ("rounded_rect", "Rectángulo redondeado"),
    ("slot", "Ranura / Chavetero"),
    ("regular_polygon", "Polígono regular"),
    ("star", "Estrella paramétrica"),
    ("ring", "Corona / Anillo"),
    ("l_profile", "Perfil en L"),
)


def create_sketch_node(profile: str, params: dict, unique_name_fn: Callable[[str], str],
                       extrude_3d: bool = False, extrude_h: float = 10.0) -> Node:
    """Construye un árbol de Node estándar de OpenSCAD para el perfil 2D elegido."""
    if profile == "rounded_rect":
        w = float(params.get("w", 40.0))
        h = float(params.get("h", 25.0))
        r = float(params.get("r", 3.0))
        center = bool(params.get("center", True))
        if r > 0.001:
            w_inner = max(0.1, w - 2 * r)
            h_inner = max(0.1, h - 2 * r)
            off = make_node("offset", unique_name_fn("Redondeo"))
            off.params["r"] = round(r, 4)
            sq = make_node("square", unique_name_fn("Base"))
            sq.params["size"] = [round(w_inner, 4), round(h_inner, 4)]
            sq.params["center"] = center
            off.children.append(sq)
            root = off
        else:
            sq = make_node("square", unique_name_fn("Rectángulo"))
            sq.params["size"] = [round(w, 4), round(h, 4)]
            sq.params["center"] = center
            root = sq

    elif profile == "slot":
        l = float(params.get("l", 30.0))
        r = float(params.get("r", 5.0))
        hull = make_node("hull", unique_name_fn("Ranura"))
        t1 = make_node("translate", unique_name_fn("Extremo 1"))
        t1.params["v"] = [-round(l / 2, 4), 0, 0]
        c1 = make_node("circle", unique_name_fn("Círculo 1"))
        c1.params["r"] = round(r, 4)
        t1.children.append(c1)
        t2 = make_node("translate", unique_name_fn("Extremo 2"))
        t2.params["v"] = [round(l / 2, 4), 0, 0]
        c2 = make_node("circle", unique_name_fn("Círculo 2"))
        c2.params["r"] = round(r, 4)
        t2.children.append(c2)
        hull.children.extend([t1, t2])
        root = hull

    elif profile == "regular_polygon":
        n = int(params.get("n", 6))
        r = float(params.get("r", 15.0))
        c = make_node("circle", unique_name_fn(f"Polígono {n} lados"))
        c.params["r"] = round(r, 4)
        c.params["$fn"] = max(3, n)
        root = c

    elif profile == "star":
        p = int(params.get("p", 5))
        r1 = float(params.get("r1", 20.0))
        r2 = float(params.get("r2", 9.0))
        p = max(3, p)
        points = []
        for i in range(2 * p):
            rad = r1 if i % 2 == 0 else r2
            angle = math.pi / 2 - i * (math.pi / p)
            points.append([round(rad * math.cos(angle), 4), round(rad * math.sin(angle), 4)])
        p_node = make_node("polygon", unique_name_fn(f"Estrella {p} puntas"))
        p_node.params["points"] = points
        root = p_node

    elif profile == "ring":
        r_ext = float(params.get("r_ext", 20.0))
        r_int = float(params.get("r_int", 12.0))
        if r_int >= r_ext:
            r_int = max(0.1, r_ext - 1.0)
        diff = make_node("difference", unique_name_fn("Anillo"))
        c1 = make_node("circle", unique_name_fn("Exterior"))
        c1.params["r"] = round(r_ext, 4)
        c2 = make_node("circle", unique_name_fn("Interior"))
        c2.params["r"] = round(r_int, 4)
        diff.children.extend([c1, c2])
        root = diff

    elif profile == "l_profile":
        w = float(params.get("w", 30.0))
        h = float(params.get("h", 30.0))
        t = float(params.get("t", 4.0))
        t_safe = min(t, min(w, h) - 0.5)
        p_node = make_node("polygon", unique_name_fn("Perfil en L"))
        p_node.params["points"] = [
            [0.0, 0.0],
            [round(w, 4), 0.0],
            [round(w, 4), round(t_safe, 4)],
            [round(t_safe, 4), round(t_safe, 4)],
            [round(t_safe, 4), round(h, 4)],
            [0.0, round(h, 4)],
        ]
        root = p_node

    else:
        raise ValueError(f"Perfil desconocido: {profile}")

    if extrude_3d:
        ext = make_node("linear_extrude", unique_name_fn("Extrusión " + root.name))
        ext.params["height"] = round(max(0.01, extrude_h), 4)
        ext.children.append(root)
        root = ext

    return root


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
        l0.addRow("Ancho (X):", self.rr_w)
        l0.addRow("Alto (Y):", self.rr_h)
        l0.addRow("Radio esquinas:", self.rr_r)
        l0.addRow("", self.rr_center)
        self.stack.addWidget(p0)

        # Pagina 1: slot
        p1 = QWidget(); l1 = QFormLayout(p1)
        self.sl_l = QDoubleSpinBox(); self.sl_l.setRange(1, 10000); self.sl_l.setValue(30.0)
        self.sl_r = QDoubleSpinBox(); self.sl_r.setRange(0.1, 1000); self.sl_r.setValue(5.0)
        l1.addRow("Largo entre centros:", self.sl_l)
        l1.addRow("Radio (anchura / 2):", self.sl_r)
        self.stack.addWidget(p1)

        # Pagina 2: regular_polygon
        p2 = QWidget(); l2 = QFormLayout(p2)
        self.poly_n = QSpinBox(); self.poly_n.setRange(3, 64); self.poly_n.setValue(6)
        self.poly_r = QDoubleSpinBox(); self.poly_r.setRange(0.5, 10000); self.poly_r.setValue(15.0)
        l2.addRow("Número de lados:", self.poly_n)
        l2.addRow("Radio circunscrito:", self.poly_r)
        self.stack.addWidget(p2)

        # Pagina 3: star
        p3 = QWidget(); l3 = QFormLayout(p3)
        self.star_p = QSpinBox(); self.star_p.setRange(3, 32); self.star_p.setValue(5)
        self.star_r1 = QDoubleSpinBox(); self.star_r1.setRange(0.5, 10000); self.star_r1.setValue(20.0)
        self.star_r2 = QDoubleSpinBox(); self.star_r2.setRange(0.1, 10000); self.star_r2.setValue(9.0)
        l3.addRow("Puntas de la estrella:", self.star_p)
        l3.addRow("Radio exterior (R1):", self.star_r1)
        l3.addRow("Radio interior (R2):", self.star_r2)
        self.stack.addWidget(p3)

        # Pagina 4: ring
        p4 = QWidget(); l4 = QFormLayout(p4)
        self.ring_rext = QDoubleSpinBox(); self.ring_rext.setRange(1, 10000); self.ring_rext.setValue(20.0)
        self.ring_rint = QDoubleSpinBox(); self.ring_rint.setRange(0.1, 10000); self.ring_rint.setValue(12.0)
        l4.addRow("Radio exterior:", self.ring_rext)
        l4.addRow("Radio interior:", self.ring_rint)
        self.stack.addWidget(p4)

        # Pagina 5: l_profile
        p5 = QWidget(); l5 = QFormLayout(p5)
        self.lp_w = QDoubleSpinBox(); self.lp_w.setRange(1, 10000); self.lp_w.setValue(30.0)
        self.lp_h = QDoubleSpinBox(); self.lp_h.setRange(1, 10000); self.lp_h.setValue(30.0)
        self.lp_t = QDoubleSpinBox(); self.lp_t.setRange(0.2, 1000); self.lp_t.setValue(4.0)
        l5.addRow("Ancho total (W):", self.lp_w)
        l5.addRow("Alto total (H):", self.lp_h)
        l5.addRow("Espesor de pared (t):", self.lp_t)
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
        idx = self.combo.currentIndex()
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
