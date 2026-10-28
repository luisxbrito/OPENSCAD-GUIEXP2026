"""Helper interactivo y guía didáctica para las operaciones de OpenSCAD.

Proporciona explicaciones claras en lenguaje natural, diagramas, consejos
profesionales (pro-tips), ejemplos de código y presets/acciones rápidas
con un solo clic para cada tipo de operación (translate, rotate, scale,
mirror, booleanas, extrusiones, hull, minkowski, offset, etc.).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPlainTextEdit, QPushButton,
                               QScrollArea, QSplitter, QVBoxLayout, QWidget)

from ..catalog import SPECS
from ..i18n import tr
from ..model import Document, Node
from .icons import icon


# Definición de catálogo didáctico de helpers para operaciones
OPERATION_HELPERS: dict[str, dict[str, Any]] = {
    "translate": {
        "title": "Mover (translate)",
        "icon": "translate",
        "category": "Transformaciones",
        "summary": "Desplaza las piezas hijas a lo largo de los ejes X, Y y Z.",
        "how_it_works": (
            "El vector [X, Y, Z] define cuántos milímetros se mueve el objeto respecto a su "
            "posición actual. El movimiento es relativo a su sistema de coordenadas local."
        ),
        "pro_tip": "💡 Si quieres apoyar una pieza sobre el plano de trabajo XY, desplázala en Z la mitad de su altura (si está centrada) o colócala en Z=0.",
        "example_code": (
            "translate([20, 0, 10]) {\n"
            "    cube([10, 10, 10], center = true); // Se mueve 20mm en X y 10mm en Z\n"
            "}"
        ),
        "presets": [
            ("X +10", lambda p: [p.get("v", [0, 0, 0])[0] + 10, p.get("v", [0, 0, 0])[1], p.get("v", [0, 0, 0])[2]], "v"),
            ("X -10", lambda p: [p.get("v", [0, 0, 0])[0] - 10, p.get("v", [0, 0, 0])[1], p.get("v", [0, 0, 0])[2]], "v"),
            ("Y +10", lambda p: [p.get("v", [0, 0, 0])[0], p.get("v", [0, 0, 0])[1] + 10, p.get("v", [0, 0, 0])[2]], "v"),
            ("Y -10", lambda p: [p.get("v", [0, 0, 0])[0], p.get("v", [0, 0, 0])[1] - 10, p.get("v", [0, 0, 0])[2]], "v"),
            ("Z +10", lambda p: [p.get("v", [0, 0, 0])[0], p.get("v", [0, 0, 0])[1], p.get("v", [0, 0, 0])[2] + 10], "v"),
            ("Z -10", lambda p: [p.get("v", [0, 0, 0])[0], p.get("v", [0, 0, 0])[1], p.get("v", [0, 0, 0])[2] - 10], "v"),
            ("Z = 0 (Base)", lambda p: [p.get("v", [0, 0, 0])[0], p.get("v", [0, 0, 0])[1], 0.0], "v"),
            ("Origen [0,0,0]", lambda p: [0.0, 0.0, 0.0], "v"),
        ],
    },
    "rotate": {
        "title": "Rotar (rotate)",
        "icon": "rotate",
        "category": "Transformaciones",
        "summary": "Gira las piezas hijas alrededor de los ejes X, Y y Z en grados sexagesimales.",
        "how_it_works": (
            "El vector [aX, aY, aZ] indica el ángulo de giro en grados. "
            "El giro se realiza alrededor del origen de coordenadas (0,0,0), salvo que se combine "
            "con un translate previo para cambiar el punto de pivote."
        ),
        "pro_tip": "💡 En OpenSCAD, el orden de rotación es Z, luego Y, luego X (rotación de Euler intrínseca).",
        "example_code": (
            "rotate([0, 0, 45]) {\n"
            "    cube([20, 10, 5], center = true); // Girado 45° en el plano horizontal\n"
            "}"
        ),
        "presets": [
            ("↺ X +90°", lambda p: [(p.get("a", [0, 0, 0])[0] + 90) % 360, p.get("a", [0, 0, 0])[1], p.get("a", [0, 0, 0])[2]], "a"),
            ("↺ Y +90°", lambda p: [p.get("a", [0, 0, 0])[0], (p.get("a", [0, 0, 0])[1] + 90) % 360, p.get("a", [0, 0, 0])[2]], "a"),
            ("↺ Z +90°", lambda p: [p.get("a", [0, 0, 0])[0], p.get("a", [0, 0, 0])[1], (p.get("a", [0, 0, 0])[2] + 90) % 360], "a"),
            ("↺ Z +45°", lambda p: [p.get("a", [0, 0, 0])[0], p.get("a", [0, 0, 0])[1], (p.get("a", [0, 0, 0])[2] + 45) % 360], "a"),
            ("↺ Z 180°", lambda p: [p.get("a", [0, 0, 0])[0], p.get("a", [0, 0, 0])[1], (p.get("a", [0, 0, 0])[2] + 180) % 360], "a"),
            ("Restablecer [0,0,0]", lambda p: [0.0, 0.0, 0.0], "a"),
        ],
    },
    "scale": {
        "title": "Escalar (scale)",
        "icon": "scale",
        "category": "Transformaciones",
        "summary": "Multiplica el tamaño de los sólidos por un factor independiente en X, Y, Z.",
        "how_it_works": (
            "Un factor mayor que 1 amplía el objeto; entre 0 y 1 lo reduce. "
            "Un factor negativo invierte el objeto a lo largo de ese eje (efecto espejo)."
        ),
        "pro_tip": "💡 Para agrandar todo proporcionalmente, usa el mismo valor en los tres ejes [s, s, s].",
        "example_code": (
            "scale([2, 1, 0.5]) {\n"
            "    sphere(r = 10); // Doble de ancho en X y mitad de alto en Z (elipsoide)\n"
            "}"
        ),
        "presets": [
            ("2x Doble", lambda p: [2.0, 2.0, 2.0], "v"),
            ("0.5x Mitad", lambda p: [0.5, 0.5, 0.5], "v"),
            ("Espejo X [-1]", lambda p: [-1.0, 1.0, 1.0], "v"),
            ("Espejo Y [-1]", lambda p: [1.0, -1.0, 1.0], "v"),
            ("Restablecer [1,1,1]", lambda p: [1.0, 1.0, 1.0], "v"),
        ],
    },
    "mirror": {
        "title": "Espejo (mirror)",
        "icon": "mirror",
        "category": "Transformaciones",
        "summary": "Refleja los sólidos a través de un plano que pasa por el origen perpendicular al vector normal.",
        "how_it_works": (
            "El vector [X, Y, Z] es la dirección perpendicular al plano de reflexión. "
            "[1,0,0] refleja a través del plano YZ (invierte X). [0,1,0] a través del plano XZ. [0,0,1] a través del XY."
        ),
        "pro_tip": "💡 Si quieres conservar tanto la pieza original como su reflejo simétrico, agrupa ambas con union().",
        "example_code": (
            "mirror([1, 0, 0]) {\n"
            "    cube([15, 10, 5]); // Reflejado horizontalmente en el eje X\n"
            "}"
        ),
        "presets": [
            ("Plano YZ [X]", lambda p: [1.0, 0.0, 0.0], "v"),
            ("Plano XZ [Y]", lambda p: [0.0, 1.0, 0.0], "v"),
            ("Plano XY [Z]", lambda p: [0.0, 0.0, 1.0], "v"),
        ],
    },
    "color": {
        "title": "Color (color)",
        "icon": "color",
        "category": "Transformaciones",
        "summary": "Asigna un color y opacidad visual al sólido para previsualización y render.",
        "how_it_works": (
            "Se puede especificar con nombre de color estándar en inglés ('SteelBlue', 'Tomato', 'Gold') "
            "o vector RGBA [r, g, b, a] con valores entre 0.0 y 1.0."
        ),
        "pro_tip": "💡 El parámetro alpha (0 a 1) permite crear piezas transparentes o translúcidas muy útiles para ver mecanismos interiores.",
        "example_code": (
            "color(\"SteelBlue\", alpha = 0.8) {\n"
            "    cylinder(h = 20, r = 5); // Cilindro azul semitransparente\n"
            "}"
        ),
        "presets": [
            ("SteelBlue", lambda p: "SteelBlue", "c"),
            ("Tomato", lambda p: "Tomato", "c"),
            ("Gold", lambda p: "Gold", "c"),
            ("SeaGreen", lambda p: "SeaGreen", "c"),
            ("DimGray", lambda p: "DimGray", "c"),
            ("Purple", lambda p: "Purple", "c"),
            ("Opaco 1.0", lambda p: 1.0, "alpha"),
            ("Semivisible 0.5", lambda p: 0.5, "alpha"),
        ],
    },
    "difference": {
        "title": "Restar (difference)",
        "icon": "difference",
        "category": "Operaciones booleanas",
        "summary": "Resta uno o varios sólidos de un sólido base (cortes, taladros y cajeados).",
        "how_it_works": (
            "¡Regla de oro de OpenSCAD!: El PRIMER hijo es el sólido base (positivo, minuendo). "
            "Todos los hijos subsiguientes (2º, 3º...) se restan (negativos, sustraendos) de esa base."
        ),
        "pro_tip": "💡 Evita caras coincidentes (Z-fighting): haz que los cilindros de agujero sobresalgan ligeramente (ej. +0.02mm o +1mm) por ambos extremos del corte para garantizar una resta limpia sin paredes infinitamente delgadas.",
        "example_code": (
            "difference() {\n"
            "    cube([40, 40, 10], center = true); // 1. Base (+)\n"
            "    cylinder(h = 12, r = 5, center = true); // 2. Taladro que resta (-)\n"
            "}"
        ),
        "presets": [],
    },
    "union": {
        "title": "Unir (union)",
        "icon": "union",
        "category": "Operaciones booleanas",
        "summary": "Fusiona múltiples sólidos en un único cuerpo volumétrico continuo.",
        "how_it_works": (
            "Une todos los hijos. Los volúmenes que se intersecan se fusionan automáticamente, "
            "eliminando las superficies interiores intermedias."
        ),
        "pro_tip": "💡 En OpenSCAD, los sólidos colocados uno junto a otro en la raíz ya tienen una unión implícita. Usar union() explícito es útil para aplicar transformaciones conjuntas o como base de una resta.",
        "example_code": (
            "union() {\n"
            "    cube([20, 20, 10], center = true);\n"
            "    cylinder(h = 25, r = 4, center = true);\n"
            "}"
        ),
        "presets": [],
    },
    "intersection": {
        "title": "Intersecar (intersection)",
        "icon": "intersection",
        "category": "Operaciones booleanas",
        "summary": "Conserva únicamente el volumen compartido donde todos los sólidos hijos coinciden.",
        "how_it_works": (
            "Deja solo la región del espacio tridimensional cubierta simultáneamente por todos los sólidos. "
            "Cualquier parte que no pertenezca a todos los hijos a la vez desaparece."
        ),
        "pro_tip": "💡 Es excelente para crear lentes, perfiles curvos compuestos y recortar formas complejas dentro de un límite definido.",
        "example_code": (
            "intersection() {\n"
            "    cube([20, 20, 20], center = true);\n"
            "    sphere(r = 13);\n"
            "}"
        ),
        "presets": [],
    },
    "linear_extrude": {
        "title": "Extruir lineal (linear_extrude)",
        "icon": "linear_extrude",
        "category": "2D a 3D",
        "summary": "Convierte una forma 2D plana en un sólido 3D estirándola verticalmente a lo largo del eje Z.",
        "how_it_works": (
            "Toma las formas 2D hijas (square, circle, polygon, text) y las proyecta hacia arriba "
            "según el parámetro 'height'. Soporta torsión ('twist') y escala progresiva ('scale')."
        ),
        "pro_tip": "💡 Las formas hijas deben ser estrictamente 2D. No intentes extruir un cubo o esfera 3D.",
        "example_code": (
            "linear_extrude(height = 15, center = false, twist = 0) {\n"
            "    circle(r = 10);\n"
            "}"
        ),
        "presets": [
            ("5 mm", lambda p: 5.0, "height"),
            ("10 mm", lambda p: 10.0, "height"),
            ("20 mm", lambda p: 20.0, "height"),
            ("Centrado Sí/No", lambda p: not p.get("center", False), "center"),
            ("Twist 90°", lambda p: 90.0, "twist"),
            ("Cono scale=0.5", lambda p: 0.5, "scale"),
        ],
    },
    "rotate_extrude": {
        "title": "Revolución (rotate_extrude)",
        "icon": "rotate_extrude",
        "category": "2D a 3D",
        "summary": "Gira una forma 2D alrededor del eje Z para crear sólidos de revolución (anillos, botellas, poleas).",
        "how_it_works": (
            "Toma una figura 2D situada en el semiplano derecho (X >= 0) y la hace girar en torno al eje vertical Z. "
            "El parámetro 'angle' controla el arco en grados (360° para un sólido cerrado completo)."
        ),
        "pro_tip": "💡 ¡Crítico!: La forma 2D debe estar completamente en X >= 0. Si cruza el eje Y a X negativa, OpenSCAD generará un error de manifold.",
        "example_code": (
            "rotate_extrude(angle = 360, $fn = 64) {\n"
            "    translate([20, 0]) circle(r = 5); // Crea un toroide (dona)\n"
            "}"
        ),
        "presets": [
            ("360° Completo", lambda p: 360.0, "angle"),
            ("180° Mitad", lambda p: 180.0, "angle"),
            ("90° Cuarto", lambda p: 90.0, "angle"),
            ("Alta suave ($fn=64)", lambda p: 64, "$fn"),
        ],
    },
    "offset": {
        "title": "Desfase 2D (offset)",
        "icon": "offset",
        "category": "Formas 2D",
        "summary": "Expande, contrae o redondea el contorno de formas bidimensionales.",
        "how_it_works": (
            "Aplica una dilatación (r > 0) o erosión (r < 0) sobre curvas y polígonos 2D. "
            "Con 'r' redondea las esquinas; con 'delta' y 'chamfer' crea chaflanes biselados."
        ),
        "pro_tip": "💡 Para hacer esquinas redondeadas en cualquier rectángulo o polígono, aplica offset(r=3) y luego offset(delta=-3).",
        "example_code": (
            "offset(r = 3) {\n"
            "    square([30, 20], center = true); // Rectángulo con esquinas redondeadas R3\n"
            "}"
        ),
        "presets": [
            ("Radio R=2", lambda p: 2.0, "r"),
            ("Radio R=5", lambda p: 5.0, "r"),
            ("Delta +1", lambda p: 1.0, "delta"),
            ("Delta -1", lambda p: -1.0, "delta"),
            ("Chaflán Sí/No", lambda p: not p.get("chamfer", False), "chamfer"),
        ],
    },
    "hull": {
        "title": "Envolvente convexa (hull)",
        "icon": "hull",
        "category": "Avanzado",
        "summary": "Calcula la envolvente convexa continua envolviendo todos los sólidos hijos como una banda elástica.",
        "how_it_works": (
            "Conecta dos o más figuras creando una transición continua y suave entre ellas. "
            "Es ideal para crear brazos mecánicos, bielas, mangos redondeados y soportes orgánicos."
        ),
        "pro_tip": "💡 Crea ranuras o chaveteros uniendo dos cilindros separados con hull().",
        "example_code": (
            "hull() {\n"
            "    translate([-15, 0, 0]) cylinder(h = 5, r = 5, center = true);\n"
            "    translate([15, 0, 0]) cylinder(h = 5, r = 8, center = true);\n"
            "}"
        ),
        "presets": [],
    },
    "minkowski": {
        "title": "Suma de Minkowski (minkowski)",
        "icon": "minkowski",
        "category": "Avanzado",
        "summary": "Suma matemática de dos formas: desplaza la segunda figura sobre cada punto de la primera.",
        "how_it_works": (
            "Es el método más potente para redondear todas las aristas de un sólido 3D sumándole una pequeña esfera o cilindro. "
            "Atención: puede ser muy exigente en tiempo de cálculo si el $fn es alto."
        ),
        "pro_tip": "💡 Mantén $fn bajo (ej. 8 o 16) mientras diseñas para que el visor responda rápido, y súbelo solo para la exportación final.",
        "example_code": (
            "minkowski() {\n"
            "    cube([30, 20, 10], center = true);\n"
            "    sphere(r = 2, $fn = 16); // Redondea todas las aristas del cubo con radio 2mm\n"
            "}"
        ),
        "presets": [],
    },
}


class OperationHelperWidget(QFrame):
    """Widget compacto que se inserta en el panel de propiedades con explicaciones y presets rápidos."""
    presetApplied = Signal(str, object)  # (param_name, new_value)
    openFullGuideRequested = Signal(str)  # kind

    def __init__(self, kind: str, current_params: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.kind = kind
        self.params = current_params
        self.setObjectName("operationHelperBox")
        self.setStyleSheet(
            "QFrame#operationHelperBox { background-color: #F8FAFC; border: 1px solid #CBD5E1; "
            "border-radius: 8px; padding: 10px; margin-top: 6px; }"
        )
        self._build_ui()

    def _build_ui(self) -> None:
        info = OPERATION_HELPERS.get(self.kind)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        if not info:
            # Helper genérico si no está en la lista detallada
            spec = SPECS.get(self.kind)
            label = spec.label if spec else self.kind
            lay.addWidget(QLabel(f"💡 <b>Helper: {label} ({self.kind})</b>"))
            if spec and spec.hint:
                lay.addWidget(QLabel(tr(spec.hint)))
            return

        # Encabezado
        head = QHBoxLayout()
        icon_w = QLabel()
        ico = icon(info.get("icon", self.kind), "#1E293B")
        if callable(getattr(ico, "pixmap", None)):
            try:
                icon_w.setPixmap(ico.pixmap(18, 18))
            except Exception:
                pass
        title = QLabel(f"<b>{tr('Helper')}: {tr(info['title'])}</b>")
        title.setStyleSheet("color: #0F172A; font-size: 12px;")
        head.addWidget(icon_w)
        head.addWidget(title)
        head.addStretch(1)
        lay.addLayout(head)

        # Resumen conciso
        summary = QLabel(tr(info["summary"]))
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #475569; font-size: 11px;")
        lay.addWidget(summary)

        # Pro-tip si existe
        if "pro_tip" in info:
            tip = QLabel(tr(info["pro_tip"]))
            tip.setWordWrap(True)
            tip.setStyleSheet(
                "background-color: #EFF6FF; border-left: 3px solid #3B82F6; color: #1E40AF; "
                "padding: 5px 8px; font-size: 10px; border-radius: 3px;"
            )
            lay.addWidget(tip)

        # Botones de presets / acciones rápidas si tiene
        presets = info.get("presets", [])
        if presets:
            lbl_actions = QLabel(f"<b>{tr('Acciones rápidas (1 clic)')}:</b>")
            lbl_actions.setStyleSheet("color: #334155; font-size: 11px; margin-top: 4px;")
            lay.addWidget(lbl_actions)

            grid = QGridLayout()
            grid.setSpacing(4)
            for idx, (btn_text, fn, param_key) in enumerate(presets):
                b = QPushButton(tr(btn_text))
                b.setStyleSheet(
                    "QPushButton { background: #FFFFFF; border: 1px solid #CBD5E1; "
                    "border-radius: 4px; padding: 4px 6px; font-size: 10px; color: #1E293B; } "
                    "QPushButton:hover { background: #F1F5F9; border-color: #94A3B8; }"
                )
                b.clicked.connect(lambda _=False, f=fn, k=param_key: self._on_preset_clicked(f, k))
                grid.addWidget(b, idx // 2, idx % 2)
            lay.addLayout(grid)

        # Botón para abrir la guía completa
        btn_guide = QPushButton(f"📖 {tr('Ver guía completa y ejemplos…')}")
        btn_guide.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #2563EB; "
            "font-size: 11px; text-decoration: underline; text-align: left; padding: 2px 0px; margin-top: 4px; } "
            "QPushButton:hover { color: #1D4ED8; }"
        )
        btn_guide.clicked.connect(lambda: self.openFullGuideRequested.emit(self.kind))
        lay.addWidget(btn_guide)

    def _on_preset_clicked(self, fn: Callable[[dict], Any], param_key: str) -> None:
        try:
            new_val = fn(self.params)
            self.presetApplied.emit(param_key, new_val)
        except Exception:
            pass


class OperationHelperDialog(QDialog):
    """Diálogo completo que actúa como centro de ayuda y documentación interactiva de todas las operaciones."""

    def __init__(self, current_kind: str = "translate", doc: Optional[Document] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle(tr("Guía y Helper de Operaciones OpenSCAD"))
        self.resize(820, 580)
        self.setMinimumSize(700, 480)
        self.current_kind = current_kind
        self._build_ui()

    def _build_ui(self) -> None:
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(14, 12, 14, 12)
        main_lay.setSpacing(10)

        # Barra superior con buscador
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        lbl_search = QLabel(f"🔍 {tr('Buscar operación')}:")
        lbl_search.setStyleSheet("font-weight: 500;")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(tr("Ej: translate, rotate, difference, extrude..."))
        self.search_box.textChanged.connect(self._filter_list)
        top_bar.addWidget(lbl_search)
        top_bar.addWidget(self.search_box, 1)
        main_lay.addLayout(top_bar)

        # Splitter central: lista a la izquierda, detalles a la derecha
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel izquierdo: lista de operaciones
        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(220)
        self._populate_list()
        self.list_widget.currentItemChanged.connect(self._on_item_changed)
        splitter.addWidget(self.list_widget)

        # Panel derecho: scroll area con explicación detallada
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.detail_widget = QWidget()
        self.detail_lay = QVBoxLayout(self.detail_widget)
        self.detail_lay.setContentsMargins(12, 10, 12, 10)
        self.detail_lay.setSpacing(12)
        scroll.setWidget(self.detail_widget)
        splitter.addWidget(scroll)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)
        main_lay.addWidget(splitter, 1)

        # Botones inferiores
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.button(QDialogButtonBox.StandardButton.Close).setText(tr("Cerrar"))
        btn_box.rejected.connect(self.reject)
        main_lay.addWidget(btn_box)

        # Seleccionar el ítem inicial
        self._select_kind(self.current_kind)

    def _populate_list(self) -> None:
        self.list_widget.clear()
        for k, info in OPERATION_HELPERS.items():
            item = QListWidgetItem()
            item.setIcon(icon(info.get("icon", k), "#1E293B"))
            item.setText(f"{info['title']}  [{info.get('category', '')}]")
            item.setData(Qt.ItemDataRole.UserRole, k)
            self.list_widget.addItem(item)

    def _filter_list(self, text: str) -> None:
        q = text.lower().strip()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            k = item.data(Qt.ItemDataRole.UserRole)
            info = OPERATION_HELPERS.get(k, {})
            visible = (q in k.lower() or q in info.get("title", "").lower()
                       or q in info.get("summary", "").lower() or q in info.get("category", "").lower())
            item.setHidden(not visible)

    def _select_kind(self, kind: str) -> None:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == kind:
                self.list_widget.setCurrentItem(item)
                break

    def _on_item_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        if current is None:
            return
        kind = current.data(Qt.ItemDataRole.UserRole)
        self._show_details(kind)

    def _show_details(self, kind: str) -> None:
        # Limpiar layout
        while self.detail_lay.count():
            item = self.detail_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        info = OPERATION_HELPERS.get(kind, {})
        if not info:
            return

        # Título e icono
        head = QHBoxLayout()
        ic = QLabel()
        ico = icon(info.get("icon", kind), "#1E293B")
        if callable(getattr(ico, "pixmap", None)):
            try:
                ic.setPixmap(ico.pixmap(28, 28))
            except Exception:
                pass
        t = QLabel(f"<h2>{info['title']}</h2>")
        head.addWidget(ic)
        head.addWidget(t)
        head.addStretch(1)
        self.detail_lay.addLayout(head)

        cat_badge = QLabel(f"<b>Categoría:</b> {info.get('category', 'General')}")
        cat_badge.setStyleSheet("color: #64748B; font-size: 11px;")
        self.detail_lay.addWidget(cat_badge)

        # Resumen
        sum_box = QLabel(info.get("summary", ""))
        sum_box.setWordWrap(True)
        sum_box.setStyleSheet("font-size: 13px; font-weight: 500; color: #1E293B;")
        self.detail_lay.addWidget(sum_box)

        # ¿Cómo funciona?
        self.detail_lay.addWidget(QLabel(f"<h3>{tr('¿Cómo funciona?')}</h3>"))
        how = QLabel(info.get("how_it_works", ""))
        how.setWordWrap(True)
        how.setStyleSheet("line-height: 1.4; color: #334155;")
        self.detail_lay.addWidget(how)

        # Pro-tip
        if "pro_tip" in info:
            tip = QLabel(info["pro_tip"])
            tip.setWordWrap(True)
            tip.setStyleSheet(
                "background-color: #FEF3C7; border-left: 4px solid #F59E0B; "
                "color: #92400E; padding: 8px 12px; font-size: 11px; border-radius: 4px;"
            )
            self.detail_lay.addWidget(tip)

        # Código de ejemplo
        if "example_code" in info:
            self.detail_lay.addWidget(QLabel(f"<h3>{tr('Ejemplo en OpenSCAD:')}</h3>"))
            code_view = QPlainTextEdit(info["example_code"])
            code_view.setReadOnly(True)
            code_view.setStyleSheet("font-family: monospace; font-size: 11px; background: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 4px;")
            code_view.setMaximumHeight(100)
            self.detail_lay.addWidget(code_view)

        self.detail_lay.addStretch(1)
