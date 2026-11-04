"""Calculadora de transmisiones: busca los dientes de los engranajes, o las poleas y la correa, para una
relación y genera las piezas. La lógica está en transmission.py."""

from __future__ import annotations

import html

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from .. import gears
from .. import transmission as tm
from ..catalog import SPECS
from ..i18n import tr
from .style import themed

DRIVES = ("gears", "pulley", "v_pulley")


def _spin(value: float, low: float, high: float, step: float = 1.0, suffix: str = " mm",
          decimals: int = 2) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(low, high)
    s.setDecimals(decimals)
    s.setSingleStep(step)
    s.setValue(value)
    s.setSuffix(suffix)
    return s


def _int(value: int, low: int, high: int) -> QSpinBox:
    s = QSpinBox()
    s.setRange(low, high)
    s.setValue(value)
    return s


class TransmissionDialog(QDialog):
    """Requisito (por engranajes o correa, relación o velocidades) y, según el tipo, los límites y las
    piezas a la izquierda; las soluciones a la derecha, ordenadas por error. La elegida se genera ya
    colocada."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Calculadora de transmisión"))
        self.resize(1000, 680)
        self.solutions: list = []
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        layout.addLayout(row, 1)
        left = QVBoxLayout()
        row.addLayout(left)

        # --- requisito, común a los tres tipos
        need = QGroupBox(tr("Requisito"))
        f = QFormLayout(need)
        self.combo_drive = QComboBox()
        self.combo_drive.addItem(tr("Engranajes"), "gears")
        self.combo_drive.addItem(tr("Correa dentada"), "pulley")
        self.combo_drive.addItem(tr("Correa en V"), "v_pulley")
        self.combo_mode = QComboBox()
        self.combo_mode.addItem(tr("Relación"), "ratio")
        self.combo_mode.addItem(tr("Velocidades (rpm)"), "rpm")
        self.spin_ratio = _spin(3.75, 0.01, 10000, 0.25, "", 4)
        self.spin_in = _spin(1500, 0.01, 1e6, 50, " rpm")
        self.spin_out = _spin(400, 0.01, 1e6, 10, " rpm")
        self.spin_tol = _spin(1, 0, 20, 0.1, " %")
        f.addRow(tr("Transmisión por"), self.combo_drive)
        f.addRow(tr("Dato"), self.combo_mode)
        self.label_ratio = QLabel(tr("Relación (entrada : salida)"))
        f.addRow(self.label_ratio, self.spin_ratio)
        self.label_in = QLabel(tr("Entrada"))
        f.addRow(self.label_in, self.spin_in)
        self.label_out = QLabel(tr("Salida"))
        f.addRow(self.label_out, self.spin_out)
        f.addRow(tr("Tolerancia"), self.spin_tol)
        left.addWidget(need)

        # --- engranajes
        self.box_gears = QGroupBox(tr("Engranajes"))
        g = QFormLayout(self.box_gears)
        self.combo_kind = QComboBox()
        for kind in tm.KINDS:
            self.combo_kind.addItem(tr(SPECS[kind].label), kind)
        self.combo_stages = QComboBox()
        self.combo_stages.addItem(tr("Una"), 1)
        self.combo_stages.addItem(tr("Dos (tren compuesto)"), 2)
        self.check_coaxial = QCheckBox(tr("Entrada y salida en el mismo eje (tren revertido)"))
        self.spin_zmin = _int(18, 3, 400)
        self.spin_zmax = _int(100, 3, 400)
        self.spin_center = _spin(0, 0, 100000, 5)
        self.spin_center.setSpecialValueText(tr("sin límite"))
        self.spin_mod = _spin(1, 0.05, 50, 0.25, "")
        self.spin_pressure = _spin(20, 10, 35, 0.5, "°")
        self.spin_helix = _spin(20, 1, 45, 1, "°")
        self.spin_thick = _spin(6, 0.1, 1000, 1)
        self.spin_backlash = _spin(0.1, 0, 2, 0.05)
        self.spin_bore = _spin(5, 0, 1000, 0.5)
        self.spin_bore.setSpecialValueText(tr("sin agujero"))
        self.spin_gap = _spin(1, 0, 1000, 0.5)
        g.addRow(tr("Tipo"), self.combo_kind)
        g.addRow(tr("Etapas"), self.combo_stages)
        g.addRow(self.check_coaxial)
        g.addRow(tr("Dientes mínimos"), self.spin_zmin)
        g.addRow(tr("Dientes máximos"), self.spin_zmax)
        g.addRow(tr("Distancia entre centros máx."), self.spin_center)
        g.addRow(tr("Módulo (m)"), self.spin_mod)
        g.addRow(tr("Ángulo de presión (°)"), self.spin_pressure)
        self.label_helix = QLabel(tr("Ángulo de hélice (°)"))
        g.addRow(self.label_helix, self.spin_helix)
        g.addRow(tr("Grueso"), self.spin_thick)
        g.addRow(tr("Holgura (mm)"), self.spin_backlash)
        g.addRow(tr("Agujero (Ø)"), self.spin_bore)
        self.label_gap = QLabel(tr("Separación entre etapas"))
        g.addRow(self.label_gap, self.spin_gap)
        left.addWidget(self.box_gears)

        # --- correa dentada
        self.box_timing = QGroupBox(tr("Correa dentada"))
        t = QFormLayout(self.box_timing)
        self.combo_tsection = QComboBox()
        for name in gears.PULLEY_SECTIONS:
            self.combo_tsection.addItem(name, name)
        self.combo_tsection.setCurrentIndex(1)                    # XL
        self.spin_tzmin = _int(10, 3, 400)
        self.spin_tzmax = _int(80, 3, 400)
        self.spin_tcenter = _spin(0, 0, 100000, 5)
        self.spin_tcenter.setSpecialValueText(tr("automática"))
        self.spin_twidth = _spin(8, 0.1, 1000, 1)
        self.combo_flange = QComboBox()
        for option in SPECS["pulley"].param("flange").options:
            self.combo_flange.addItem(tr(option), option)
        self.combo_flange.setCurrentIndex(3)                      # ambas: la correa no se sale
        self.spin_tbore = _spin(5, 0, 1000, 0.5)
        self.spin_tbore.setSpecialValueText(tr("sin agujero"))
        self.check_tbelt = QCheckBox(tr("Añadir la correa (como referencia)"))
        self.check_tbelt.setChecked(True)
        t.addRow(tr("Sección"), self.combo_tsection)
        t.addRow(tr("Dientes mínimos"), self.spin_tzmin)
        t.addRow(tr("Dientes máximos"), self.spin_tzmax)
        t.addRow(tr("Distancia entre centros aprox."), self.spin_tcenter)
        t.addRow(tr("Ancho (correa)"), self.spin_twidth)
        t.addRow(tr("Pestañas"), self.combo_flange)
        t.addRow(tr("Agujero (Ø)"), self.spin_tbore)
        t.addRow(self.check_tbelt)
        left.addWidget(self.box_timing)

        # --- correa en V
        self.box_v = QGroupBox(tr("Correa en V"))
        v = QFormLayout(self.box_v)
        self.combo_vsection = QComboBox()
        for name in gears.V_BELT_SECTIONS:
            self.combo_vsection.addItem(name, name)
        self.spin_dmin = _spin(0, 0, 5000, 5)
        self.spin_dmin.setSpecialValueText(tr("el recomendado"))
        self.spin_dmax = _spin(400, 10, 5000, 10)
        self.spin_dstep = _spin(5, 0.5, 100, 0.5)
        self.spin_vcenter = _spin(0, 0, 100000, 5)
        self.spin_vcenter.setSpecialValueText(tr("automática"))
        self.spin_vlength = _spin(0, 0, 100000, 10)
        self.spin_vlength.setSpecialValueText(tr("la que salga"))
        self.spin_grooves = _int(1, 1, 20)
        self.spin_vbore = _spin(12, 0, 1000, 0.5)
        self.spin_vbore.setSpecialValueText(tr("sin agujero"))
        self.check_vbelt = QCheckBox(tr("Añadir la correa (como referencia)"))
        self.check_vbelt.setChecked(True)
        v.addRow(tr("Sección"), self.combo_vsection)
        v.addRow(tr("Ø mínimo"), self.spin_dmin)
        v.addRow(tr("Ø máximo"), self.spin_dmax)
        v.addRow(tr("Paso de diámetros"), self.spin_dstep)
        v.addRow(tr("Distancia entre centros aprox."), self.spin_vcenter)
        v.addRow(tr("Longitud de correa"), self.spin_vlength)
        v.addRow(tr("Ranuras"), self.spin_grooves)
        v.addRow(tr("Agujero (Ø)"), self.spin_vbore)
        v.addRow(self.check_vbelt)
        left.addWidget(self.box_v)
        left.addStretch(1)

        right = QVBoxLayout()
        row.addLayout(right, 1)
        self.table = QTableWidget(0, 5)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._show_selected)
        self.table.itemDoubleClicked.connect(lambda _item: self.btn_insert.isEnabled() and self.accept())
        right.addWidget(self.table, 1)
        self.lbl_info = QLabel()
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_info.setStyleSheet(themed("color: #3D4756; font-size: 11px;"))
        right.addWidget(self.lbl_info)

        buttons = QHBoxLayout()
        self.btn_insert = QPushButton()
        self.btn_insert.setObjectName("primary")
        self.btn_insert.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("Cancelar"))
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_insert)
        layout.addLayout(buttons)

        # La búsqueda de dos etapas tarda unas décimas: se lanza cuando se deja de teclear.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.refresh)
        for w in (self.spin_ratio, self.spin_in, self.spin_out, self.spin_tol, self.spin_zmin, self.spin_zmax,
                  self.spin_center, self.spin_mod, self.spin_helix, self.spin_tzmin, self.spin_tzmax,
                  self.spin_tcenter, self.spin_dmin, self.spin_dmax, self.spin_dstep, self.spin_vcenter,
                  self.spin_vlength):
            w.valueChanged.connect(self._schedule)
        for w in (self.spin_pressure, self.spin_helix):
            w.valueChanged.connect(self._suggest_min_teeth)
        for c in (self.combo_mode, self.combo_stages, self.combo_drive, self.combo_tsection, self.combo_vsection):
            c.currentIndexChanged.connect(self._schedule)
        self.combo_kind.currentIndexChanged.connect(self._on_kind)
        self.check_coaxial.toggled.connect(self._schedule)
        for w in (self.spin_thick, self.spin_backlash, self.spin_bore, self.spin_gap, self.spin_twidth,
                  self.spin_tbore, self.spin_grooves, self.spin_vbore):
            w.valueChanged.connect(self._show_selected)
        self._sync_visibility()
        self.refresh()

    # ------------------------------------------------------------------ datos
    def drive(self) -> str:
        return self.combo_drive.currentData()

    def kind(self) -> str:
        return self.combo_kind.currentData()

    def helix(self) -> float:
        return self.spin_helix.value() if self.kind() in tm.HELICAL else 0.0

    def ratio(self) -> float:
        if self.combo_mode.currentData() == "rpm":
            return tm.ratio_from_speeds(self.spin_in.value(), self.spin_out.value())
        return self.spin_ratio.value()

    def rpm_in(self) -> float:
        return self.spin_in.value() if self.combo_mode.currentData() == "rpm" else 0.0

    def stages(self) -> int:
        return int(self.combo_stages.currentData() or 1)

    def coaxial(self) -> bool:
        return self.stages() == 2 and self.check_coaxial.isChecked()

    def params(self) -> dict:
        if self.drive() == "pulley":
            return {"width": self.spin_twidth.value(), "bore": self.spin_tbore.value(),
                    "flange": self.combo_flange.currentData()}
        if self.drive() == "v_pulley":
            return {"grooves": self.spin_grooves.value(), "bore": self.spin_vbore.value()}
        p = {"mod": self.spin_mod.value(), "pressure_angle": self.spin_pressure.value(),
             "thickness": self.spin_thick.value(), "backlash": self.spin_backlash.value()}
        if self.spin_bore.value() > 0:
            p["bore"] = self.spin_bore.value()
        if self.kind() in tm.HELICAL:
            p["helix_angle"] = self.spin_helix.value()
        return p

    def selected(self):
        rows = self.table.selectionModel().selectedRows()
        return self.solutions[rows[0].row()] if rows and rows[0].row() < len(self.solutions) else None

    def get_result(self) -> dict:
        belt = self.check_tbelt.isChecked() if self.drive() == "pulley" else self.check_vbelt.isChecked()
        return {"drive": self.drive(), "solution": self.selected(), "kind": self.kind(), "params": self.params(),
                "stage_gap": self.spin_gap.value(), "coaxial": self.coaxial(), "belt": belt}

    # ------------------------------------------------------------------ reacciones
    def _schedule(self, *_args) -> None:
        self._sync_visibility()
        self._timer.start()

    def _on_kind(self, *_args) -> None:
        # Un espina de pescado necesita más grueso que un recto (dos mitades helicoidales).
        self.spin_thick.setValue({"spur_gear": 6, "helical_gear": 10, "herringbone_gear": 16}[self.kind()])
        self._suggest_min_teeth()
        self._schedule()

    def _suggest_min_teeth(self, *_args) -> None:
        self.spin_zmin.setValue(tm.default_min_teeth(self.kind(), self.helix(), self.spin_pressure.value()))

    def _sync_visibility(self) -> None:
        rpm = self.combo_mode.currentData() == "rpm"
        for w in (self.label_ratio, self.spin_ratio):
            w.setVisible(not rpm)
        for w in (self.label_in, self.spin_in, self.label_out, self.spin_out):
            w.setVisible(rpm)
        drive = self.drive()
        self.box_gears.setVisible(drive == "gears")
        self.box_timing.setVisible(drive == "pulley")
        self.box_v.setVisible(drive == "v_pulley")
        helical = self.kind() in tm.HELICAL
        self.label_helix.setVisible(helical)
        self.spin_helix.setVisible(helical)
        two = self.stages() == 2
        self.check_coaxial.setEnabled(two)
        self.label_gap.setVisible(two)
        self.spin_gap.setVisible(two)
        self.btn_insert.setText(tr("Generar engranajes") if drive == "gears" else tr("Generar poleas"))
        if drive == "gears":
            heads = [tr("Dientes"), tr("Relación"), tr("Error"), tr("Distancia entre centros"), tr("Ø primitivos")]
        else:
            heads = [tr("Poleas"), tr("Relación"), tr("Error"), tr("Distancia entre centros"), tr("Correa"),
                     tr("Abrazamiento")]
        self.table.setColumnCount(len(heads))
        self.table.setHorizontalHeaderLabels(heads)

    def _search(self) -> list:
        drive = self.drive()
        if drive == "pulley":
            return tm.search_timing(self.ratio(), self.spin_tol.value(), self.combo_tsection.currentData(),
                                    self.spin_tzmin.value(), self.spin_tzmax.value(), self.spin_tcenter.value())
        if drive == "v_pulley":
            return tm.search_v(self.ratio(), self.spin_tol.value(), self.combo_vsection.currentData(),
                               self.spin_dmin.value(), self.spin_dmax.value(), self.spin_dstep.value(),
                               self.spin_vcenter.value(), self.spin_vlength.value())
        return tm.search(self.ratio(), self.spin_tol.value(), self.stages(), self.spin_zmin.value(),
                         self.spin_zmax.value(), self.kind(), self.spin_mod.value(), self.helix(),
                         self.spin_center.value(), self.coaxial())

    def _cells(self, sol) -> tuple:
        if isinstance(sol, tm.BeltSolution):
            if sol.kind == "pulley":
                pulleys = f"{int(sol.driver)}/{int(sol.driven)}"
                belt = tr("{n} dientes · {l:.1f} mm").format(n=sol.belt_teeth, l=sol.length)
            else:
                pulleys = "Ø {:g}/{:g}".format(sol.driver, sol.driven)
                belt = f"{sol.length:.1f} mm"
            return (pulleys, f"{sol.ratio:.5g}", f"{sol.error * 100:+.3f} %", f"{sol.center:.2f}", belt,
                    f"{sol.wrap:.0f}°")
        teeth = "  ·  ".join(f"{a}/{b}" for a, b in sol.stages)
        diam = "  ·  ".join("{:g}/{:g}".format(round(tm.pitch_d(self.kind(), self.spin_mod.value(), a, self.helix()), 2),
                                               round(tm.pitch_d(self.kind(), self.spin_mod.value(), b, self.helix()), 2))
                            for a, b in sol.stages)
        return (teeth, f"{sol.ratio:.5g}", f"{sol.error * 100:+.3f} %",
                "  ·  ".join(f"{c:.2f}" for c in sol.centers), diam)

    def refresh(self) -> None:
        """Vuelve a buscar y rellena la tabla."""
        self._timer.stop()
        self._sync_visibility()
        self.table.setRowCount(0)
        try:
            self.solutions = self._search()
        except ValueError as exc:
            self.solutions = []
            self._message(str(exc), error=True)
            return
        for sol in self.solutions:
            r = self.table.rowCount()
            self.table.insertRow(r)
            shared = isinstance(sol, tm.Solution) and not all(sol.hunting)
            for col, text in enumerate(self._cells(sol)):
                item = QTableWidgetItem(text)
                if col:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if shared:
                    item.setToolTip(tr("Dientes con divisores comunes: el desgaste no se reparte"))
                self.table.setItem(r, col, item)
        if self.solutions:
            self.table.selectRow(0)
        elif self.drive() == "gears":
            self._message(tr("Ninguna combinación cumple la relación dentro de la tolerancia. Prueba con más "
                             "tolerancia, más dientes máximos o dos etapas."), error=True)
        else:
            self._message(tr("Ninguna pareja de poleas cumple la relación dentro de la tolerancia. Prueba con más "
                             "tolerancia, otros límites o una distancia entre centros mayor."), error=True)

    def _message(self, text: str, error: bool = False) -> None:
        color = "#B42318" if error else "#3D4756"
        self.lbl_info.setText(themed(f"<span style='color: {color};'>{html.escape(text)}</span>"))
        self.btn_insert.setEnabled(False)

    def _belt_lines(self, sol: tm.BeltSolution) -> list[str]:
        d1, d2 = sol.diameters
        lines = [tr("Ø primitivos {a:.2f} y {b:.2f} mm, a {c:.2f} mm entre centros.").format(a=d1, b=d2, c=sol.center)]
        if sol.kind == "pulley":
            lines.append(tr("Correa {s} de {n} dientes ({l:.1f} mm); abraza {m:.1f} dientes de la polea "
                            "pequeña.").format(s=sol.section, n=sol.belt_teeth, l=sol.length, m=sol.mesh_teeth))
        elif self.spin_vlength.value() > 0:
            lines.append(tr("Con la correa de {l:.1f} mm de longitud primitiva.").format(l=sol.length))
        else:
            lines.append(tr("Longitud primitiva de la correa: {l:.1f} mm. Pon la de tu catálogo en «Longitud de "
                            "correa» y se recalcula la distancia.").format(l=sol.length))
        if self.rpm_in() > 0:
            lines.append(tr("La correa va a {v:.2f} m/s.").format(v=3.141592653589793 * d1 * self.rpm_in() / 60000))
        return lines

    def _show_selected(self, *_args) -> None:
        sol = self.selected()
        if sol is None:
            if self.solutions:
                self._message(tr("Elige una solución de la tabla."))
            return
        lines = [tr("Relación real {r:.5g}:1 (error {e:+.3f} %).").format(r=sol.ratio, e=sol.error * 100)]
        if self.rpm_in() > 0:
            lines.append(tr("Salida a {v:.4g} rpm con la entrada a {i:.4g} rpm.").format(
                v=self.spin_in.value() / sol.ratio, i=self.spin_in.value()))
        if isinstance(sol, tm.BeltSolution):
            lines += self._belt_lines(sol)
            bore = self.spin_tbore.value() if sol.kind == "pulley" else self.spin_vbore.value()
            notes = tm.belt_notes(sol, self.rpm_in(), bore)
        else:
            names = ([tr("Motriz"), tr("Conducido")] if len(sol.stages) == 1 else
                     [tr("Motriz"), tr("Intermedio 1"), tr("Intermedio 2"), tr("Salida")])
            teeth = [z for st in sol.stages for z in st]
            lines.append(", ".join(tr("{name}: {z} dientes").format(name=n, z=z) for n, z in zip(names, teeth)))
            if self.coaxial():
                lines.append(tr("La salida queda en el eje de la entrada; el eje intermedio, a {a:.2f} mm.").format(
                    a=sol.centers[0]))
            notes = tm.notes(sol, self.kind(), self.helix(), self.spin_pressure.value())
        txt = "<br>".join(html.escape(line) for line in lines)
        for text, data in notes:
            txt += "<br><span style='color: #B54708;'>{}</span>".format(html.escape(tr(text).format(**data)))
        self.lbl_info.setText(themed(txt))
        self.btn_insert.setEnabled(True)
