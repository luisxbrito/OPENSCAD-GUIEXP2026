"""Panel de propiedades: un formulario generado a partir de los parámetros del catálogo."""

from __future__ import annotations

import copy
import math
import os
from typing import Any, Optional

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton,
                               QScrollArea, QSpinBox, QToolButton, QVBoxLayout, QWidget)

from ..catalog import Param
from ..i18n import tr
from ..model import Document, Expr, Node, RawCode, format_value
from ..radii import conflicts
from ..parser import literal
from .editors import edit_faces, edit_matrix, edit_points
from .style import themed

COLOR_NAMES = ["SteelBlue", "Gold", "Tomato", "SeaGreen", "SlateGray", "Orange", "Crimson",
               "RoyalBlue", "Purple", "Black", "White", "Silver", "Brown", "Pink", "Teal"]


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _rows_of(v: Any, n: Optional[int], ints: bool = False) -> bool:
    if not isinstance(v, list) or not v:
        return False
    for row in v:
        if not isinstance(row, list) or not row or not all(_is_num(x) for x in row):
            return False
        if n is not None and len(row) != n:
            return False
        if ints and not all(float(x).is_integer() for x in row):
            return False
    return True


def conforms(p: Param, v: Any) -> bool:
    """¿El valor actual se puede mostrar con el editor "bonito" de su tipo?"""
    k = p.kind
    if k in ("num",):
        return _is_num(v)
    if k == "int":
        return _is_num(v) and float(v).is_integer()
    if k == "bool":
        return isinstance(v, bool)
    if k in ("vec2", "vec3"):
        n = 2 if k == "vec2" else 3
        return isinstance(v, list) and len(v) == n and all(_is_num(x) for x in v)
    if k in ("str", "file", "color"):
        return isinstance(v, str)
    if k == "choice":
        return isinstance(v, str) and v in p.options
    if k == "points2":
        return _rows_of(v, 2)
    if k == "points3":
        return _rows_of(v, 3)
    if k == "faces":
        return _rows_of(v, None, ints=True)
    if k == "matrix":
        return _rows_of(v, 4) and len(v) in (3, 4)
    if k == "edges":
        return isinstance(v, list) and all(isinstance(x, str) and x in p.options for x in v)
    return False  # expr


