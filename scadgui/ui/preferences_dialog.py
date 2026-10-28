"""Diálogo unificado de configuración y preferencias de la aplicación y OpenSCAD."""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QSpinBox,
                               QTabWidget, QVBoxLayout, QWidget)

from ..i18n import LANGUAGES, get_language, set_language, tr
from ..runner import find_openscad


COLOR_SCHEMES = [
    "Tomorrow Night",
    "Metallic",
    "Sunset",
    "Starnight",
    "DeepOcean",
    "Solarized",
    "BeforeDawn",
    "Nature",
    "Monospaced",
]


class PreferencesDialog(QDialog):
    """Diálogo de preferencias para configurar el motor OpenSCAD y las herramientas avanzadas."""

    def __init__(self, settings: QSettings, current_exe: str = "", current_backend: str = "", parent=None):
        super().__init__(parent)
        self.settings = settings
        self._detected_version = ""

        # Asegurar que el idioma activo inicial coincida con la configuración
        active_lang = str(self.settings.value("language", get_language(), str) or "es")
        self._initial_lang = active_lang
        set_language(active_lang)

        self.resize(560, 500)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        self.tabs = QTabWidget()

        # ------------------------------------------------------------- 1. Motor OpenSCAD
        tab_engine = QWidget()
        lay_engine = QVBoxLayout(tab_engine)

        self.grp_exe = QGroupBox()
        lay_exe = QVBoxLayout(self.grp_exe)
        row_exe = QHBoxLayout()
        self.edit_exe = QLineEdit(current_exe or self.settings.value("openscad_path", "", str))
        self.btn_browse = QPushButton()
        self.btn_browse.clicked.connect(self._on_browse_exe)
        self.btn_test = QPushButton()
        self.btn_test.clicked.connect(self._on_test_exe)
        row_exe.addWidget(self.edit_exe)
        row_exe.addWidget(self.btn_browse)
        row_exe.addWidget(self.btn_test)
        lay_exe.addLayout(row_exe)

        self.lbl_exe_status = QLabel()
        self.lbl_exe_status.setStyleSheet("color: #5A6474; font-size: 11px;")
        lay_exe.addWidget(self.lbl_exe_status)
        lay_engine.addWidget(self.grp_exe)

        self.grp_csg = QGroupBox()
        form_csg = QFormLayout(self.grp_csg)
        self.combo_backend = QComboBox()
        self.combo_backend.addItem("", "")
        self.combo_backend.addItem("", "manifold")
        self.combo_backend.addItem("", "cgal")
        saved_backend = current_backend or self.settings.value("backend", "", str)
        idx_b = self.combo_backend.findData(saved_backend)
        if idx_b >= 0:
            self.combo_backend.setCurrentIndex(idx_b)
        self.lbl_csg = QLabel()
        form_csg.addRow(self.lbl_csg, self.combo_backend)

        self.combo_colorscheme = QComboBox()
        for scheme in COLOR_SCHEMES:
            self.combo_colorscheme.addItem(scheme, scheme)
        saved_scheme = self.settings.value("colorscheme", "Tomorrow Night", str)
        idx_c = self.combo_colorscheme.findData(saved_scheme)
        if idx_c >= 0:
            self.combo_colorscheme.setCurrentIndex(idx_c)
        self.lbl_colorscheme = QLabel()
        form_csg.addRow(self.lbl_colorscheme, self.combo_colorscheme)

        self.chk_roof = QCheckBox()
        self.chk_roof.setChecked(self.settings.value("enable_roof", False, bool))
        form_csg.addRow("", self.chk_roof)

        self.edit_extra_flags = QLineEdit(self.settings.value("extra_flags", "", str))
        self.lbl_extra_flags = QLabel()
        form_csg.addRow(self.lbl_extra_flags, self.edit_extra_flags)

        lay_engine.addWidget(self.grp_csg)
        lay_engine.addStretch(1)
        self.tabs.addTab(tab_engine, "")

        # ------------------------------------------------------------- 2. Visor 3D y Manipulación
        tab_view = QWidget()
        lay_view = QVBoxLayout(tab_view)

        self.grp_viewer = QGroupBox()
        form_viewer = QFormLayout(self.grp_viewer)
        self.combo_viewer_type = QComboBox()
        self.combo_viewer_type.addItem("", "gl")
        self.combo_viewer_type.addItem("", "image")
        saved_viewer = self.settings.value("viewer", "gl", str)
        idx_v = self.combo_viewer_type.findData(saved_viewer)
        if idx_v >= 0:
            self.combo_viewer_type.setCurrentIndex(idx_v)
        self.lbl_viewer = QLabel()
        form_viewer.addRow(self.lbl_viewer, self.combo_viewer_type)
        lay_view.addWidget(self.grp_viewer)

        self.grp_gizmo = QGroupBox()
        form_gizmo = QFormLayout(self.grp_gizmo)
        self.chk_gizmo_enabled = QCheckBox()
        self.chk_gizmo_enabled.setChecked(self.settings.value("gizmo_enabled", True, bool))
        form_gizmo.addRow("", self.chk_gizmo_enabled)

        self.combo_snap = QComboBox()
        self.combo_snap.addItem("", 0.1)
        self.combo_snap.addItem("0.5 mm", 0.5)
        self.combo_snap.addItem("", 1.0)
        self.combo_snap.addItem("5.0 mm", 5.0)
        self.combo_snap.addItem("10.0 mm", 10.0)
        saved_snap = float(self.settings.value("gizmo_snap", 1.0) or 1.0)
        idx_s = self.combo_snap.findData(saved_snap)
        if idx_s >= 0:
            self.combo_snap.setCurrentIndex(idx_s)
        self.lbl_snap = QLabel()
        form_gizmo.addRow(self.lbl_snap, self.combo_snap)

        self.spin_explode = QDoubleSpinBox()
        self.spin_explode.setRange(1.0, 5.0)
        self.spin_explode.setSingleStep(0.5)
        self.spin_explode.setValue(float(self.settings.value("explode_max_mult", 2.0) or 2.0))
        self.lbl_explode = QLabel()
        form_gizmo.addRow(self.lbl_explode, self.spin_explode)

        lay_view.addWidget(self.grp_gizmo)
        lay_view.addStretch(1)
        self.tabs.addTab(tab_view, "")

        # ------------------------------------------------------------- 3. Componentes y Planos 2D
        tab_tools = QWidget()
        lay_tools = QVBoxLayout(tab_tools)

        self.grp_hw = QGroupBox()
        form_hw = QFormLayout(self.grp_hw)
        self.combo_hw_fit = QComboBox()
        self.combo_hw_fit.addItem("", "medium")
        self.combo_hw_fit.addItem("", "fine")
        self.combo_hw_fit.addItem("", "coarse")
        saved_fit = self.settings.value("hardware_fit", "medium", str)
        idx_f = self.combo_hw_fit.findData(saved_fit)
        if idx_f >= 0:
            self.combo_hw_fit.setCurrentIndex(idx_f)
        self.lbl_hw_fit = QLabel()
        form_hw.addRow(self.lbl_hw_fit, self.combo_hw_fit)

        self.combo_hw_metric = QComboBox()
        for m in ("M2", "M2.5", "M3", "M4", "M5", "M6", "M8", "M10"):
            self.combo_hw_metric.addItem(m, m)
        saved_m = self.settings.value("hardware_metric", "M3", str)
        idx_m = self.combo_hw_metric.findData(saved_m)
        if idx_m >= 0:
            self.combo_hw_metric.setCurrentIndex(idx_m)
        self.lbl_hw_metric = QLabel()
        form_hw.addRow(self.lbl_hw_metric, self.combo_hw_metric)
        lay_tools.addWidget(self.grp_hw)

        self.grp_draw = QGroupBox()
        form_draw = QFormLayout(self.grp_draw)
        self.combo_sheet = QComboBox()
        self.combo_sheet.addItem("", "A4")
        self.combo_sheet.addItem("", "A3")
        saved_sheet = self.settings.value("drawing_sheet", "A4", str)
        idx_sh = self.combo_sheet.findData(saved_sheet)
        if idx_sh >= 0:
            self.combo_sheet.setCurrentIndex(idx_sh)
        self.lbl_sheet = QLabel()
        form_draw.addRow(self.lbl_sheet, self.combo_sheet)

        self.edit_author = QLineEdit(self.settings.value("drawing_author", "Diseñador CAD", str))
        self.lbl_author = QLabel()
        form_draw.addRow(self.lbl_author, self.edit_author)
        lay_tools.addWidget(self.grp_draw)

        lay_tools.addStretch(1)
        self.tabs.addTab(tab_tools, "")

        # ------------------------------------------------------------- 4. Editor y Proyecto
        tab_proj = QWidget()
        lay_proj = QVBoxLayout(tab_proj)

        self.grp_proj = QGroupBox()
        form_proj = QFormLayout(self.grp_proj)

        self.spin_fn = QSpinBox()
        self.spin_fn.setRange(0, 360)
        self.spin_fn.setValue(int(self.settings.value("default_fn", 0) or 0))
        self.lbl_fn = QLabel()
        form_proj.addRow(self.lbl_fn, self.spin_fn)

        self.combo_debounce = QComboBox()
        self.combo_debounce.addItem("", 300)
        self.combo_debounce.addItem("", 500)
        self.combo_debounce.addItem("", 800)
        saved_deb = int(self.settings.value("debounce_ms", 500) or 500)
        idx_deb = self.combo_debounce.findData(saved_deb)
        if idx_deb >= 0:
            self.combo_debounce.setCurrentIndex(idx_deb)
        self.lbl_debounce = QLabel()
        form_proj.addRow(self.lbl_debounce, self.combo_debounce)

        self.combo_lang = QComboBox()
        for code, name in LANGUAGES.items():
            self.combo_lang.addItem(f"{name} ({code})", code)
        idx_lang = self.combo_lang.findData(active_lang)
        if idx_lang >= 0:
            self.combo_lang.setCurrentIndex(idx_lang)
        self.lbl_lang = QLabel()
        form_proj.addRow(self.lbl_lang, self.combo_lang)

        lay_proj.addWidget(self.grp_proj)
        lay_proj.addStretch(1)
        self.tabs.addTab(tab_proj, "")

        main_layout.addWidget(self.tabs)

        # Botones inferiores
        btn_box = QHBoxLayout()
        self.btn_save = QPushButton()
        self.btn_save.setObjectName("primary")
        self.btn_save.clicked.connect(self._on_save)

        self.btn_cancel = QPushButton()
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addStretch(1)
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_save)
        main_layout.addLayout(btn_box)

        # Aplicar textos traducidos
        self._translate_ui()

        # Conectar cambio de idioma dinámico en el combo
        self.combo_lang.currentIndexChanged.connect(self._on_language_selection_changed)

        # Probar el exe inicial si existe
        if self.edit_exe.text().strip():
            self._on_test_exe()

    def _translate_ui(self) -> None:
        """Aplica las traducciones dinámicamente a todos los textos del diálogo."""
        self.setWindowTitle(tr("Configuración y Preferencias"))

        # Pestañas
        self.tabs.setTabText(0, tr("Motor OpenSCAD"))
        self.tabs.setTabText(1, tr("Visor 3D y Gizmo"))
        self.tabs.setTabText(2, tr("Componentes y Planos"))
        self.tabs.setTabText(3, tr("Editor y Proyecto"))

        # 1. Motor OpenSCAD
        self.grp_exe.setTitle(tr("Ejecutable de OpenSCAD"))
        self.edit_exe.setPlaceholderText(tr("Ruta a openscad.exe o openscad.com"))
        self.btn_browse.setText(tr("Examinar…"))
        self.btn_test.setText(tr("Probar"))
        if not self._detected_version and not self.edit_exe.text().strip():
            self.lbl_exe_status.setText(tr("Estado: sin verificar"))

        self.grp_csg.setTitle(tr("Motor de renderizado (Backend)"))
        self.lbl_csg.setText(tr("Motor CSG:"))
        self.combo_backend.setItemText(0, tr("Automático (recomendado)"))
        self.combo_backend.setItemText(1, tr("Manifold (aceleración moderna ultrarrápida)"))
        self.combo_backend.setItemText(2, tr("CGAL (motor clásico de OpenSCAD)"))

        self.lbl_colorscheme.setText(tr("Esquema de colores (vista previa):"))
        self.chk_roof.setText(tr("Habilitar primitiva experimental roof() (--enable=roof)"))
        self.lbl_extra_flags.setText(tr("Parámetros CLI extra:"))
        self.edit_extra_flags.setPlaceholderText(tr("Ej: --enable=fast-csg"))

        # 2. Visor 3D
        self.grp_viewer.setTitle(tr("Tipo de visor principal"))
        self.lbl_viewer.setText(tr("Tecnología del visor:"))
        self.combo_viewer_type.setItemText(0, tr("Visor 3D OpenGL interactivo (recomendado)"))
        self.combo_viewer_type.setItemText(1, tr("Visor de imágenes estáticas OpenSCAD"))

        self.grp_gizmo.setTitle(tr("Gizmo 3D de transformación interactiva"))
        self.chk_gizmo_enabled.setText(tr("Mostrar flechas de arrastre XYZ en la selección"))
        self.lbl_snap.setText(tr("Salto de rejilla (Snapping):"))
        self.combo_snap.setItemText(0, tr("Libre (0.1 mm)"))
        self.combo_snap.setItemText(2, tr("1.0 mm (recomendado)"))
        self.lbl_explode.setText(tr("Factor máx. vista explosionada:"))

        # 3. Componentes y Planos
        self.grp_hw.setTitle(tr("Tornillería y componentes mecánicos"))
        self.lbl_hw_fit.setText(tr("Tolerancia por defecto (ISO 273):"))
        self.combo_hw_fit.setItemText(0, tr("Media / Impresión 3D FDM (+0.4 mm paso)"))
        self.combo_hw_fit.setItemText(1, tr("Fina / Mecanizado (+0.2 mm paso)"))
        self.combo_hw_fit.setItemText(2, tr("Gruesa / Holgada (+0.6 mm paso)"))
        self.lbl_hw_metric.setText(tr("Métrica sugerida por defecto:"))

        self.grp_draw.setTitle(tr("Láminas y planos técnicos 2D"))
        self.lbl_sheet.setText(tr("Formato de hoja por defecto:"))
        self.combo_sheet.setItemText(0, tr("A4 Horizontal (297 × 210 mm)"))
        self.combo_sheet.setItemText(1, tr("A3 Horizontal (420 × 297 mm)"))
        self.lbl_author.setText(tr("Diseñador / Autor por defecto:"))

        # 4. Editor y Proyecto
        self.grp_proj.setTitle(tr("Valores por defecto del proyecto"))
        self.lbl_fn.setText(tr("Resolución $fn por defecto:"))
        self.spin_fn.setSpecialValueText(tr("0 (Adaptativo OpenSCAD)"))
        self.lbl_debounce.setText(tr("Retardo de actualización (ms):"))
        self.combo_debounce.setItemText(0, tr("Rápido (300 ms)"))
        self.combo_debounce.setItemText(1, tr("Normal (500 ms)"))
        self.combo_debounce.setItemText(2, tr("Pausado (800 ms)"))
        self.lbl_lang.setText(tr("Idioma de la interfaz:"))

        # Botones
        self.btn_save.setText(tr("Guardar preferencias"))
        self.btn_cancel.setText(tr("Cancelar"))

    def _on_language_selection_changed(self) -> None:
        """Actualiza el idioma dinámicamente cuando el usuario cambia el selector."""
        new_lang = str(self.combo_lang.currentData() or "es")
        set_language(new_lang)
        self._translate_ui()

    def _on_browse_exe(self) -> None:
        filt = "OpenSCAD (openscad.exe openscad.com)" if os.name == "nt" else "OpenSCAD (*)"
        start = self.edit_exe.text().strip() or ""
        path, _ = QFileDialog.getOpenFileName(self, tr("¿Dónde está OpenSCAD?"), start, filt)
        if path:
            exe = find_openscad(path)
            self.edit_exe.setText(exe)
            self._on_test_exe()

    def _on_test_exe(self) -> None:
        raw_path = self.edit_exe.text().strip()
        if not raw_path:
            self.lbl_exe_status.setText(tr("Estado: ruta vacía"))
            self.lbl_exe_status.setStyleSheet("color: #8A5A00; font-size: 11px;")
            return

        exe = find_openscad(raw_path)
        if not os.path.exists(exe):
            self.lbl_exe_status.setText(f"{tr('Estado')}: {tr('no se encontró')} '{exe}'")
            self.lbl_exe_status.setStyleSheet("color: #B42318; font-size: 11px;")
            return

        # Intentar ejecutar con --version
        import subprocess
        try:
            res = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=3.0)
            ver = (res.stdout or res.stderr or "").strip()
            self._detected_version = ver
            self.lbl_exe_status.setText(f"{tr('Correcto')}: {ver}")
            self.lbl_exe_status.setStyleSheet("color: #174A96; font-size: 11px;")
        except Exception as exc:  # noqa: BLE001
            self.lbl_exe_status.setText(f"{tr('Error al ejecutar')}: {exc}")
            self.lbl_exe_status.setStyleSheet("color: #B42318; font-size: 11px;")

    def _on_save(self) -> None:
        # Guardar en QSettings
        self.settings.setValue("openscad_path", self.edit_exe.text().strip())
        self.settings.setValue("backend", self.combo_backend.currentData() or "")
        self.settings.setValue("colorscheme", self.combo_colorscheme.currentData() or "Tomorrow Night")
        self.settings.setValue("enable_roof", self.chk_roof.isChecked())
        self.settings.setValue("extra_flags", self.edit_extra_flags.text().strip())

        self.settings.setValue("viewer", self.combo_viewer_type.currentData() or "gl")
        self.settings.setValue("gizmo_enabled", self.chk_gizmo_enabled.isChecked())
        self.settings.setValue("gizmo_snap", float(self.combo_snap.currentData() or 1.0))
        self.settings.setValue("explode_max_mult", float(self.spin_explode.value()))

        self.settings.setValue("hardware_fit", self.combo_hw_fit.currentData() or "medium")
        self.settings.setValue("hardware_metric", self.combo_hw_metric.currentData() or "M3")
        self.settings.setValue("drawing_sheet", self.combo_sheet.currentData() or "A4")
        self.settings.setValue("drawing_author", self.edit_author.text().strip())

        self.settings.setValue("default_fn", int(self.spin_fn.value()))
        self.settings.setValue("debounce_ms", int(self.combo_debounce.currentData() or 500))

        new_lang = str(self.combo_lang.currentData() or "es")
        old_lang = str(self.settings.value("language", "es", str) or "es")
        self.settings.setValue("language", new_lang)
        set_language(new_lang)

        self.accept()

    def reject(self) -> None:
        set_language(self._initial_lang)
        super().reject()

    def get_config(self) -> dict:
        return {
            "openscad_path": self.edit_exe.text().strip(),
            "backend": self.combo_backend.currentData() or "",
            "colorscheme": self.combo_colorscheme.currentData() or "Tomorrow Night",
            "enable_roof": self.chk_roof.isChecked(),
            "extra_flags": self.edit_extra_flags.text().strip(),
            "viewer": self.combo_viewer_type.currentData() or "gl",
            "gizmo_enabled": self.chk_gizmo_enabled.isChecked(),
            "gizmo_snap": float(self.combo_snap.currentData() or 1.0),
            "explode_max_mult": float(self.spin_explode.value()),
            "hardware_fit": self.combo_hw_fit.currentData() or "medium",
            "hardware_metric": self.combo_hw_metric.currentData() or "M3",
            "drawing_sheet": self.combo_sheet.currentData() or "A4",
            "drawing_author": self.edit_author.text().strip(),
            "default_fn": int(self.spin_fn.value()),
            "debounce_ms": int(self.combo_debounce.currentData() or 500),
            "language": str(self.combo_lang.currentData() or "es"),
        }
