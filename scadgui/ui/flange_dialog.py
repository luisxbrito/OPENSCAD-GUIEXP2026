"""Asistente de bridas normalizadas (ASME B16.5 y EN 1092-1). Los datos y cálculos están en flanges.py."""

from __future__ import annotations

import html

from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout)

from .. import flanges
from ..i18n import tr
from .style import themed


class FlangeDialog(QDialog):
    """Norma, clase o PN, tipo, tamaño y cara; la ficha muestra las medidas que tendrá la pieza.
    Si la norma deja el agujero al comprador, hay que escribirlo antes de insertar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Insertar brida normalizada"))
        self.resize(520, 520)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        group = QGroupBox(tr("Brida"))
        form = QFormLayout(group)
        self.combo_standard = QComboBox()
        for std in flanges.STANDARDS:
            self.combo_standard.addItem(flanges.STANDARD_NAMES[std], std)
        self.combo_rating = QComboBox()
        self.combo_type = QComboBox()
        self.combo_size = QComboBox()
        self.combo_facing = QComboBox()
        for facing in flanges.FACINGS:
            self.combo_facing.addItem(flanges.facing_name(facing), facing)
        self.spin_bore = QDoubleSpinBox()
        self.spin_bore.setRange(0.0, 5000.0)
        self.spin_bore.setDecimals(2)
        self.spin_bore.setSuffix(" mm")
        self.label_rating = QLabel()
        form.addRow(tr("Norma:"), self.combo_standard)
        form.addRow(self.label_rating, self.combo_rating)
        form.addRow(tr("Tipo:"), self.combo_type)
        form.addRow(tr("Tamaño:"), self.combo_size)
        form.addRow(tr("Cara:"), self.combo_facing)
        self.label_bore = QLabel(tr("Agujero (Ø interior del tubo):"))
        form.addRow(self.label_bore, self.spin_bore)
        layout.addWidget(group)

        info_group = QGroupBox(tr("Medidas de la norma"))
        info_lay = QVBoxLayout(info_group)
        self.lbl_info = QLabel()
        self.lbl_info.setStyleSheet(themed("color: #3D4756; font-size: 11px;"))
        self.lbl_info.setWordWrap(True)
        info_lay.addWidget(self.lbl_info)
        layout.addWidget(info_group)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        self.btn_insert = QPushButton(tr("Insertar brida"))
        self.btn_insert.setObjectName("primary")
        self.btn_insert.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("Cancelar"))
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_insert)
        layout.addLayout(buttons)

        self.combo_standard.currentIndexChanged.connect(self._on_standard_changed)
        self.combo_rating.currentIndexChanged.connect(self._fill_sizes)
        self.combo_type.currentIndexChanged.connect(self._fill_sizes)
        self.combo_facing.currentIndexChanged.connect(self._fill_sizes)
        self.combo_size.currentIndexChanged.connect(self._on_size_changed)
        self.spin_bore.valueChanged.connect(self._update_info)
        self._on_standard_changed()

    # --------------------------------------------------------------- selección

    def standard(self) -> str:
        return str(self.combo_standard.currentData() or flanges.STANDARDS[0])

    def _refill(self, combo: QComboBox, items, keep) -> None:
        combo.blockSignals(True)
        combo.clear()
        for text, data in items:
            combo.addItem(text, data)
        combo.setCurrentIndex(max(0, combo.findData(keep)))
        combo.blockSignals(False)

    def _on_standard_changed(self) -> None:
        std = self.standard()
        self.label_rating.setText(tr("Clase:") if std == "asme_b16_5" else tr("Presión (PN):"))
        default_rating = "150" if std == "asme_b16_5" else "16"
        self._refill(self.combo_rating, [(flanges.rating_label(std, r), r) for r in flanges.ratings(std)],
                     self.combo_rating.currentData() or default_rating)
        if self.combo_rating.currentData() not in flanges.ratings(std):
            self.combo_rating.setCurrentIndex(max(0, self.combo_rating.findData(default_rating)))
        names = [(tr("{name} (tipo {n})").format(name=flanges.type_name(t), n=flanges.EN_TYPE_NUMBERS[t])
                  if std == "en_1092_1" else flanges.type_name(t), t) for t in flanges.TYPES[std]]
        self._refill(self.combo_type, names, self.combo_type.currentData() or "weld_neck")
        self._fill_sizes()

    def _fill_sizes(self) -> None:
        std = self.standard()
        rating = str(self.combo_rating.currentData())
        ftype = str(self.combo_type.currentData())
        facing = str(self.combo_facing.currentData())
        keep = self.combo_size.currentData() or ("4" if std == "asme_b16_5" else "100")
        sizes = flanges.available_sizes(std, rating, ftype, facing)
        self._refill(self.combo_size, [(flanges.size_label(std, s), s) for s in sizes], keep)
        self._on_size_changed()

    def _on_size_changed(self) -> None:
        data = self._data()
        self.spin_bore.blockSignals(True)
        self.spin_bore.setValue(float(data["bore"] or 0.0) if data else 0.0)
        self.spin_bore.blockSignals(False)
        blind = self.combo_type.currentData() == "blind"
        self.label_bore.setVisible(not blind)
        self.spin_bore.setVisible(not blind)
        self._update_info()

    def _data(self):
        size = self.combo_size.currentData()
        if size is None:
            return None
        try:
            return flanges.flange(self.standard(), str(self.combo_rating.currentData()), str(size),
                                  str(self.combo_type.currentData()), str(self.combo_facing.currentData()))
        except ValueError:
            return None

    def _update_info(self) -> None:
        result = self.get_result()
        if result["size"] is None:
            self.lbl_info.setText(themed(html.escape(tr("La norma no tiene esta brida en ninguna medida."))))
            self.btn_insert.setEnabled(False)
            return
        lines = flanges.describe(result["standard"], result["rating"], result["size"], result["type"],
                                 result["facing"], result["bore"] or None)
        txt = "<br>".join([f"<b>{html.escape(lines[0])}</b>", *map(html.escape, lines[1:])])
        missing = result["type"] != "blind" and not result["bore"]
        params = dict(self._data() or {})
        if result["bore"]:
            params["bore"] = result["bore"]
        for warning in ([] if missing else flanges.flange_warnings(params)):
            txt += "<br><span style='color: #B42318;'>{}</span>".format(html.escape(warning))
        self.lbl_info.setText(themed(txt))
        self.btn_insert.setEnabled(not missing)

    def get_result(self) -> dict:
        blind = self.combo_type.currentData() == "blind"
        return {"standard": self.standard(), "rating": str(self.combo_rating.currentData()),
                "type": str(self.combo_type.currentData()), "facing": str(self.combo_facing.currentData()),
                "size": None if self.combo_size.currentData() is None else str(self.combo_size.currentData()),
                "bore": None if blind else self.spin_bore.value()}