class _WheelGuard(QObject):
    """La rueda del ratón no cambia valores de un campo que no tiene el foco."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and not obj.hasFocus():
            event.ignore()
            return True
        return False


class PropertyPanel(QScrollArea):
    changed = Signal(int, str, object)    # id del nodo, parámetro, valor (None = quitar)
    renamed = Signal(int, str)
    editCode = Signal(int)
    fnChanged = Signal(object)
    selectNode = Signal(int)
    openBooleanWizard = Signal(int)
    setDifferenceBase = Signal(int, int)
    openOperationHelper = Signal(str)
    fixRadii = Signal(int)
    addMeshingGear = Signal(int, int)       # engranaje, dientes de la pareja

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.node = None
        self.doc: Optional[Document] = None
        self.base_dir = ""
        self._guard = _WheelGuard(self)
        self._body = QWidget()
        self.setWidget(self._body)
        self.show_node(None, Document())

    # ----------------------------------------------------------------- construcción
    def show_node(self, node, doc: Document) -> None:
        self.node = node
        self.doc = doc
        body = QWidget()
        body.setObjectName("propsBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(10)
        self._lay = lay

        if node is None:
            self._document_form(doc)
        elif isinstance(node, RawCode):
            self._raw_form(node)
        else:
            self._node_form(node)
        lay.addStretch(1)
        old = self.takeWidget()
        if old is not None:
            old.deleteLater()
        self.setWidget(body)

    def refresh(self) -> None:
        QTimer.singleShot(0, lambda: self.show_node(self.node, self.doc))

    def _title(self, text: str, mono: str = "") -> None:
        row = QHBoxLayout()
        t = QLabel(text)
        t.setObjectName("sectionTitle")
        row.addWidget(t)
        row.addStretch(1)
        if mono:
            m = QLabel(mono)
            m.setObjectName("accentMono")
            row.addWidget(m)
        self._lay.addLayout(row)

    def _hint(self, text: str, kind: str = "hint") -> QLabel:
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setObjectName(kind)
        self._lay.addWidget(lab)
        return lab

    def _caption(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("caption")
        return lab

    # ----- sin selección: ajustes del documento
    def _document_form(self, doc: Document) -> None:
        self._title(tr("Documento"))
        self._hint(tr("Selecciona una pieza en el árbol para editar sus propiedades, o crea una con la cinta de arriba."))
        row = QHBoxLayout()
        check = QCheckBox(tr("Resolución global ($fn)"))
        spin = QSpinBox()
        spin.setRange(3, 512)
        spin.setValue(doc.fn or 64)
        spin.setEnabled(bool(doc.fn))
        check.setChecked(bool(doc.fn))
        self._guarded(spin)
        check.toggled.connect(lambda on: (spin.setEnabled(on), self.fnChanged.emit(spin.value() if on else None)))
        spin.valueChanged.connect(lambda v: self.fnChanged.emit(v) if check.isChecked() else None)
        row.addWidget(check)
        row.addWidget(spin)
        self._lay.addLayout(row)
        self._hint(tr("Más segmentos = curvas más suaves y vista previa más lenta."), "caption")

    # ----- código literal
    def _raw_form(self, node: RawCode) -> None:
        self._title(tr("Comentario") if node.is_comment else tr("Código"), tr("solo código"))
        box = QLabel(tr("<b>Bloque programado</b><br>Este fragmento usa lógica de OpenSCAD (variables, "
                        "bucles, módulos…). Se conserva tal cual y se edita en el panel de código "
                        "para no romperlo.") if not node.is_comment else
                     tr("Comentario del archivo. Se conserva al guardar."))
        box.setWordWrap(True)
        box.setObjectName("warnBox")
        self._lay.addWidget(box)
        view = QPlainTextEdit(node.text)
        view.setReadOnly(True)
        view.setObjectName("rawView")
        view.setMinimumHeight(120)
        self._lay.addWidget(view)
        btn = QPushButton(tr("Editar en el código"))
        btn.clicked.connect(lambda: self.editCode.emit(node.id))
        self._lay.addWidget(btn)

    # ----- nodo normal
    def _node_form(self, node: Node) -> None:
        spec = node.spec
        self._title(tr("Propiedades"), f"{node.kind}()")
        self._lay.addWidget(self._caption(tr("Nombre")))
        name = QLineEdit(node.name)
        name.setPlaceholderText(tr(spec.label) if spec else node.kind)
        name.editingFinished.connect(lambda: self.renamed.emit(node.id, name.text()))
        self._lay.addWidget(name)

        for p in (spec.params if spec else ()):
            self._param_row(node, p)

        extras = [k for k in node.params if not spec or not spec.param(k)]
        for key in extras:
            self._extra_row(node, key)

        problems = conflicts(node)
        if problems:
            self._hint("\n".join(problems), "warnText")
            fix = QPushButton(tr("Corregir (misma forma)"))
            fix.clicked.connect(lambda: self.fixRadii.emit(node.id))
            self._lay.addWidget(fix)
        if node.kind in ("spur_gear", "helical_gear", "herringbone_gear", "rack", "bevel_gear"):
            self._gear_info(node)
        if node.kind == "pulley":
            self._pulley_info(node)
        if node.kind == "v_pulley":
            self._v_pulley_info(node)
        if node.kind == "spline":
            self._spline_info(node)
        if node.kind == "cam":
            self._cam_info(node)
        if node.kind == "cam_lobe":
            self._lobe_info(node)
        if node.kind in ("cam_lobe", "camshaft_main_shaft") and self.doc is not None:
            self._camshaft_info(node)
        if node.kind == "pipe_flange":
            self._flange_info(node)
        if spec and spec.hint:
            self._hint(tr(spec.hint))
        if spec and spec.container and not node.children:
            self._hint(tr("Está vacío: selecciónalo y añade piezas desde la cinta, o usa "
                          "“Meter en el de arriba” en el árbol."), "warnText")
        if spec and spec.level == "experimental":
            self._hint(tr("Función experimental: OpenSCAD la ejecuta con --enable=roof."), "warnText")

        if node.kind in ("difference", "union", "intersection"):
            self._boolean_form(node)
        self._operation_helper_form(node)

    def _gear_info(self, node: Node) -> None:
        """Medidas calculadas, avisos de diseño y el botón para añadir la pareja que engrana."""
        from .. import gears
        p = node.params

        def val(key, default):
            v = p.get(key, default)
            return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

        mod, z, pa = val("mod", 1), val("teeth", 20), val("pressure_angle", 20)
        if None in (mod, z, pa):
            return                                   # con expresiones no se puede calcular aquí
        num = lambda k: val(k, 0) or 0
        if node.kind == "rack":
            psi, thick = val("helix_angle", 0), val("thickness", 5)
            if None in (psi, thick):
                return
            d = gears.rack_dims(mod, int(z), pa, num("base"), psi, thick)
            self._hint(tr("Paso {p:.3f} mm · longitud {l:g} mm · altura {h:g} mm · grueso del diente "
                          "{t:.3f} mm").format(p=d["pitch"], l=round(d["length"], 3),
                                               h=round(d["height"], 3), t=d["tooth_thickness"]))
            if psi:
                self._hint(tr("Módulo aparente {mt:.3f} · presión aparente {at:.2f}° · el dentado se "
                              "corre {s:.2f} mm sobre el grueso · engrana con un helicoidal de "
                              "{h:g}° de la misma mano").format(mt=d["transverse_mod"],
                                                                at=d["transverse_angle"],
                                                                s=d["shift"], h=psi))
            problems = gears.rack_warnings(mod, int(z), pa, num("backlash"), num("base"), psi)
            label = tr("Añadir engranaje sobre la cremallera")
            tip = tr("Crea el engranaje del mismo módulo que le corresponde (helicoidal de la misma "
                     "mano si el dentado va inclinado), ya colocado sobre la cremallera y girado "
                     "para que los dientes encajen.")
            start = 20
        elif node.kind == "bevel_gear":
            zm, sigma = val("mate_teeth", 20), val("shaft_angle", 90)
            face = val("face_width", 4)
            if None in (zm, sigma, face):
                return
            d = gears.bevel_dims(mod, int(z), int(zm), sigma, pa, face)
            self._hint(tr("Ø primitivo {d:g} mm · Ø exterior {da:g} mm · cono primitivo {g:.2f}° · "
                          "distancia de cono {c:.2f} mm").format(d=round(d["pitch_d"], 3),
                                                                 da=round(d["tip_d"], 3),
                                                                 g=d["gamma"], c=d["cone"]))
            self._hint(tr("Cono de cabeza {fa:.2f}° · cono de pie {ra:.2f}° · dientes virtuales "
                          "{v:.1f} · cara máxima {mf:.1f} mm").format(fa=d["face_angle"],
                                                                      ra=d["root_angle"],
                                                                      v=d["virtual_teeth"],
                                                                      mf=d["max_face"]))
            problems = gears.bevel_warnings(mod, int(z), int(zm), sigma, pa, num("backlash"),
                                            num("bore"), face)
            label = tr("Añadir engranaje que engrane")
            tip = tr("Crea el otro cónico de la pareja, girado el ángulo entre ejes y en fase. Los "
                     "dos comparten el vértice del cono, que está en el origen, así que no hay nada "
                     "que mover.")
            start = int(zm)
        elif node.kind == "helical_gear":
            psi, thick = val("helix_angle", 20), val("thickness", 10)
            if None in (psi, thick):
                return
            d = gears.helical_dims(mod, int(z), psi, pa, thick)
            self._hint(tr("Ø primitivo {d:g} mm · Ø exterior {da:g} mm · Ø raíz {df:g} mm").format(
                d=round(d["pitch_d"], 3), da=round(d["tip_d"], 3), df=round(d["root_d"], 3)))
            self._hint(tr("Módulo aparente {mt:.3f} · presión aparente {at:.2f}° · avance de la hélice "
                          "{lead:.1f} mm · giro {tw:.1f}° sobre el grueso · solape axial {ov:.2f}").format(
                mt=d["transverse_mod"], at=d["transverse_angle"], lead=d["lead"], tw=d["twist"],
                ov=d["axial_overlap"]))
            problems = gears.helical_warnings(mod, int(z), psi, pa, num("backlash"), num("bore"), thick)
            label = tr("Añadir engranaje que engrane")
            tip = tr("Crea otro engranaje de la misma hélice pero de mano contraria (si no, no "
                     "engranan), ya colocado a m·(z1 + z2)/(2·cos ψ) y girado para que los dientes "
                     "encajen.")
            start = int(z)
        elif node.kind == "herringbone_gear":
            psi, thick, groove = val("helix_angle", 25), val("thickness", 16), num("groove")
            if None in (psi, thick):
                return
            half_b = (thick - groove) / 2
            d = gears.helical_dims(mod, int(z), psi, pa, half_b)
            self._hint(tr("Ø primitivo {d:g} mm · Ø exterior {da:g} mm · Ø raíz {df:g} mm").format(
                d=round(d["pitch_d"], 3), da=round(d["tip_d"], 3), df=round(d["root_d"], 3)))
            self._hint(tr("Módulo aparente {mt:.3f} · presión aparente {at:.2f}° · giro {tw:.1f}° "
                          "por mitad · solape axial por mitad {ov:.2f}").format(
                mt=d["transverse_mod"], at=d["transverse_angle"], tw=d["twist"],
                ov=d["axial_overlap"]))
            problems = gears.herringbone_warnings(mod, int(z), psi, pa, num("backlash"), num("bore"),
                                                  thick, groove)
            label = tr("Añadir engranaje que engrane")
            tip = tr("Crea otro engranaje de la misma hélice pero de mano contraria (si no, no "
                     "engranan), ya colocado a m·(z1 + z2)/(2·cos ψ) y girado para que los dientes "
                     "encajen.")
            start = int(z)
        else:
            d = gears.dims(mod, z, pa)
            self._hint(tr("Ø primitivo {d:g} mm · Ø exterior {da:g} mm · Ø raíz {df:g} mm · paso {p:.3f} mm").format(
                d=round(d["pitch_d"], 3), da=round(d["tip_d"], 3), df=round(d["root_d"], 3), p=d["circular_pitch"]))
            problems = gears.warnings(mod, z, pa, num("backlash"), num("bore"))
            label = tr("Añadir engranaje que engrane")
            tip = tr("Crea otro engranaje del mismo módulo, ya colocado a m·(z1 + z2)/2 y girado "
                     "para que los dientes encajen.")
            start = int(z)
        for text, values in problems:
            self._hint(tr(text).format(**values), "warnText")
        if node.kind == "bevel_gear":     # el Ø más estrecho del cono de pie, en el lado interior
            self._keyway_info(p, 2 * d["inner_z"] * math.tan(math.radians(d["root_angle"])))
        elif node.kind != "rack":
            self._keyway_info(p, d["root_d"])
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        teeth = QSpinBox()
        teeth.setRange(3, 400)
        teeth.setValue(start)
        teeth.setToolTip(tr("Dientes del engranaje nuevo"))
        add = QPushButton(label)
        add.setToolTip(tip)
        add.clicked.connect(lambda: self.addMeshingGear.emit(node.id, teeth.value()))
        lay.addWidget(add, 1)
        lay.addWidget(QLabel(tr("dientes:")))
        lay.addWidget(teeth)
        self._lay.addWidget(row)

    def _keyway_info(self, p: dict, root_d: float) -> None:
        """Medidas y avisos del cuñero, si la pieza lo lleva."""
        from .. import gears
        if p.get("keyway") is not True:
            return

        def val(key):
            v = p.get(key, 0)
            return None if isinstance(v, bool) or not isinstance(v, (int, float)) else v

        bore, width, depth = val("bore"), val("key_width"), val("key_depth")
        if None in (bore, width, depth):
            return                                   # con expresiones no se puede calcular aquí
        size = gears.keyway_size(bore, width, depth)
        row = gears.key_row(bore)
        if bore > 0 and size and row and size == (row[2], row[5]):
            self._hint(tr("Cuñero para eje Ø {d:g}: ancho {b:g} mm · profundidad en el cubo {t:g} mm · "
                          "cuña {b:g} × {h:g} mm · profundidad en el eje {s:g} mm (BS 4235)").format(
                d=bore, b=row[2], t=row[5], h=row[3], s=row[4]))
        elif bore > 0 and size:
            self._hint(tr("Cuñero a medida: ancho {b:g} mm · profundidad en el cubo {t:g} mm").format(
                b=size[0], t=size[1]))
        for text, values in gears.keyway_warnings(bore, width, depth, root_d):
            self._hint(tr(text).format(**values), "warnText")

    def _spline_info(self, node: Node) -> None:
        """Medidas calculadas, avisos de diseño y el botón para añadir la pieza pareja."""
        from .. import gears
        p = node.params
        values = [p.get(k, v) for k, v in (("mod", 1), ("teeth", 20), ("pressure_angle", 30),
                                           ("clearance", 0), ("hub_d", 0))]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            return                                   # con expresiones no se puede calcular aquí
        mod, z, pa, es, hub = values
        fillet, internal = p.get("fillet_root") is True, p.get("internal") is True
        d = gears.spline_dims(mod, int(z), pa, fillet, 0.0 if internal else es, hub)
        self._hint(tr("Ø primitivo {d:g} mm · Ø base {b:.3f} mm · paso {p:.3f} mm · grueso del diente "
                      "{s:.3f} mm").format(d=round(d["pitch_d"], 3), b=d["base_d"], p=d["pitch"],
                                           s=d["basic_width"] - d["es"]))
        if internal:
            self._hint(tr("Cubo: Ø mayor {a:.3f} mm · Ø de forma {f:.3f} mm · Ø menor {i:.3f} mm · Ø "
                          "exterior {o:.3f} mm").format(a=d["major_i"], f=d["form_i"], i=d["minor_i"],
                                                        o=d["hub_d"]))
        else:
            self._hint(tr("Eje: Ø mayor {a:.3f} mm · Ø de forma {f:.3f} mm · Ø menor {i:.3f} mm").format(
                a=d["major_e"], f=d["form_e"], i=d["minor_e"]))
        for text, data in gears.spline_warnings(mod, int(z), pa, fillet, internal, es, hub):
            self._hint(tr(text).format(**data), "warnText")
        add = QPushButton(tr("Añadir la pieza pareja"))
        add.setToolTip(tr("Crea el cubo o el eje que encaja con esta pieza, en el mismo sitio: no hay "
                          "que moverlo ni girarlo."))
        add.clicked.connect(lambda: self.addMeshingGear.emit(node.id, 0))
        self._lay.addWidget(add)

    def _cam_info(self, node: Node) -> None:
        """Medidas calculadas y avisos de diseño de la leva de disco."""
        from .. import gears
        p = node.params
        values = [p.get(k, v) for k, v in (("base_d", 40), ("lift", 10), ("rise_angle", 90),
                                           ("dwell_angle", 0), ("fall_angle", 90))]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            return                                   # con expresiones no se puede calcular aquí
        base_d, lift, rise, dwell, fall = values
        motion = p.get("motion", "cicloidal")
        d = gears.cam_dims(base_d, lift, rise, dwell, fall)
        motion_label = {"cicloidal": tr("cicloidal"), "armonica": tr("armónica"),
                        "parabolica": tr("parabólica"),
                        "velocidad_constante": tr("velocidad constante")}.get(motion, motion)
        self._hint(tr("Ø base {b:.2f} mm · Ø exterior {o:.2f} mm · ley {m}").format(
            b=d["base_r"] * 2, o=d["outer_r"] * 2, m=motion_label))
        self._hint(tr("Reposo abajo {r:.1f}°").format(r=d["rest_angle"]))
        for text, values2 in gears.cam_warnings(base_d, lift, rise, dwell, fall):
            self._hint(tr(text).format(**values2), "warnText")

    def _lobe_info(self, node: Node) -> None:
        """Medidas y avisos del lóbulo del árbol de levas."""
        from .. import gears
        p = node.params
        values = [p.get(k, v) for k, v in (("base_r", 15), ("lift", 8), ("rise_angle", 110),
                                           ("dwell_angle", 20), ("fall_angle", 110), ("position", 20),
                                           ("width", 12), ("nose_r", 0), ("step", 1))]
        motion, profile = p.get("motion", "cicloidal"), p.get("profile", "ley")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values) \
                or motion not in gears.CAM_MOTIONS or profile not in gears.LOBE_PROFILES:
            return                                   # con expresiones no se puede calcular aquí
        base_r, lift, rise, dwell, fall, position, width, nose_r, step = values
        if base_r > 0:
            top = base_r if profile == "circular" else base_r + max(0, lift)
            poly = gears.lobe_polygon(base_r, lift, rise, dwell, fall, motion, 0, step, profile, nose_r)
            self._hint(tr("Ø base {b:.2f} mm · Ø en la punta {o:.2f} mm · abre {a:.1f}° de la vuelta").format(
                b=2 * base_r, o=2 * top, a=gears.lobe_opening(poly, base_r, lift)))
        self._hint(tr("Ocupa de z = {a:g} a z = {b:g} mm").format(a=position - width / 2, b=position + width / 2))
        for text, data in gears.lobe_warnings(base_r, lift, rise, dwell, fall, motion, profile, nose_r, step):
            self._hint(tr(text).format(**data), "warnText")

    def _camshaft_info(self, node: Node) -> None:
        """Solapes, lóbulos fuera del eje y radios base menores que el del eje, mirando las piezas del
        árbol que están en el mismo contenedor. En un lóbulo, solo los avisos que le tocan."""
        from .. import camshaft
        shaft, lobes = camshaft.siblings(self.doc, node)
        problems = camshaft.shaft_problems(shaft.params if shaft is not None else None,
                                           [(lobe.name or lobe.kind, lobe.params) for lobe in lobes])
        if node.kind == "camshaft_main_shaft":
            self._hint(tr("Lóbulos en este árbol: {n}").format(n=len(lobes)))
        else:
            mine = node.name or node.kind
            problems = [(t, d) for t, d in problems if mine in (d.get("a"), d.get("b"))]
        for text, data in problems:
            self._hint(tr(text).format(**data), "warnText")

    def _flange_info(self, node: Node) -> None:
        """Volumen y avisos de forma de la brida (también si se retocan las medidas a mano)."""
        from .. import flanges
        p = node.params
        if not all(isinstance(p.get(k, 0), (int, float)) and not isinstance(p.get(k, 0), bool)
                   for k in flanges.MODULE_PARAMS):
            return                                   # con expresiones no se puede calcular aquí
        self._hint(tr("Volumen {v:.1f} cm³").format(v=flanges.flange_volume(p) / 1000))
        for text in flanges.flange_warnings(p):
            self._hint(text, "warnText")

    def _pulley_info(self, node: Node) -> None:
        """Medidas calculadas y avisos de diseño de la polea dentada."""
        from .. import gears
        p = node.params
        section = p.get("section", "XL")
        z = p.get("teeth", 20)
        if section not in gears.PULLEY_SECTIONS or not isinstance(z, (int, float)) or isinstance(z, bool):
            return                                   # con expresiones no se puede calcular aquí
        bore = p.get("bore", 0)
        bore = bore if isinstance(bore, (int, float)) and not isinstance(bore, bool) else 0
        d = gears.pulley_dims(section, int(z))
        self._hint(tr("Paso {p:.3f} mm · Ø primitivo {d:.2f} mm · Ø exterior {o:.2f} mm · Ø de "
                      "fondo {r:.2f} mm").format(p=d["pitch"], d=round(d["pitch_d"], 3),
                                                  o=round(d["outer_d"], 3), r=round(d["root_d"], 3)))
        self._hint(tr("Ángulo de diente {a:g}° · grueso en la línea primitiva {b:.3f} mm · "
                      "diferencial de línea primitiva {pld:.3f} mm").format(
            a=d["tooth_angle"], b=d["tooth_width"], pld=d["pld"]))
        flange = p.get("flange", "ninguna")
        flange_label = {"superior": tr("superior"), "inferior": tr("inferior"),
                        "ambas": tr("a ambos lados")}.get(flange)
        if flange_label:
            fh = p.get("flange_height", 1.5)
            fh = fh if isinstance(fh, (int, float)) and not isinstance(fh, bool) else 1.5
            self._hint(tr("Pestaña ({side}): Ø {fd:.2f} mm").format(
                side=flange_label, fd=round(d["outer_d"] + 2 * fh, 3)))
        for text, values in gears.pulley_warnings(section, int(z), bore):
            self._hint(tr(text).format(**values), "warnText")
        self._keyway_info(p, d["root_d"])

    def _v_pulley_info(self, node: Node) -> None:
        """Medidas calculadas y avisos de diseño de la polea trapecial."""
        from .. import gears
        p = node.params
        section = p.get("section", "A")
        dd = p.get("datum_d", 80)
        ng = p.get("grooves", 1)
        if (section not in gears.V_BELT_SECTIONS or not isinstance(dd, (int, float))
                or isinstance(dd, bool) or not isinstance(ng, (int, float)) or isinstance(ng, bool)):
            return                                   # con expresiones no se puede calcular aquí
        bore = p.get("bore", 0)
        bore = bore if isinstance(bore, (int, float)) and not isinstance(bore, bool) else 0
        d = gears.v_pulley_dims(section, dd, int(ng))
        self._hint(tr("Ángulo de ranura {a:g}° · boca {bg:.3f} mm · profundidad {hg:.3f} mm · "
                      "Ø de fondo {r:.2f} mm").format(a=d["groove_angle"], bg=d["groove_width"],
                                                       hg=d["groove_depth"],
                                                       r=round(d["root_d"], 3)))
        self._hint(tr("Ancho de cara {w:.2f} mm ({n} ranuras · separación {sg:.3f} mm · margen "
                      "{se:.3f} mm)").format(w=round(d["face_width"], 3), n=d["grooves"],
                                              sg=d["groove_spacing"], se=d["edge_distance"]))
        for text, values in gears.v_pulley_warnings(section, dd, int(ng), bore):
            self._hint(tr(text).format(**values), "warnText")
        self._keyway_info(p, d["root_d"])

    def _operation_helper_form(self, node: Node) -> None:
        """Añade el widget helper interactivo si la operación tiene guía o presets disponibles."""
        from .operation_helper import OPERATION_HELPERS, OperationHelperWidget
        if node.kind in OPERATION_HELPERS and node.kind not in ("difference", "union", "intersection"):
            helper_w = OperationHelperWidget(node.kind, node.params, self)
            helper_w.presetApplied.connect(lambda param_name, new_val: self.changed.emit(node.id, param_name, new_val))
            helper_w.openFullGuideRequested.connect(self.openOperationHelper.emit)
            self._lay.addWidget(helper_w)

    def _boolean_form(self, node: Node) -> None:
        """Muestra un panel visual interactivo sobre la operación booleana y los roles de sus piezas."""
        box = QFrame()
        box.setObjectName("booleanPanelBox")
        box.setStyleSheet(
            themed("QFrame#booleanPanelBox { background-color: #F8FAFC; border: 1px solid #CBD5E1; "
            "border-radius: 6px; padding: 10px; margin-top: 8px; }")
        )
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        if node.kind == "difference":
            title = QLabel(f"<b>{tr('Operación Restar (difference)')}</b>")
            title.setStyleSheet(themed("color: #991B1B; font-size: 13px;"))
            lay.addWidget(title)

            desc = QLabel(tr("El primer sólido es la Base (+); los siguientes se le restan (-) como cortes o huecos."))
            desc.setWordWrap(True)
            desc.setStyleSheet(themed("color: #475569; font-size: 11px;"))
            lay.addWidget(desc)

            if node.children:
                # 1er hijo: Base
                base_child = node.children[0]
                base_row = QHBoxLayout()
                base_lbl = QLabel(f"<b>{tr('Base (+)')}:</b> {base_child.label}")
                base_lbl.setStyleSheet(themed("color: #166534; font-size: 12px;"))
                base_row.addWidget(base_lbl, 1)
                btn_view_base = QPushButton(tr("Ver"))
                btn_view_base.setMaximumWidth(50)
                btn_view_base.clicked.connect(lambda: self.selectNode.emit(base_child.id))
                base_row.addWidget(btn_view_base)
                lay.addLayout(base_row)

                # Siguientes hijos: Restas
                restas = node.children[1:]
                if restas:
                    lbl_restas = QLabel(f"<b>{tr('Sólidos que se restan (-)')}:</b>")
                    lbl_restas.setStyleSheet(themed("color: #991B1B; font-size: 12px; margin-top: 4px;"))
                    lay.addWidget(lbl_restas)

                    for r in restas:
                        r_row = QHBoxLayout()
                        r_lbl = QLabel(f"  • {r.label}")
                        r_lbl.setStyleSheet(themed("color: #334155; font-size: 11px;"))
                        r_row.addWidget(r_lbl, 1)

                        btn_make_base = QPushButton(tr("Hacer Base"))
                        btn_make_base.setToolTip(tr("Mover esta pieza al 1er lugar para que sea la base a la que se resta"))
                        btn_make_base.setMaximumWidth(80)
                        btn_make_base.clicked.connect(lambda _=False, cid=r.id: self.setDifferenceBase.emit(node.id, cid))
                        r_row.addWidget(btn_make_base)

                        btn_view_r = QPushButton(tr("Ver"))
                        btn_view_r.setMaximumWidth(50)
                        btn_view_r.clicked.connect(lambda _=False, cid=r.id: self.selectNode.emit(cid))
                        r_row.addWidget(btn_view_r)
                        lay.addLayout(r_row)
                else:
                    lay.addWidget(QLabel(f"<i>{tr('(Aún no hay piezas para restar. Añade otra pieza a este grupo)')}</i>"))
            else:
                lay.addWidget(QLabel(f"<i>{tr('(difference vacío. Añade una base y piezas para restar)')}</i>"))

        elif node.kind == "union":
            title = QLabel(f"<b>{tr('Operación Unir (union)')}</b>")
            title.setStyleSheet(themed("color: #15803D; font-size: 13px;"))
            lay.addWidget(title)

            desc = QLabel(tr("Fusiona todos los sólidos hijos en un único cuerpo sólido continuo."))
            desc.setWordWrap(True)
            desc.setStyleSheet(themed("color: #475569; font-size: 11px;"))
            lay.addWidget(desc)

            for c in node.children:
                row = QHBoxLayout()
                lbl = QLabel(f"  • {c.label}")
                lbl.setStyleSheet(themed("color: #334155; font-size: 11px;"))
                row.addWidget(lbl, 1)
                btn = QPushButton(tr("Ver"))
                btn.setMaximumWidth(50)
                btn.clicked.connect(lambda _=False, cid=c.id: self.selectNode.emit(cid))
                row.addWidget(btn)
                lay.addLayout(row)

        else:  # intersection
            title = QLabel(f"<b>{tr('Operación Intersecar (intersection)')}</b>")
            title.setStyleSheet(themed("color: #6B21A8; font-size: 13px;"))
            lay.addWidget(title)

            desc = QLabel(tr("Conserva exclusivamente el volumen común compartido por todos los sólidos hijos."))
            desc.setWordWrap(True)
            desc.setStyleSheet(themed("color: #475569; font-size: 11px;"))
            lay.addWidget(desc)

            for c in node.children:
                row = QHBoxLayout()
                lbl = QLabel(f"  • {c.label}")
                lbl.setStyleSheet(themed("color: #334155; font-size: 11px;"))
                row.addWidget(lbl, 1)
                btn = QPushButton(tr("Ver"))
                btn.setMaximumWidth(50)
                btn.clicked.connect(lambda _=False, cid=c.id: self.selectNode.emit(cid))
                row.addWidget(btn)
                lay.addLayout(row)

        btn_wizard = QPushButton(f"{tr('Abrir Asistente Booleano...')}")
        btn_wizard.setStyleSheet(themed("margin-top: 6px; font-weight: 500;"))
        btn_wizard.clicked.connect(lambda: self.openBooleanWizard.emit(node.id))
        lay.addWidget(btn_wizard)

        self._lay.addWidget(box)

    def _param_row(self, node: Node, p: Param) -> None:
        present = p.name in node.params
        value = node.params.get(p.name, copy.deepcopy(p.default))
        head = QHBoxLayout()
        head.setSpacing(6)
        if p.optional:
            check = QCheckBox(tr(p.title))
            check.setObjectName("captionCheck")
            check.setChecked(present)
            check.toggled.connect(lambda on, p=p: self._toggle_optional(node, p, on))
            head.addWidget(check)
        else:
            head.addWidget(self._caption(tr(p.title)))
        head.addStretch(1)
        self._lay.addLayout(head)

        if p.optional and not present:
            return  # parámetro no usado: solo se muestra la casilla

        editor = self._editor(node, p, value)
        self._lay.addWidget(editor)

    def _toggle_optional(self, node: Node, p: Param, on: bool) -> None:
        self.changed.emit(node.id, p.name, copy.deepcopy(p.default) if on else None)
        self.refresh()

    def _extra_row(self, node: Node, key: str) -> None:
        head = QHBoxLayout()
        head.addWidget(self._caption(key))
        head.addStretch(1)
        remove = QToolButton()
        remove.setText(tr("Quitar"))
        remove.clicked.connect(lambda: (self.changed.emit(node.id, key, None), self.refresh()))
        head.addWidget(remove)
        self._lay.addLayout(head)
        self._lay.addWidget(self._expr_editor(node, key, node.params[key]))

    # ----------------------------------------------------------------- editores
    def _emit(self, node: Node, key: str, value: Any) -> None:
        self.changed.emit(node.id, key, value)

    def _guarded(self, w: QWidget) -> QWidget:
        w.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        w.installEventFilter(self._guard)
        return w

    def _num_spin(self, p: Param, value: float, integer: bool = False):
        spin = QSpinBox() if integer else QDoubleSpinBox()
        if integer:
            spin.setRange(int(max(p.minimum, -10 ** 9)), int(min(p.maximum, 10 ** 9)))
        else:
            spin.setDecimals(4)
            spin.setRange(max(p.minimum, -1e7), min(p.maximum, 1e7))
            spin.setSingleStep(p.step)
        spin.setKeyboardTracking(False)
        spin.setValue(int(value) if integer else float(value))
        return self._guarded(spin)

    def _editor(self, node: Node, p: Param, value: Any) -> QWidget:
        if not conforms(p, value):
            return self._expr_editor(node, p.name, value)
        k = p.kind
        if k in ("num", "int"):
            box = QWidget()
            row = QHBoxLayout(box)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            spin = self._num_spin(p, value, integer=(k == "int"))
            spin.valueChanged.connect(lambda v: self._emit(node, p.name, v))
            row.addWidget(spin, 1)

            vars_list = self.doc.get_variables() if self.doc is not None else []
            if vars_list:
                fx = QPushButton("ƒx")
                fx.setObjectName("fxButton")
                fx.setFixedWidth(28)
                fx.setToolTip(tr("Asignar variable global"))
                menu = QMenu(self)
                for v in vars_list:
                    a = menu.addAction(f"{v['name']}  (= {v['value']})")
                    a.triggered.connect(lambda _=False, n=v['name']: (self._emit(node, p.name, Expr(n)), self.refresh()))
                fx.setMenu(menu)
                row.addWidget(fx)
            return box
        if k == "bool":
            check = QCheckBox(tr("Sí"))
            check.setChecked(bool(value))
            check.toggled.connect(lambda on: self._emit(node, p.name, on))
            return check
        if k in ("vec2", "vec3"):
            return self._vector_editor(node, p, value)
        if k == "str":
            edit = QLineEdit(value)
            edit.editingFinished.connect(lambda: self._emit(node, p.name, edit.text()))
            return edit
        if k == "choice":
            combo = self._guarded(QComboBox())
            for option in p.options:
                combo.addItem(tr(option) if p.translated else option, option)
            combo.setCurrentIndex(max(0, combo.findData(value)))
            combo.currentIndexChanged.connect(lambda i: self._emit(node, p.name, combo.itemData(i)))
            return combo
        if k == "color":
            return self._color_editor(node, p, value)
        if k == "file":
            return self._file_editor(node, p, value)
        if k in ("points2", "points3", "faces", "matrix"):
            return self._table_button(node, p, value)
        if k == "edges":
            return self._edges_editor(node, p, value)
        return self._expr_editor(node, p.name, value)

    def _edges_editor(self, node: Node, p: Param, value: list) -> QWidget:
        """Casillas con el nombre de cada arista; las del cubo, en filas según el eje al que son paralelas."""
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        checks = []
        rows = [p.options[i:i + 4] for i in range(0, len(p.options), 4)]
        axes = ("∥Z", "∥X", "∥Y") if len(p.options) == 12 else ()
        for r, keys in enumerate(rows):
            if axes:
                grid.addWidget(QLabel(axes[r]), r, 0)
            for c, key in enumerate(keys):
                check = QCheckBox(key)
                check.setChecked(key in value)
                grid.addWidget(check, r, c + 1)
                checks.append((key, check))
        for _key, check in checks:
            check.toggled.connect(lambda _=False: self._emit(
                node, p.name, [k for k, ch in checks if ch.isChecked()]))
        box.setToolTip(tr("0 es el lado mínimo y 1 el máximo: x1y1 es la arista vertical en X e Y máximos."))
        return box

    def _vector_editor(self, node: Node, p: Param, value: list) -> QWidget:
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        spins = []
        for i, axis in enumerate("XYZ"[:len(value)]):
            lab = QLabel(axis)
            lab.setObjectName("axis" + axis)
            spin = self._num_spin(p, value[i])
            spin.setRange(-1e7, 1e7)
            grid.addWidget(lab, 0, i * 2)
            grid.addWidget(spin, 0, i * 2 + 1)
            grid.setColumnStretch(i * 2 + 1, 1)
            spins.append(spin)
        for spin in spins:
            spin.valueChanged.connect(lambda _=None: self._emit(node, p.name, [s.value() for s in spins]))
        return box

    def _color_editor(self, node: Node, p: Param, value: str) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        combo = self._guarded(QComboBox())
        combo.setEditable(True)
        combo.addItems(COLOR_NAMES)
        combo.setCurrentText(value)
        swatch = QPushButton()
        swatch.setFixedSize(30, 28)
        swatch.setToolTip(tr("Elegir color…"))

        def paint(text):
            c = QColor(text)
            # El fondo es el color de la pieza tal cual: no pasa por el tema (solo el borde).
            swatch.setStyleSheet(f"background:{c.name() if c.isValid() else '#ffffff'};"
                                 + themed("border:1px solid #CBD1DA;border-radius:6px"))

        def pick():
            c = QColorDialog.getColor(QColor(combo.currentText()), self, tr("Color"))
            if c.isValid():
                combo.setCurrentText(c.name())

        paint(value)
        combo.currentTextChanged.connect(paint)
        combo.currentTextChanged.connect(lambda t: self._emit(node, p.name, t) if QColor(t).isValid() else None)
        swatch.clicked.connect(pick)
        row.addWidget(combo, 1)
        row.addWidget(swatch)
        return box

    def _file_editor(self, node: Node, p: Param, value: str) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit(value)
        edit.setPlaceholderText("pieza.stl")
        button = QPushButton("…")
        button.setFixedWidth(34)

        def browse():
            path = choose_import_file(self, node.kind, self.base_dir)
            if path:
                edit.setText(path)
                self._emit(node, p.name, path)

        edit.editingFinished.connect(lambda: self._emit(node, p.name, edit.text()))
        button.clicked.connect(browse)
        row.addWidget(edit, 1)
        row.addWidget(button)
        return box

    def _table_button(self, node: Node, p: Param, value: list) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        names = {"points2": tr("puntos"), "points3": tr("vértices"), "faces": tr("caras"), "matrix": tr("filas")}
        summary = QLabel(f"{len(value)} {names[p.kind]}")
        summary.setObjectName("caption")
        button = QPushButton(tr("Editar…"))

        def open_editor():
            current = node.params.get(p.name, value)
            if p.kind == "points2":
                res = edit_points(self, tr("Puntos del polígono"), current, 2)
            elif p.kind == "points3":
                res = edit_points(self, tr("Vértices del poliedro"), current, 3)
            elif p.kind == "faces":
                res = edit_faces(self, current)
            else:
                res = edit_matrix(self, current if len(current) == 4 else current + [[0, 0, 0, 1]])
            if res is not None:
                self._emit(node, p.name, res)
                self.refresh()

        button.clicked.connect(open_editor)
        row.addWidget(summary, 1)
        row.addWidget(button)
        return box

    def _expr_editor(self, node: Node, key: str, value: Any) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        edit = QLineEdit(format_value(value))
        edit.setObjectName("exprEdit")
        edit.setToolTip(tr("Expresión OpenSCAD. Escribe un valor literal (10, [1, 2, 3], true, \"texto\") "
                           "para volver al editor normal."))

        def commit():
            new = literal(edit.text()) if edit.text().strip() else None
            if new is None:
                return
            old = node.params.get(key)
            if new != old:
                self._emit(node, key, new)
                if not isinstance(new, Expr):
                    self.refresh()

        edit.editingFinished.connect(commit)
        row.addWidget(edit, 1)

        vars_list = self.doc.get_variables() if self.doc is not None else []
        if vars_list:
            fx = QPushButton("ƒx")
            fx.setObjectName("fxButton")
            fx.setFixedWidth(28)
            fx.setToolTip(tr("Vincular con una variable global del proyecto"))
            menu = QMenu(self)
            for v in vars_list:
                a = menu.addAction(f"{v['name']}  (= {v['value']})")
                a.triggered.connect(lambda _=False, n=v['name']: (edit.setText(n), commit()))
            fx.setMenu(menu)
            row.addWidget(fx)

        return box


def choose_import_file(parent, kind: str, base_dir: str) -> str:
    if kind == "surface":
        filt = tr("Mapas de altura (*.png *.dat);;Todos (*)")
    else:
        filt = tr("Modelos y dibujos (*.stl *.off *.3mf *.amf *.obj *.svg *.dxf *.csg);;"
                  "Mallas 3D (*.stl *.off *.3mf *.amf *.obj);;Dibujos 2D (*.svg *.dxf);;Todos (*)")
    path, _ = QFileDialog.getOpenFileName(parent, tr("Elegir archivo"), base_dir or "", filt)
    if not path:
        return ""
    if base_dir:
        try:
            rel = os.path.relpath(path, base_dir)
            if not rel.startswith(".."):
                path = rel
        except ValueError:  # otra unidad en Windows
            pass
    return path.replace("\\", "/")
