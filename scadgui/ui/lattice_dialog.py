"""Diálogo interactivo para configurar e insertar estructuras aligeradas, lattice celular y TPMS Gyroid."""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                               QDoubleSpinBox, QFormLayout, QFrame, QGroupBox,
                               QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QRadioButton, QScrollArea, QSizePolicy, QSplitter,
                               QTabWidget, QVBoxLayout, QWidget)

from .. import lattice
from ..i18n import tr
from ..model import Node
from .style import themed


class LatticeSlicePreview(QWidget):
    """Visualizador 2D interactivo del corte transversal del patrón celular y su piel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.dx = 50.0
        self.dy = 50.0
        self.cell_size = 10.0
        self.wall_thick = 1.2
        self.pattern = "gyroid"
        self.has_shell = False
        self.shell_thick = 1.2
        self.has_drain = False
        self.drain_d = 4.0

    def update_params(self, dx: float, dy: float, cell_size: float, wall_thick: float,
                      pattern: str, has_shell: bool, shell_thick: float,
                      has_drain: bool, drain_d: float) -> None:
        self.dx = max(1.0, dx)
        self.dy = max(1.0, dy)
        self.cell_size = max(1.0, cell_size)
        self.wall_thick = max(0.2, wall_thick)
        self.pattern = pattern
        self.has_shell = has_shell
        self.shell_thick = shell_thick
        self.has_drain = has_drain
        self.drain_d = drain_d
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Fondo del visor
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#0F172A"))

        # Escala y centrado
        margin = 25
        avail_w = max(10, w - 2 * margin)
        avail_h = max(10, h - 2 * margin)
        scale = min(avail_w / self.dx, avail_h / self.dy)

        pw = self.dx * scale
        ph = self.dy * scale
        cx = (w - pw) / 2.0
        cy = (h - ph) / 2.0

        # Cuadrícula base / límite de la pieza
        p.setPen(QPen(QColor("#334155"), 1.0, Qt.PenStyle.DashLine))
        p.drawRect(int(cx), int(cy), int(pw), int(ph))

        # Dibujo del patrón celular interno
        cell_px = max(4.0, self.cell_size * scale)
        wall_px = max(1.0, self.wall_thick * scale)

        clip_x = cx
        clip_y = cy
        clip_w = pw
        clip_h = ph

        if self.has_shell:
            s_px = self.shell_thick * scale
            clip_x += s_px
            clip_y += s_px
            clip_w = max(0.0, pw - 2 * s_px)
            clip_h = max(0.0, ph - 2 * s_px)

        p.save()
        p.setClipRect(int(clip_x), int(clip_y), int(clip_w), int(clip_h))

        if self.pattern == "gyroid":
            # Líneas onduladas periódicas TPMS que representan el corte en z = 0
            p.setPen(QPen(QColor("#38BDF8"), max(1.5, wall_px)))
            ny = int(clip_h / cell_px) + 2
            nx = int(clip_w / cell_px) + 2
            for iy in range(-1, ny):
                base_y = clip_y + iy * cell_px
                prev_pt = None
                steps = max(10, int(clip_w / 3.0))
                for s in range(steps + 1):
                    t = s / steps
                    cur_x = clip_x + t * clip_w
                    wave = math.sin((cur_x - clip_x) / cell_px * 2 * math.pi) * (cell_px * 0.35)
                    cur_y = base_y + wave
                    if prev_pt is not None:
                        p.drawLine(int(prev_pt[0]), int(prev_pt[1]), int(cur_x), int(cur_y))
                    prev_pt = (cur_x, cur_y)

        elif self.pattern == "schwarz_p":
            # Cuadrícula ortogonal con nodos redondeados
            p.setPen(QPen(QColor("#818CF8"), max(1.5, wall_px)))
            x = clip_x
            while x <= clip_x + clip_w:
                p.drawLine(int(x), int(clip_y), int(x), int(clip_y + clip_h))
                x += cell_px
            y = clip_y
            while y <= clip_y + clip_h:
                p.drawLine(int(clip_x), int(y), int(clip_x + clip_w), int(y))
                y += cell_px

        elif self.pattern == "honeycomb":
            # Panal hexagonal 2D
            p.setPen(QPen(QColor("#F59E0B"), max(1.5, wall_px)))
            r = cell_px * 0.5
            dx_step = r * 1.732
            dy_step = r * 1.5
            nx = int(clip_w / dx_step) + 3
            ny = int(clip_h / dy_step) + 3
            for row in range(-1, ny):
                for col in range(-1, nx):
                    hx = clip_x + col * dx_step + ((row % 2) * (dx_step / 2.0))
                    hy = clip_y + row * dy_step
                    # 6 vértices
                    pts = []
                    for k in range(6):
                        ang = math.radians(60 * k - 30)
                        pts.append((hx + (r - wall_px * 0.5) * math.cos(ang),
                                    hy + (r - wall_px * 0.5) * math.sin(ang)))
                    for k in range(6):
                        p1 = pts[k]
                        p2 = pts[(k + 1) % 6]
                        p.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

        else:  # voronoi
            # Celdas poligonales orgánicas
            p.setPen(QPen(QColor("#34D399"), max(1.5, wall_px)))
            step = cell_px * 1.1
            nx = int(clip_w / step) + 2
            ny = int(clip_h / step) + 2
            for iy in range(ny):
                for ix in range(nx):
                    vx = clip_x + ix * step + ((iy % 2) * (step * 0.3))
                    vy = clip_y + iy * step
                    p.drawEllipse(int(vx), int(vy), int(step * 0.7), int(step * 0.7))

        p.restore()

        # Dibujo de la piel sólida exterior si está activada
        if self.has_shell:
            p.setPen(QPen(QColor("#60A5FA"), max(2.0, self.shell_thick * scale)))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(int(cx), int(cy), int(pw), int(ph))

        # Orificios de drenaje
        if self.has_drain and self.drain_d > 0:
            p.setPen(QPen(QColor("#F87171"), 1.5))
            p.setBrush(QColor("#EF4444"))
            dr_px = max(4.0, self.drain_d * scale)
            # Agujero superior e inferior
            p.drawEllipse(int(cx + pw / 2.0 - dr_px / 2.0), int(cy - dr_px / 2.0), int(dr_px), int(dr_px))
            p.drawEllipse(int(cx + pw / 2.0 - dr_px / 2.0), int(cy + ph - dr_px / 2.0), int(dr_px), int(dr_px))

        # Texto informativo en esquina
        p.setPen(QColor("#94A3B8"))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(8, h - 8, f"{self.dx:.0f}x{self.dy:.0f} mm | Celda: {self.cell_size:.1f} mm")


class LatticeDialog(QDialog):
    """Diálogo interactivo para el generador de estructuras aligeradas y TPMS Gyroid."""

    def __init__(self, parent=None,
                 target_node: Optional[Node] = None,
                 target_code: Optional[str] = None,
                 target_bbox: Optional[tuple[float, float, float, float, float, float]] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Generador de estructuras aligeradas & Gyroid TPMS"))
        self.resize(840, 600)
        self.setMinimumSize(700, 500)

        self.target_node = target_node
        self.target_code = target_code
        self.target_bbox = target_bbox or (60.0, 40.0, 30.0, 0.0, 0.0, 0.0)
        self.target_name = (target_node.name or target_node.kind) if target_node else ""
        self.has_target = bool(target_node and target_code)

        init_dx, init_dy, init_dz = self.target_bbox[0], self.target_bbox[1], self.target_bbox[2]

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(14, 14, 14, 14)
        main_lay.setSpacing(10)

        # Encabezado
        head = QHBoxLayout()
        lbl_icon = QLabel("🧬")
        lbl_icon.setStyleSheet("font-size: 26px; padding: 2px;")
        head.addWidget(lbl_icon)

        head_text = QVBoxLayout()
        title = QLabel(f"<b>{tr('Estructuras aligeradas, Lattice y Superficies Matemáticas Gyroid')}</b>")
        title.setStyleSheet("font-size: 14px;")
        sub = QLabel(tr("Reduce el peso y consumo de material manteniendo alta rigidez con geometrías mínimas periódicas."))
        sub.setStyleSheet(themed("color: #64748B; font-size: 11px;"))
        head_text.addWidget(title)
        head_text.addWidget(sub)
        head.addLayout(head_text, 1)
        main_lay.addLayout(head)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Panel izquierdo: Parámetros en ScrollArea
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_widget = QWidget()
        left_lay = QVBoxLayout(left_widget)
        left_lay.setSpacing(10)
        left_lay.setContentsMargins(0, 0, 8, 0)

        # 0. Destino de la estructura (si hay un sólido seleccionado)
        if self.has_target:
            grp_dest = QGroupBox(tr("Destino de la estructura"))
            lay_dest = QVBoxLayout(grp_dest)
            lay_dest.setSpacing(6)

            self.radio_apply = QRadioButton(
                tr("Aplicar al sólido seleccionado ({name})").format(name=self.target_name)
            )
            self.radio_apply.setChecked(True)
            self.radio_apply.toggled.connect(self._on_dest_mode_changed)
            lay_dest.addWidget(self.radio_apply)

            self.radio_new = QRadioButton(tr("Crear nuevo bloque independiente"))
            self.radio_new.toggled.connect(self._on_dest_mode_changed)
            lay_dest.addWidget(self.radio_new)

            self.lbl_target_info = QLabel(
                tr("La estructura aligerada reemplazará al sólido seleccionado '{name}', manteniendo su contorno y ahuecando su interior con el patrón celular.").format(name=self.target_name)
            )
            self.lbl_target_info.setWordWrap(True)
            self.lbl_target_info.setStyleSheet(themed("font-size: 11px; color: #475569; padding: 2px 0;"))
            lay_dest.addWidget(self.lbl_target_info)

            left_lay.addWidget(grp_dest)

        # 1. Patrón
        grp_pat = QGroupBox(tr("Tipo de patrón celular"))
        form_pat = QFormLayout(grp_pat)
        self.combo_pattern = QComboBox()
        self.combo_pattern.addItem(tr("Giroide (Gyroid TPMS - Isotropía 3D)"), "gyroid")
        self.combo_pattern.addItem(tr("Schwarz P (TPMS - Canales ortogonales)"), "schwarz_p")
        self.combo_pattern.addItem(tr("Panal de abeja (Honeycomb - Compresión Z)"), "honeycomb")
        self.combo_pattern.addItem(tr("Voronoi 3D (Celular biomimético)"), "voronoi")
        self.combo_pattern.currentIndexChanged.connect(self._recalc)
        form_pat.addRow(tr("Patrón:"), self.combo_pattern)
        left_lay.addWidget(grp_pat)

        # 2. Dimensiones
        grp_dim = QGroupBox(tr("Dimensiones externas (mm)"))
        form_dim = QFormLayout(grp_dim)
        self.spin_dx = self._spin(1.0, 1000.0, init_dx, " mm")
        self.spin_dy = self._spin(1.0, 1000.0, init_dy, " mm")
        self.spin_dz = self._spin(1.0, 1000.0, init_dz, " mm")
        form_dim.addRow(tr("Ancho (X):"), self.spin_dx)
        form_dim.addRow(tr("Largo (Y):"), self.spin_dy)
        form_dim.addRow(tr("Alto (Z):"), self.spin_dz)
        left_lay.addWidget(grp_dim)

        # 3. Lattice
        grp_lat = QGroupBox(tr("Parámetros del reticulado"))
        form_lat = QFormLayout(grp_lat)
        self.spin_cell = self._spin(2.0, 50.0, 10.0, " mm", step=0.5)
        self.spin_wall = self._spin(0.4, 10.0, 1.2, " mm", step=0.2)
        form_lat.addRow(tr("Tamaño celda (λ):"), self.spin_cell)
        form_lat.addRow(tr("Espesor pared (t):"), self.spin_wall)
        left_lay.addWidget(grp_lat)

        # 4. Fabricación y Piel
        grp_fab = QGroupBox(tr("Fabricación aditiva y acabado"))
        form_fab = QFormLayout(grp_fab)
        self.chk_shell = QCheckBox(tr("Piel sólida exterior (Solid Skin)"))
        self.chk_shell.setChecked(True)
        self.chk_shell.toggled.connect(self._on_shell_toggled)
        self.spin_shell = self._spin(0.4, 10.0, 1.6, " mm", step=0.2)

        self.chk_drain = QCheckBox(tr("Orificios de drenaje (Resina SLA / SLS)"))
        self.chk_drain.setChecked(False)
        self.chk_drain.toggled.connect(self._on_drain_toggled)
        self.spin_drain = self._spin(1.0, 20.0, 4.0, " mm", step=0.5)
        self.spin_drain.setEnabled(False)

        form_fab.addRow(self.chk_shell)
        form_fab.addRow(tr("Espesor de piel:"), self.spin_shell)
        form_fab.addRow(self.chk_drain)
        form_fab.addRow(tr("Diámetro orificios:"), self.spin_drain)
        left_lay.addWidget(grp_fab)

        # 5. Material
        grp_mat = QGroupBox(tr("Material y densidad"))
        form_mat = QFormLayout(grp_mat)
        self.combo_mat = QComboBox()
        for key, (label, dens) in lattice.MATERIALS.items():
            self.combo_mat.addItem(f"{label} ({dens:.2f} g/cm³)", key)
        self.combo_mat.currentIndexChanged.connect(self._recalc)
        form_mat.addRow(tr("Material:"), self.combo_mat)
        left_lay.addWidget(grp_mat)

        left_lay.addStretch(1)
        left_scroll.setWidget(left_widget)
        left_scroll.setMinimumWidth(300)
        splitter.addWidget(left_scroll)

        # Panel derecho: Métricas y Vista previa
        right_box = QWidget()
        right_lay = QVBoxLayout(right_box)
        right_lay.setContentsMargins(8, 0, 0, 0)
        right_lay.setSpacing(10)

        # Tarjeta de Métricas
        self.card_metrics = QFrame()
        self.card_metrics.setStyleSheet(themed(
            "QFrame { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 6px; }"
        ))
        card_lay = QVBoxLayout(self.card_metrics)
        card_lay.setSpacing(4)

        top_metric = QHBoxLayout()
        self.lbl_saving_badge = QLabel(tr("Ahorro estimado: -64%"))
        self.lbl_saving_badge.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #047857; background: #D1FAE5; "
            "padding: 4px 8px; border-radius: 6px; border: 1px solid #A7F3D0;"
        )
        top_metric.addWidget(self.lbl_saving_badge)
        top_metric.addStretch(1)
        card_lay.addLayout(top_metric)

        self.lbl_details = QLabel()
        self.lbl_details.setStyleSheet(themed("font-size: 11px; color: #334155; line-height: 1.4;"))
        card_lay.addWidget(self.lbl_details)
        right_lay.addWidget(self.card_metrics)

        # Tabs: Esquema 2D y Código OpenSCAD
        tabs = QTabWidget()
        self.preview_widget = LatticeSlicePreview()
        tabs.addTab(self.preview_widget, tr("Esquema 2D / Corte"))

        self.code_view = QPlainTextEdit()
        self.code_view.setReadOnly(True)
        self.code_view.setStyleSheet(themed(
            "font-family: monospace; font-size: 11px; background: #F1F5F9; "
            "border: 1px solid #CBD5E1; border-radius: 4px; padding: 6px;"
        ))
        tabs.addTab(self.code_view, tr("Código OpenSCAD"))
        right_lay.addWidget(tabs, 1)

        splitter.addWidget(right_box)
        splitter.setSizes([320, 520])
        main_lay.addWidget(splitter, 1)

        # Botones inferiores
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)

        btn_copy = QPushButton(tr("Copiar código OpenSCAD"))
        btn_copy.clicked.connect(self._copy_code)
        btn_bar.addWidget(btn_copy)

        btn_bar.addStretch(1)

        btn_cancel = QPushButton(tr("Cerrar"))
        btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(btn_cancel)

        initial_btn_text = tr("Aplicar al sólido") if self.has_target else tr("Insertar en el modelo")
        self.btn_insert = QPushButton(initial_btn_text)
        self.btn_insert.setDefault(True)
        self.btn_insert.setStyleSheet("font-weight: bold;")
        self.btn_insert.clicked.connect(self.accept)
        btn_bar.addWidget(self.btn_insert)

        main_lay.addLayout(btn_bar)

        self._recalc()

    def _spin(self, v_min: float, v_max: float, v_val: float, suffix: str, step: float = 1.0) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(v_min, v_max)
        sp.setValue(v_val)
        sp.setSingleStep(step)
        sp.setSuffix(suffix)
        sp.valueChanged.connect(self._recalc)
        return sp

    def _on_dest_mode_changed(self) -> None:
        if not self.has_target:
            return
        is_apply = self.radio_apply.isChecked()
        self.lbl_target_info.setVisible(is_apply)
        if is_apply:
            self.btn_insert.setText(tr("Aplicar al sólido"))
            self.spin_dx.setValue(self.target_bbox[0])
            self.spin_dy.setValue(self.target_bbox[1])
            self.spin_dz.setValue(self.target_bbox[2])
        else:
            self.btn_insert.setText(tr("Insertar en el modelo"))
        self._recalc()

    def _on_shell_toggled(self, checked: bool) -> None:
        self.spin_shell.setEnabled(checked)
        self._recalc()

    def _on_drain_toggled(self, checked: bool) -> None:
        self.spin_drain.setEnabled(checked)
        self._recalc()

    def _recalc(self) -> None:
        dx = self.spin_dx.value()
        dy = self.spin_dy.value()
        dz = self.spin_dz.value()
        cell = self.spin_cell.value()
        wall = self.spin_wall.value()
        pat = str(self.combo_pattern.currentData())
        shell = self.chk_shell.isChecked()
        s_thick = self.spin_shell.value()
        drain = self.chk_drain.isChecked()
        d_hole = self.spin_drain.value()
        mat_key = str(self.combo_mat.currentData())

        m = lattice.estimate_metrics(dx, dy, dz, cell, wall, shell, s_thick, drain, d_hole, mat_key)

        mat_label, _ = lattice.MATERIALS.get(mat_key, (mat_key.upper(), 1.0))
        self.lbl_saving_badge.setText(tr("Ahorro estimado: -{pct:.0f}% peso").format(pct=m["savings_pct"]))

        self.lbl_details.setText(
            f"<b>{tr('Masa sólida original:')}</b> {m['solid_mass_g']:.1f} g &nbsp;|&nbsp; "
            f"<b>{tr('Masa aligerada:')}</b> <span style='color: #047857; font-weight: bold;'>{m['lattice_mass_g']:.1f} g</span><br>"
            f"<b>{tr('Densidad relativa infill:')}</b> {m['relative_density_pct']:.1f}% &nbsp;|&nbsp; "
            f"<b>{tr('Material:')}</b> {mat_label}"
        )

        is_apply = bool(self.has_target and self.radio_apply.isChecked())
        solid_code = self.target_code if is_apply else None
        solid_name = self.target_name if is_apply else ""
        cx = self.target_bbox[3] if is_apply else 0.0
        cy = self.target_bbox[4] if is_apply else 0.0
        cz = self.target_bbox[5] if is_apply else 0.0

        code = lattice.generate_scad_code(
            dx, dy, dz, cell, wall, pat, shell, s_thick, drain, d_hole,
            cx=cx, cy=cy, cz=cz, solid_code=solid_code, solid_name=solid_name
        )
        self.code_view.setPlainText(code)

        self.preview_widget.update_params(dx, dy, cell, wall, pat, shell, s_thick, drain, d_hole)

    def _copy_code(self) -> None:
        QApplication.clipboard().setText(self.code_view.toPlainText())

    def get_result(self) -> dict:
        is_apply = bool(self.has_target and self.radio_apply.isChecked())
        return {
            "dx": self.spin_dx.value(),
            "dy": self.spin_dy.value(),
            "dz": self.spin_dz.value(),
            "cx": self.target_bbox[3] if is_apply else 0.0,
            "cy": self.target_bbox[4] if is_apply else 0.0,
            "cz": self.target_bbox[5] if is_apply else 0.0,
            "cell_size": self.spin_cell.value(),
            "wall_thick": self.spin_wall.value(),
            "pattern": str(self.combo_pattern.currentData()),
            "has_shell": self.chk_shell.isChecked(),
            "shell_thick": self.spin_shell.value(),
            "has_drain": self.chk_drain.isChecked(),
            "drain_d": self.spin_drain.value(),
            "code": self.code_view.toPlainText(),
            "apply_to_selected": is_apply,
            "target_name": self.target_name if is_apply else "",
            "target_code": self.target_code if is_apply else None,
            "selected_id": self.target_node.id if (is_apply and self.target_node) else None,
        }
