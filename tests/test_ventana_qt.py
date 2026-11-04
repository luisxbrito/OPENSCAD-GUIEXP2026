"""Pruebas con el Qt real (PySide6 y pyqtgraph instalados), sin mostrar la ventana.

Mandan eventos de ratón de verdad a la vista 3D, que es lo que las simulaciones de
tests/simulacion no pueden comprobar. Si falta PySide6 o pyqtgraph, se omiten.

Usa la configuración guardada del programa (salvo el idioma: siempre en español): si el visor está puesto en
"imágenes" en Preferencias, estas pruebas no se pueden hacer.

Ejecutar:  python tests/test_ventana_qt.py
"""

import math
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # sin ventana; OpenGL no hace falta para los eventos
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

try:
    import numpy as np
    import pyqtgraph  # noqa: F401
    from PySide6.QtCore import QPoint, QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
except ImportError as exc:
    print(f"Falta {exc.name}: se omiten estas pruebas")
    sys.exit(0)

app = QApplication.instance() or QApplication(sys.argv)
import scadgui.ui.mainwindow as mw  # noqa: E402

LEFT, NONE = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier


def window():
    settings = QSettings("OpenSCAD-GUI-Mejorada", "app")
    saved = settings.value("language")
    settings.setValue("language", "es")   # las pruebas miran textos en español, sea cual sea el guardado
    try:
        w = mw.MainWindow("")
    finally:
        if saved is None:
            settings.remove("language")
        else:
            settings.setValue("language", saved)
    w.resize(1400, 900)
    w.show()
    app.processEvents()   # el arranque (en blanco) se hace en el primer ciclo de eventos
    w.open_example(mw.EXAMPLE_PLACA)
    app.processEvents()
    assert w.gl, w._gl_error
    return w


def pixel_of(view, p) -> QPoint:
    """Píxel por el que se ve el punto p (inversa de _GLView.ray)."""
    cam, _ = view.ray(view.width() / 2, view.height() / 2)
    c = view.opts["center"]
    fwd = np.array([c.x(), c.y(), c.z()]) - cam
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 0, 1.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    d = np.asarray(p, float) - cam
    tx = math.tan(math.radians(view.opts["fov"]) / 2)
    ty = tx * view.height() / view.width()
    nx, ny = (d @ right) / (d @ fwd) / tx, (d @ up) / (d @ fwd) / ty
    return QPoint(round((nx + 1) / 2 * view.width()), round((1 - ny) / 2 * view.height()))


def test_clic_en_el_vacio_deselecciona():
    """Antes, un clic cerca de la pieza seleccionada agarraba el gizmo y no deseleccionaba."""
    w = window()
    v, view = w.viewer, w.viewer.view
    cube = w.doc.children[0].children[0]
    tried = 0
    for x in range(10, view.width(), 40):
        for y in range(10, view.height(), 40):
            w.select_ids([cube.id])
            o, d = view.ray(x, y)
            if v._get_picker().pick(o, d)[0] is not None:
                continue  # ahí hay una pieza
            tried += 1
            QTest.mouseClick(view, LEFT, NONE, QPoint(x, y))
            assert w.selected_ids() == [], (x, y)
    assert tried > 50


def test_gizmo_arrastrar_mueve_y_clic_no_deja_rastro():
    w = window()
    view = w.viewer.view
    cube = w.doc.children[0].children[0]
    w.select_ids([cube.id])
    tip = pixel_of(view, view.gizmo_origin + [0.8 * view.gizmo_len, 0, 0])
    QTest.mousePress(view, LEFT, NONE, tip)
    assert view._active_axis == "X"
    for k in range(1, 6):
        QTest.mouseMove(view, tip + QPoint(8 * k, 0))
    QTest.mouseRelease(view, LEFT, NONE, tip + QPoint(40, 0))
    assert any(n.kind == "translate" and n.children == [cube] for n, _, _ in w.doc.walk())
    w.undo()
    w.select_ids([cube.id])
    steps = len(w.history.undo_stack)
    tip = pixel_of(view, view.gizmo_origin + [0.8 * view.gizmo_len, 0, 0])
    QTest.mouseClick(view, LEFT, NONE, tip)   # el extremo del eje queda fuera de la pieza
    assert len(w.history.undo_stack) == steps and w.selected_ids() == []



def test_panel_avisa_y_corrige_radios_que_chocan():
    from PySide6.QtWidgets import QPushButton
    from scadgui.i18n import tr
    from scadgui.parser import parse
    w = window()
    w.set_document(parse("cylinder(h = 10, r = 1, d2 = 4, center = true);"))
    cyl = w.doc.children[0]
    w.select_ids([cyl.id])
    app.processEvents()
    fix = [b for b in w.props.findChildren(QPushButton) if b.text() == tr("Corregir (misma forma)")]
    assert len(fix) == 1
    fix[0].click()
    app.processEvents()
    assert "cylinder(h = 10, r1 = 1, d2 = 4, center = true);" in w.code.text.toPlainText()
    w.undo()
    assert "r = 1, d2 = 4" in w.code.text.toPlainText()



def test_arbol_sobre_el_visor():
    """El mismo árbol pasa al visor y vuelve: la selección y los clics siguen funcionando."""
    from PySide6.QtCore import QSettings
    settings = QSettings("OpenSCAD-GUI-Mejorada", "app")
    saved = settings.value("tree_overlay")            # la prueba no debe cambiar la configuración
    w = window()
    w.set_tree_overlay(False)                       # sin depender de cómo quedó la configuración
    view = w.viewer.view
    cube = w.doc.children[0].children[0]
    w.viewer.tree_btn.click()                       # botón «Árbol» de la barra del visor
    app.processEvents()
    assert w.a_tree_overlay.isChecked() and w.viewer.tree_overlay.isVisible()
    parent, chain = w.tree.parentWidget(), []
    while parent is not None:
        chain.append(parent)
        parent = parent.parentWidget()
    assert view in chain                             # el árbol está dentro del visor
    item = w._item_for(cube.id)
    rect = w.tree.visualItemRect(item)
    QTest.mouseClick(w.tree.viewport(), LEFT, NONE, rect.center())
    assert w.selected_ids() == [cube.id]
    assert w.viewer.selection.x() > w.viewer.tree_overlay.width()   # la etiqueta no queda debajo
    w.viewer.tree_overlay_fold.click()               # plegar: solo la cabecera
    app.processEvents()
    assert not w.viewer.tree_overlay_body.isVisible() and w.viewer.tree_overlay.height() < 60
    w.a_tree_overlay.setChecked(False)               # menú Ver: vuelve al panel Modelo
    app.processEvents()
    assert w.tree.parentWidget() is w.model_split and not w.viewer.tree_overlay.isVisible()
    assert not w.viewer.tree_btn.isChecked()
    if saved is None:
        settings.remove("tree_overlay")
    else:
        settings.setValue("tree_overlay", saved)



def test_atajos_marcan_la_vista_actual():
    """Al cambiar de vista con el teclado se marca su botón y su nombre aparece en el visor."""
    from scadgui.i18n import tr
    w = window()
    v = w.viewer
    v.key_command("1")                                # frontal
    assert v.view_buttons["front"].isChecked()
    assert not any(b.isChecked() for k, b in v.view_buttons.items() if k != "front")
    assert v.view_name.text().startswith(tr("Frontal")) and v.view_name.isVisible()
    v.key_command("7", True)                          # Ctrl+7: inferior (sin botón)
    assert not any(b.isChecked() for b in v.view_buttons.values())
    assert v.view_name.text().startswith(tr("Inferior"))
    v.key_command("0")
    v.key_command("4")                                # girar a mano: vista libre
    assert not any(b.isChecked() for b in v.view_buttons.values())
    assert v.view_name.text().startswith(tr("Libre"))
    v.key_command("5")                                # perspectiva -> ortográfica
    assert v.view_name.text().endswith(tr("Ortográfica"))
    v.key_command("5")
    v.view_buttons["top"].click()                     # botón de la barra: también queda marcado
    assert v.view_buttons["top"].isChecked() and v.view_name.text().startswith(tr("Superior"))
    v.view_buttons["top"].click()                     # pulsarlo otra vez no lo desmarca
    assert v.view_buttons["top"].isChecked()


def test_regla_de_los_ejes():
    """Botón y tecla R muestran la regla; al alejar la cámara el paso de los números crece."""
    from PySide6.QtCore import QSettings
    settings = QSettings("OpenSCAD-GUI-Mejorada", "app")
    saved = settings.value("ruler")
    w = window()
    v = w.viewer
    v.set_ruler(False)
    assert not v.ruler_pos[0].visible() and v.axes.visible()
    v.ruler_btn.click()
    assert v.ruler_on and v.ruler_pos[0].visible() and v.ruler_neg[2].visible() and not v.axes.visible()
    v.view.setCameraPosition(distance=100)
    near = v._ruler_key[0]
    v.view.setCameraPosition(distance=1000)               # 10 veces más lejos: paso 10 veces mayor
    assert math.isclose(v._ruler_key[0], near * 10), (near, v._ruler_key)
    texts = v.ruler_texts()
    assert not v.ruler_labels or (texts and all(t.lstrip("-").replace(".", "").isdigit() for t in texts))
    # Un número dentro de la pieza no se ve: se oculta (los textos de pyqtgraph no tienen profundidad).
    from scadgui.parser import parse
    w.set_document(parse("cube(120, center = true);"))
    app.processEvents()
    v.view.setCameraPosition(distance=300, elevation=30, azimuth=-55)
    v._hide_covered_labels()
    shown = {(round(float(p[0])), round(float(p[1])), round(float(p[2]))): item.visible()
             for item, p in zip(v.ruler_labels, v._label_points)}
    if shown:
        inside = [vis for (x, y, z), vis in shown.items() if max(abs(x), abs(y), abs(z)) < 55]
        assert inside and not any(inside), shown
        assert any(shown.values())
    v.key_command("R")                                    # tecla R: la quita
    assert not v.ruler_on and not v.ruler_btn.isChecked() and not v.ruler_pos[0].visible()
    if saved is None:
        settings.remove("ruler")
    else:
        settings.setValue("ruler", saved)



def test_boton_ajustar_encuadra():
    """El botón «Ajustar» encuadra el modelo aunque la cámara esté lejos y descentrada."""
    import pyqtgraph as pg
    from scadgui.i18n import tr
    w = window()
    v = w.viewer
    v.view.setCameraPosition(pos=pg.Vector(500, 500, 500), distance=5000)
    from PySide6.QtWidgets import QPushButton
    button = next(b for b in v.findChildren(QPushButton) if b.text() == tr("Ajustar"))
    button.click()
    app.processEvents()
    lo, hi = v._scene_box()
    center = v.view.opts["center"]
    assert np.allclose([center.x(), center.y(), center.z()], (lo + hi) / 2, atol=1e-3)
    assert v.view.opts["distance"] < 1000


def test_rejilla_desde_el_menu_y_con_la_tecla_g():
    """La rejilla se oculta con Ver › Rejilla o con la tecla G, y el menú Ver sobrevive al cambio de idioma."""
    from PySide6.QtCore import QSettings
    from scadgui.i18n import set_language, tr
    settings = QSettings("OpenSCAD-GUI-Mejorada", "app")
    saved = settings.value("grid")
    w = window()
    v = w.viewer
    v.set_grid(True)
    assert v.grid.visible() and w.a_grid.isChecked()
    v.key_command("G")                                     # tecla G en el visor
    assert not v.grid.visible() and not w.a_grid.isChecked()
    w.a_grid.trigger()                                     # menú Ver › Rejilla
    assert v.grid.visible() and w.a_grid.isChecked()
    set_language("en")
    w.retranslate_ui()
    texts = [a.text() for a in w.view_menu.actions()]
    set_language("es")
    w.retranslate_ui()
    assert "Grid\tG" in texts and "Tree over the 3D view" in texts, texts
    assert w.a_grid in w.view_menu.actions() and w.a_gl in w.view_menu.actions()
    w.code.start_editing()                                 # escribir una G en el código no la oculta
    w.code.text.setFocus()
    QTest.keyClick(w.code.text, Qt.Key.Key_G)
    app.processEvents()
    assert v.grid.visible() and w.code.text.toPlainText().count("G") > 0
    w.code.stop_editing(discard=True)
    if saved is None:
        settings.remove("grid")
    else:
        settings.setValue("grid", saved)


def test_mensaje_del_visor_en_el_idioma_de_la_interfaz():
    """El aviso del visor vacío sale traducido y cambia al cambiar de idioma."""
    from scadgui.i18n import set_language
    from scadgui.model import Document
    w = window()
    w.set_document(Document())
    w.render_view(False)
    app.processEvents()
    assert w.viewer.message.text().startswith("Crea una pieza"), w.viewer.message.text()
    set_language("en")
    try:
        w.retranslate_ui()
        app.processEvents()
        assert w.viewer.message.text() == "Create a part with the buttons above to see it here.", w.viewer.message.text()
    finally:
        set_language("es")
        w.retranslate_ui()


def test_gizmo_con_flechas_y_se_puede_apagar():
    """Las puntas del gizmo son conos en el extremo de cada eje; Ver › Flechas lo enciende y apaga."""
    from PySide6.QtCore import QSettings
    settings = QSettings("OpenSCAD-GUI-Mejorada", "app")
    saved = settings.value("gizmo_enabled")
    w = window()
    v = w.viewer
    w.a_gizmo.setChecked(True)
    cube = w.doc.children[0].children[0]
    w.select_ids([cube.id])
    app.processEvents()
    assert v.gizmo_tips.visible() and v.view.gizmo_origin is not None
    o, L = v.view.gizmo_origin, v.view.gizmo_len
    verts = v.gizmo_tips.opts["meshdata"].vertexes()
    assert np.isclose(verts[:, 0].max(), o[0] + L, atol=1e-3)     # la flecha de X acaba en el extremo
    assert w.a_gizmo in w.view_menu.actions()
    w.a_gizmo.setChecked(False)                                    # apagar
    app.processEvents()
    assert not v.gizmo_tips.visible() and not v.gizmo_lines.visible() and v.view.gizmo_origin is None
    assert settings.value("gizmo_enabled", True, bool) is False
    w.a_gizmo.setChecked(True)
    app.processEvents()
    assert v.gizmo_tips.visible()
    if saved is None:
        settings.remove("gizmo_enabled")
    else:
        settings.setValue("gizmo_enabled", saved)


def test_documento_nuevo_no_deja_rastros_del_anterior():
    """Al abrir otro archivo o empezar uno nuevo no queda nada del anterior en el visor."""
    from scadgui import geometry as geo
    from scadgui.model import Document
    from scadgui.parser import parse
    w = window()
    v = w.viewer
    cube = w.doc.children[0].children[0]
    v.set_mesh(np.concatenate(list(w.ghosts.values())))       # como si OpenSCAD hubiera calculado la malla
    w.select_ids([cube.id])
    v.measure_btn.setChecked(True)
    v._add_measure_point([0, 0, 0])
    w.runner._pending = (("mesh", "x.off", "x.scad", "", "", False), [], "")   # cálculo del anterior en espera
    app.processEvents()
    assert v.model.visible() and v.highlight.visible() and v.measure_dots.visible()
    w.set_document(parse("sphere(5);"))                          # abrir otro archivo
    app.processEvents()
    assert v.real is None and not v.model.visible(), "sigue la malla calculada del archivo anterior"
    assert not v.highlight.visible() and v.view.gizmo_origin is None and not v.measure_dots.visible()
    assert w.runner._pending is None
    box = geo.bbox(v._display_ghosts and np.concatenate(list(v._display_ghosts.values())))
    assert box is not None and np.allclose(box[1], [5, 5, 5], atol=0.5)    # solo la esfera nueva
    v.measure_btn.setChecked(False)
    w.set_document(Document())                                   # Archivo › Nuevo
    app.processEvents()
    assert not v.model.visible() and not v.approx.visible()


def test_panel_modelo_solo_con_seleccion_cuando_el_arbol_esta_en_el_visor():
    """Árbol en el visor: las propiedades flotan a la derecha y solo se ven con algo
    seleccionado, sin cambiar el tamaño del visor; al devolver el árbol vuelve todo al panel."""
    from PySide6.QtCore import QSettings
    settings = QSettings("OpenSCAD-GUI-Mejorada", "app")
    saved = settings.value("tree_overlay")
    w = window()
    w.set_tree_overlay(False)
    w.dock_model.show()
    w.dock_vars.show()
    w.select_ids([])
    w.set_tree_overlay(True)
    app.processEvents()
    v = w.viewer
    assert not w.dock_model.isVisible() and not w.dock_vars.isVisible()
    assert not v.props_overlay.isVisible()
    width = v.view.width()
    cube = w.doc.children[0].children[0]
    item = w._item_for(cube.id)
    QTest.mouseClick(w.tree.viewport(), LEFT, NONE, w.tree.visualItemRect(item).center())   # clic en el árbol
    app.processEvents()
    assert w.selected_ids() == [cube.id]
    assert v.props_overlay.isVisible() and w.props.isVisible()
    assert w.model_panel.parentWidget() is v.props_overlay
    assert v.view.width() == width                    # el visor no cambia de tamaño
    w.select_ids([])
    app.processEvents()
    assert not v.props_overlay.isVisible()
    w.set_tree_overlay(False)                         # árbol de vuelta: propiedades al panel Modelo
    app.processEvents()
    assert w.dock_model.widget() is w.model_panel and w.dock_model.isVisible()
    assert w.dock_vars in w.tabifiedDockWidgets(w.dock_model) and w.dock_vars.toggleViewAction().isChecked()
    if saved is None:
        settings.remove("tree_overlay")
    else:
        settings.setValue("tree_overlay", saved)


def test_esquema_de_color_de_preferencias_se_aplica():
    """El esquema elegido en Preferencias cambia el fondo, el color de las piezas sin color() y,
    con fondo claro, los textos y el árbol sobre el visor pasan a oscuros."""
    from PySide6.QtCore import QSettings
    from scadgui import colorschemes
    from scadgui import geometry as geo
    from scadgui.parser import parse
    settings = QSettings("OpenSCAD-GUI-Mejorada", "app")
    saved = settings.value("colorscheme")
    w = window()
    v = w.viewer
    w.set_document(parse("cube(10);"))
    try:
        settings.setValue("colorscheme", "Cornfield")
        w.apply_color_scheme()
        app.processEvents()
        assert w.runner.colorscheme == "Cornfield"
        assert v.light_background and "viewName" in v.view.styleSheet()
        assert np.allclose(geo.DEFAULT_COLOR[:3], colorschemes.get("Cornfield").rgba()[:3])
        assert tree_icon_dark(w)
        settings.setValue("colorscheme", "Tomorrow Night")
        w.apply_color_scheme()
        assert not v.light_background and v.view.styleSheet() == "" and w.runner.colorscheme == "Tomorrow Night"
    finally:
        if saved is None:
            settings.remove("colorscheme")
        else:
            settings.setValue("colorscheme", saved)
        w.apply_color_scheme()


def tree_icon_dark(w) -> bool:
    """Con el fondo del visor claro, el árbol flotante usa los colores oscuros."""
    return mw.tree_colors(True, w._light_viewer()) == mw.TREE_COLORS[False]


def test_preferencias_que_antes_no_hacian_nada():
    """roof, parámetros extra, factor de explosión, retardo y $fn por defecto se aplican de verdad."""
    from PySide6.QtCore import QSettings
    settings = QSettings("OpenSCAD-GUI-Mejorada", "app")
    keys = ("enable_roof", "extra_flags", "explode_max_mult", "debounce_ms", "default_fn")
    saved = {k: settings.value(k) for k in keys}
    w = window()
    try:
        settings.setValue("enable_roof", True)
        settings.setValue("extra_flags", '--enable=manifold -D "nombre=1"')
        assert w._openscad_args() == ["--enable=roof", "--enable=manifold", "-D", "nombre=1"]
        settings.setValue("enable_roof", False)
        settings.setValue("extra_flags", "")
        assert w._openscad_args() == []
        settings.setValue("default_fn", 48)
        assert w._new_document().fn == 48
        settings.setValue("default_fn", 0)
        assert w._new_document().fn is None
        settings.setValue("debounce_ms", 800)
        settings.setValue("explode_max_mult", 4.0)
        w.apply_settings()
        assert w.viewer._render_timer.interval() == 800
        assert not w.gl or w.viewer.explode_factor == 4.0
    finally:
        for k, v in saved.items():
            settings.remove(k) if v is None else settings.setValue(k, v)
        w.apply_settings()


def test_reiniciar_vuelve_a_abrir_el_mismo_archivo():
    """«Reiniciar ahora» (tema o visor) lanza otra vez la aplicación con el archivo abierto y cierra esta."""
    w = window()
    calls, quits = [], []

    class FakeProcess:
        @staticmethod
        def startDetached(program, args):
            calls.append((program, list(args)))
            return True

    class FakeApp:
        @staticmethod
        def instance():
            return type("A", (), {"quit": staticmethod(lambda: quits.append(1))})

    real = mw.QProcess, mw.QApplication
    mw.QProcess, mw.QApplication = FakeProcess, FakeApp
    try:
        w.path = os.path.join(ROOT, "examples", "rueda_con_eje_giratorio.scad")
        w.restart()
    finally:
        mw.QProcess, mw.QApplication = real
        w.path = ""
    assert quits and calls[0][0] == sys.executable
    assert calls[0][1][-1].endswith("rueda_con_eje_giratorio.scad"), calls


def test_engranaje_desde_la_cinta_y_pareja_desde_el_panel():
    """Botón spur_gear de la cinta → engranaje; el panel muestra sus diámetros y crea la pareja."""
    from PySide6.QtWidgets import QLabel, QPushButton
    from scadgui.i18n import tr
    from scadgui.model import Document
    w = window()
    w.set_document(Document())
    w.ribbon.buttons["spur_gear"].click()
    app.processEvents()
    gear = w.doc.children[0]
    assert gear.kind == "spur_gear" and w.selected_ids() == [gear.id]
    texts = [l.text() for l in w.props.findChildren(QLabel)]
    assert any(t.startswith("Ø primitivo 20 mm") for t in texts), texts         # m = 1, z = 20
    add = next(b for b in w.props.findChildren(QPushButton) if b.text() == tr("Añadir engranaje que engrane"))
    add.click()
    app.processEvents()
    assert [n.kind for n in w.doc.children] == ["spur_gear", "translate"]
    new = w.doc.find(w.selected_ids()[0])
    assert new.kind == "spur_gear" and w.doc.children[1].params["v"] == [20, 0, 0]
    assert "module spur_gear(" in w.code.text.toPlainText()
    w.runner.exe = w.runner.exe or "openscad-que-no-existe"     # con OpenSCAD (aunque falle)…
    w.render_view(False)
    app.processEvents()
    assert not w.viewer.message.text().startswith("Crea una pieza")  # …no queda el aviso de «vacío»
    w.runner.cancel_preview()


def test_polea_desde_la_cinta():
    """Botón pulley de la cinta; el panel calcula sus medidas (sección XL por defecto)."""
    from PySide6.QtWidgets import QLabel
    from scadgui.model import Document
    w = window()
    w.set_document(Document())
    w.ribbon.buttons["pulley"].click()
    app.processEvents()
    pu = w.doc.children[0]
    assert pu.kind == "pulley" and w.selected_ids() == [pu.id]
    texts = [l.text() for l in w.props.findChildren(QLabel)]
    assert any(t.startswith("Paso 5.080 mm · Ø primitivo 32.34 mm") for t in texts), texts
    assert any("grueso en la línea primitiva 2.565 mm" in t for t in texts), texts
    assert "module pulley(" in w.code.text.toPlainText()


def test_asiento_de_rodamiento_en_el_dialogo():
    """El diálogo da la ficha, avisa fuera de tabla y la máscara se resta de la pieza seleccionada."""
    from scadgui.model import Document
    from scadgui.ui import hardware_dialog as hd
    dlg = hd.HardwareDialog(has_selection=True)
    index = next(i for i in range(dlg.combo_type.count()) if dlg.combo_type.itemData(i)[0] == "bearing_seat")
    dlg.combo_type.setCurrentIndex(index)
    assert not dlg.rb_solid.isEnabled() and not dlg.combo_seat.isHidden() and not dlg.spin_wall.isHidden()
    assert dlg.spin_diameter.isHidden() and dlg.combo_seal.isHidden()
    assert "22.35" in dlg.lbl_info.text()                  # 608 impreso, ajuste medio
    dlg.combo_seat.setCurrentIndex(dlg.combo_seat.findData("H7"))
    assert "22.021" in dlg.lbl_info.text()
    dlg.combo_size.setCurrentIndex(dlg.combo_size.findData("624"))    # Ø13 no tiene tolerancia en la tabla
    assert "bearing" not in dlg.lbl_info.text().lower() and "624" not in dlg.lbl_info.text()
    dlg.combo_type.setCurrentIndex(0)
    assert dlg.combo_seat.isHidden() and dlg.spin_wall.isHidden()

    w = window()
    w.set_document(Document())
    w.ribbon.buttons["cube"].click()
    app.processEvents()

    def fake_exec(d):
        d.combo_type.setCurrentIndex(index)
        d.combo_size.setCurrentIndex(d.combo_size.findData("6204"))
        d.combo_seat.setCurrentIndex(d.combo_seat.findData("H7"))
        d.spin_wall.setValue(5)
        return True

    real, hd.HardwareDialog.exec = hd.HardwareDialog.exec, fake_exec
    try:
        w.open_hardware_dialog()
    finally:
        hd.HardwareDialog.exec = real
    app.processEvents()
    root = w.doc.children[0]
    assert root.kind == "difference" and root.children[1].kind == "group"
    code = w.code.text.toPlainText()
    assert "r = 23.506" in code or "r = 23.507" in code
    assert "r = 20.5" in code


def test_ranuras_en_el_dialogo_de_piezas_normalizadas():
    """Las ranuras solo existen como máscara, restan de la selección y piden lo que les hace falta."""
    from scadgui.ui.hardware_dialog import HardwareDialog
    dlg = HardwareDialog(has_selection=True)

    def choose(cat, std):
        for i in range(dlg.combo_type.count()):
            if dlg.combo_type.itemData(i) == (cat, std):
                dlg.combo_type.setCurrentIndex(i)
                return
        raise AssertionError((cat, std))

    choose("ring_groove", "3am1")
    r = dlg.get_result()
    assert (r["category"], r["standard"], r["size"], r["mode"]) == ("ring_groove", "3am1", "20", "hole")
    assert r["subtract"] and not dlg.rb_solid.isEnabled() and not dlg.combo_fit.isEnabled()
    assert dlg.spin_diameter.isHidden() and "18.85" in dlg.lbl_info.text()
    choose("oring_groove", "shaft")
    dlg.spin_diameter.setValue(40)
    r = dlg.get_result()
    assert (r["size"], r["diameter"], r["seal"]) == ("2.62", 40, "static")
    assert not dlg.spin_diameter.isHidden() and not dlg.combo_seal.isHidden() and "Ø40" in dlg.lbl_info.text()
    choose("oring_groove", "face")
    assert dlg.combo_seal.isHidden() and not dlg.spin_diameter.isHidden()
    dlg.spin_diameter.setValue(1)                    # no da para la ranura: sin ficha, sin errores
    assert "o-ring" not in dlg.lbl_info.text()
    choose("washer", "din125")                       # las demás piezas vuelven a ser sólidas
    assert dlg.rb_solid.isEnabled() and dlg.rb_solid.isChecked()
    choose("screw", "iso4762")
    dlg.rb_hole.setChecked(True)
    assert dlg.combo_fit.isEnabled()                 # y conservan su tolerancia


def test_ranura_se_resta_de_la_pieza_seleccionada():
    """Aceptar el diálogo con una pieza seleccionada la mete en un difference con la máscara."""
    from scadgui.model import Document
    from scadgui.ui import hardware_dialog as hd
    w = window()

    def accept_with(cat, std, value=None):
        def fake_exec(dlg):
            for i in range(dlg.combo_type.count()):
                if dlg.combo_type.itemData(i) == (cat, std):
                    dlg.combo_type.setCurrentIndex(i)
            if value is not None:
                dlg.spin_diameter.setValue(value)
            return True
        real, hd.HardwareDialog.exec = hd.HardwareDialog.exec, fake_exec
        try:
            w.open_hardware_dialog()
        finally:
            hd.HardwareDialog.exec = real
        app.processEvents()

    w.set_document(Document())
    w.ribbon.buttons["cylinder"].click()
    app.processEvents()
    cyl = w.doc.children[0]
    accept_with("ring_groove", "3am1")
    root = w.doc.children[0]
    assert root.kind == "difference" and root.children[0] is cyl
    assert root.children[1].kind == "difference" and root.children[1].children[1].children[0].params["r"] == 9.425
    assert w.selected_ids() == [root.children[1].id]
    w.select_ids([root.id])
    accept_with("oring_groove", "shaft", 40)         # se añade al mismo difference, no anida otro
    assert len(root.children) == 3 and w.doc.children == [root]
    code = w.code.text.toPlainText()
    assert "r = 17.917" in code and code.count("difference()") == 3


def test_estriado_desde_la_cinta_y_pareja_desde_el_panel():
    """Botón spline de la cinta; el panel da las medidas y el botón añade el cubo en el mismo sitio."""
    from PySide6.QtWidgets import QLabel, QPushButton
    from scadgui.i18n import tr
    from scadgui.model import Document
    w = window()
    w.set_document(Document())
    w.ribbon.buttons["spline"].click()
    app.processEvents()
    shaft = w.doc.children[0]
    assert shaft.kind == "spline" and w.selected_ids() == [shaft.id]
    texts = [l.text() for l in w.props.findChildren(QLabel)]
    assert any(t.startswith("Ø primitivo 20 mm · Ø base 17.321 mm") for t in texts), texts
    assert any(t.startswith("Eje: Ø mayor 21.000 mm") for t in texts), texts
    next(b for b in w.props.findChildren(QPushButton) if b.text() == tr("Añadir la pieza pareja")).click()
    app.processEvents()
    assert [n.kind for n in w.doc.children] == ["spline", "spline"]
    hub = w.doc.find(w.selected_ids()[0])
    assert hub is w.doc.children[1] and hub.params["internal"] is True
    texts = [l.text() for l in w.props.findChildren(QLabel)]
    assert any(t.startswith("Cubo: Ø mayor 21.500 mm") for t in texts), texts
    assert "module spline(" in w.code.text.toPlainText()


def test_cunero_en_el_panel():
    """El panel da las medidas de la tabla según el agujero y avisa si no están en ella."""
    from PySide6.QtWidgets import QLabel
    from scadgui.model import Document
    w = window()
    for kind in ("spur_gear", "helical_gear", "bevel_gear", "pulley", "v_pulley"):
        w.set_document(Document())
        w.ribbon.buttons[kind].click()
        app.processEvents()
        node = w.doc.children[0]

        def labels(bore):
            w.mutate(lambda: (w.doc.set_param(node.id, "bore", bore), w.doc.set_param(node.id, "keyway", True)),
                     select=[node.id])
            app.processEvents()
            return [l.text() for l in w.props.findChildren(QLabel)]

        texts = labels(20)
        assert any(t.startswith("Cuñero para eje Ø 20: ancho 6 mm") for t in texts), (kind, texts)
        texts = labels(5)
        assert any(t.startswith("La tabla de cuñeros") for t in texts), (kind, texts)
        assert "module shaft_bore(" in w.code.text.toPlainText(), kind


def test_pestanas_de_la_polea_en_el_idioma_de_la_interfaz():
    """El desplegable y el código salen en el idioma elegido; el modelo guarda siempre el mismo valor."""
    from PySide6.QtWidgets import QComboBox
    from scadgui.i18n import set_language
    from scadgui.model import Document
    w = window()
    w.set_document(Document())
    w.ribbon.buttons["pulley"].click()
    app.processEvents()
    pu = w.doc.children[0]
    w.mutate(lambda: w.doc.set_param(pu.id, "flange", "superior"), select=[pu.id])
    set_language("en")
    try:
        w.retranslate_ui()
        w.select_ids([])
        w.select_ids([pu.id])
        app.processEvents()
        combo = next(c for c in w.props.findChildren(QComboBox) if c.findText("both") >= 0)
        assert combo.currentText() == "top"
        assert 'flange = "top"' in w.code.text.toPlainText()
        combo.setCurrentIndex(combo.findText("both"))
        app.processEvents()
        assert w.doc.find(pu.id).params["flange"] == "ambas"
        assert 'flange = "both"' in w.code.text.toPlainText()
    finally:
        set_language("es")
        w.retranslate_ui()
    assert 'flange = "ambas"' in w.code.text.toPlainText()


def test_polea_trapecial_desde_la_cinta():
    """Botón v_pulley de la cinta; el panel calcula sus medidas (sección A por defecto)."""
    from PySide6.QtWidgets import QLabel
    from scadgui.model import Document
    w = window()
    w.set_document(Document())
    w.ribbon.buttons["v_pulley"].click()
    app.processEvents()
    pu = w.doc.children[0]
    assert pu.kind == "v_pulley" and w.selected_ids() == [pu.id]
    texts = [l.text() for l in w.props.findChildren(QLabel)]
    assert any(t.startswith("Ángulo de ranura 34° · boca 12.548 mm") for t in texts), texts
    assert any("Ancho de cara 19.05 mm" in t for t in texts), texts
    assert "module v_pulley(" in w.code.text.toPlainText()


def test_espina_de_pescado_desde_la_cinta():
    """Botón herringbone_gear de la cinta; el panel calcula sus datos y crea la pareja IGUAL
    (sin voltear la mano, a diferencia del helicoidal simple)."""
    from PySide6.QtWidgets import QLabel, QPushButton
    from scadgui.i18n import tr
    from scadgui.model import Document
    w = window()
    w.set_document(Document())
    w.ribbon.buttons["herringbone_gear"].click()
    app.processEvents()
    gear = w.doc.children[0]
    assert gear.kind == "herringbone_gear"
    texts = [l.text() for l in w.props.findChildren(QLabel)]
    assert any("Módulo aparente 1.103" in t for t in texts), texts     # m = 1, hélice 25°, grueso/2 = 8
    assert any(t.startswith("Ø primitivo 22.068 mm") for t in texts), texts
    add = next(b for b in w.props.findChildren(QPushButton) if b.text() == tr("Añadir engranaje que engrane"))
    add.click()
    app.processEvents()
    assert [n.kind for n in w.doc.children] == ["herringbone_gear", "translate"]
    pair = w.doc.find(w.selected_ids()[0])
    assert pair.kind == "herringbone_gear" and pair.params["left_hand"] is True  # mano contraria
    assert "module herringbone_gear(" in w.code.text.toPlainText()


def test_helicoidal_y_cremallera_desde_la_cinta():
    """Botones helical_gear y rack de la cinta; el panel calcula sus datos y crea la pareja."""
    from PySide6.QtWidgets import QLabel, QPushButton
    from scadgui.i18n import tr
    from scadgui.model import Document
    w = window()
    w.set_document(Document())
    w.ribbon.buttons["helical_gear"].click()
    app.processEvents()
    gear = w.doc.children[0]
    assert gear.kind == "helical_gear"
    texts = [l.text() for l in w.props.findChildren(QLabel)]
    assert any("Módulo aparente 1.064" in t for t in texts), texts      # m = 1, hélice 20°
    assert any(t.startswith("Ø primitivo 21.284 mm") for t in texts), texts
    add = next(b for b in w.props.findChildren(QPushButton) if b.text() == tr("Añadir engranaje que engrane"))
    add.click()
    app.processEvents()
    assert [n.kind for n in w.doc.children] == ["helical_gear", "translate"]
    assert w.doc.find(w.selected_ids()[0]).params["left_hand"] is True
    assert "module helical_gear(" in w.code.text.toPlainText()

    w.set_document(Document())
    w.ribbon.buttons["rack"].click()
    app.processEvents()
    rack = w.doc.children[0]
    assert rack.kind == "rack"
    texts = [l.text() for l in w.props.findChildren(QLabel)]
    assert any(t.startswith("Paso 3.142 mm") for t in texts), texts
    add = next(b for b in w.props.findChildren(QPushButton)
               if b.text() == tr("Añadir engranaje sobre la cremallera"))
    add.click()
    app.processEvents()
    assert [n.kind for n in w.doc.children] == ["rack", "translate"]
    assert w.doc.find(w.selected_ids()[0]).kind == "spur_gear"
    assert "module rack(" in w.code.text.toPlainText()

    # Y con el dentado inclinado: la hélice es un parámetro opcional, se activa con su casilla.
    from PySide6.QtWidgets import QCheckBox
    w.select_ids([rack.id])                                          # el botón dejó elegido el engranaje
    app.processEvents()
    box = next(c for c in w.props.findChildren(QCheckBox) if c.text() == tr("Ángulo de hélice (°)"))
    box.setChecked(True)
    app.processEvents()
    assert rack.params["helix_angle"] == 20
    texts = [l.text() for l in w.props.findChildren(QLabel)]
    assert any("el dentado se corre 1.82 mm" in t for t in texts), texts
    add = next(b for b in w.props.findChildren(QPushButton)
               if b.text() == tr("Añadir engranaje sobre la cremallera"))
    add.click()
    app.processEvents()
    pair = w.doc.find(w.selected_ids()[0])                           # …la pareja es un helicoidal
    assert pair.kind == "helical_gear" and pair.params["helix_angle"] == 20

    w.set_document(Document())                                       # y el cónico, girado sin mover
    w.ribbon.buttons["bevel_gear"].click()
    app.processEvents()
    texts = [l.text() for l in w.props.findChildren(QLabel)]
    assert any(t.startswith("Ø primitivo 20 mm") and "cono primitivo 45.00°" in t for t in texts), texts
    add = next(b for b in w.props.findChildren(QPushButton) if b.text() == tr("Añadir engranaje que engrane"))
    add.click()
    app.processEvents()
    assert [n.kind for n in w.doc.children] == ["bevel_gear", "rotate"]
    assert w.doc.children[1].params["a"] == [0, 90, 0]
    assert "module bevel_gear(" in w.code.text.toPlainText()

def test_brida_desde_la_cinta_y_asistente():
    """El botón pipe_flange crea la brida de la tabla y el panel da su volumen; el asistente ofrece solo
    lo que la norma tiene y no deja insertar una brida de cuello sin agujero cuando la norma no lo da."""
    from PySide6.QtWidgets import QLabel
    from scadgui import flanges
    from scadgui.i18n import set_language
    from scadgui.model import Document
    from scadgui.ui.flange_dialog import FlangeDialog
    set_language("es")
    w = window()
    w.set_document(Document())
    w.ribbon.buttons["pipe_flange"].click()
    app.processEvents()
    node = w.doc.children[0]
    assert node.kind == "pipe_flange" and w.selected_ids() == [node.id]
    volume = flanges.flange_volume(node.params) / 1000
    texts = [l.text() for l in w.props.findChildren(QLabel)]
    assert f"Volumen {volume:.1f} cm³" in texts, texts
    assert "module pipe_flange(" in w.code.text.toPlainText()
    assert "flange_wizard" in w.ribbon.buttons

    dlg = FlangeDialog(w)
    dlg.combo_standard.setCurrentIndex(dlg.combo_standard.findData("en_1092_1"))
    dlg.combo_rating.setCurrentIndex(dlg.combo_rating.findData("16"))
    dlg.combo_type.setCurrentIndex(dlg.combo_type.findData("weld_neck"))
    dlg.combo_size.setCurrentIndex(dlg.combo_size.findData("100"))
    assert "DN 100" in dlg.lbl_info.text() and dlg.btn_insert.isEnabled()
    assert dlg.get_result()["bore"] == 107.1
    dlg.combo_standard.setCurrentIndex(dlg.combo_standard.findData("asme_b16_5"))
    dlg.combo_rating.setCurrentIndex(dlg.combo_rating.findData("2500"))
    dlg.combo_type.setCurrentIndex(dlg.combo_type.findData("slip_on"))
    assert dlg.combo_size.count() == 0 and not dlg.btn_insert.isEnabled()
    dlg.combo_rating.setCurrentIndex(dlg.combo_rating.findData("600"))
    dlg.combo_type.setCurrentIndex(dlg.combo_type.findData("weld_neck"))
    dlg.combo_size.setCurrentIndex(dlg.combo_size.findData("4"))
    assert not dlg.btn_insert.isEnabled()                    # B16.5 deja el agujero al comprador
    dlg.spin_bore.setValue(97.2)
    assert dlg.btn_insert.isEnabled()
    res = dlg.get_result()
    assert (res["standard"], res["rating"], res["type"], res["size"], res["bore"]) == (
        "asme_b16_5", "600", "weld_neck", "4", 97.2)
    dlg.deleteLater()


def test_arbol_de_levas_desde_la_cinta():
    """Botones del grupo Árbol de levas: eje y lóbulo; el panel da las medidas del lóbulo y dónde está."""
    from PySide6.QtWidgets import QLabel
    from scadgui.i18n import set_language
    from scadgui.model import Document
    set_language("es")
    w = window()
    w.set_document(Document())
    w.ribbon.buttons["camshaft_main_shaft"].click()
    w.ribbon.buttons["cam_lobe"].click()
    app.processEvents()
    assert [n.kind for n in w.doc.children] == ["camshaft_main_shaft", "cam_lobe"]
    lobe = w.doc.children[1]
    assert w.selected_ids() == [lobe.id]
    texts = [l.text() for l in w.props.findChildren(QLabel)]
    assert "Ø base 30.00 mm · Ø en la punta 46.00 mm · abre 214.0° de la vuelta" in texts, texts
    assert "Ocupa de z = 14 a z = 26 mm" in texts, texts
    code = w.code.text.toPlainText()
    assert "module cam_lobe(" in code and "module camshaft_main_shaft(" in code


def test_asistente_de_arbol_de_levas():
    """El asistente propone 4 cilindros con admisión y escape, reparte el desfase al cambiar los
    cilindros, no deja insertar con un orden que no vale y avisa de solapes; el panel del lóbulo
    avisa si se solapa con otro."""
    from PySide6.QtWidgets import QLabel
    from scadgui import camshaft
    from scadgui.i18n import set_language
    from scadgui.model import Document
    from scadgui.ui.camshaft_dialog import CamshaftDialog
    set_language("es")
    w = window()
    assert "camshaft_wizard" in w.ribbon.buttons
    dlg = CamshaftDialog(w)
    assert len(dlg.items()) == 8 and dlg.btn_insert.isEnabled()
    dlg.spin_cyl.setValue(3)
    assert dlg.spin_offset.value() == 120 and len(dlg.items()) == 6
    dlg.edit_order.setText("1-1-2")
    assert not dlg.btn_insert.isEnabled() and "cilindro" in dlg.lbl_info.text()
    dlg.edit_order.setText("1-3-2")
    assert dlg.btn_insert.isEnabled()
    dlg.spin_gap.setValue(5)
    assert "solapan" in dlg.lbl_info.text()
    res = dlg.get_result()
    group = camshaft.create_camshaft(res["shaft"], res["lobe"], dlg.items(), w.doc.unique_name)
    dlg.deleteLater()
    w.set_document(Document())
    w.mutate(lambda: w.doc.children.append(group), select=[group.children[1].id])
    app.processEvents()
    texts = [l.text() for l in w.props.findChildren(QLabel)]
    assert any(t.startswith("Los lóbulos Admisión 1 y Escape 1 se solapan") for t in texts), texts


def test_pestana_mecanica():
    """Sólidos 3D solo tiene las primitivas; las piezas mecánicas y sus asistentes van en Mecánica."""
    w = window()
    tabs = [w.ribbon.widget(i) for i in range(w.ribbon.count())]

    def tab_of(cmd):
        return next(i for i, page in enumerate(tabs) if page.isAncestorOf(w.ribbon.buttons[cmd]))
    solid, mech = tab_of("cube"), tab_of("spur_gear")
    assert solid != mech and mech == solid + 1
    assert all(tab_of(c) == solid for c in ("cube", "sphere", "cylinder", "polyhedron"))
    assert all(tab_of(c) == mech for c in ("helical_gear", "herringbone_gear", "bevel_gear", "rack", "pulley",
                                           "v_pulley", "spline", "cam",
                                           "camshaft_main_shaft", "cam_lobe", "pipe_flange", "hardware",
                                           "flange_wizard", "camshaft_wizard"))


def test_barra_del_visor_cambia_de_idioma():
    """Al cambiar de idioma, la barra del visor (vistas, Medir, Regla…) se vuelve a escribir sin
    reiniciar, en el visor OpenGL y en el de imágenes."""
    from scadgui.i18n import set_language
    from scadgui.ui.viewer import Viewport
    w = window()
    set_language("es")
    w.retranslate_ui()
    assert w.viewer.measure_btn.text() == "Medir" and w.viewer.view_buttons["iso"].text() == "Isométrica"
    set_language("en")
    try:
        w.retranslate_ui()
        assert w.viewer.measure_btn.text() == "Measure", w.viewer.measure_btn.text()
        assert w.viewer.view_buttons["iso"].text() == "Isometric"
        assert w.viewer.ruler_btn.text() == "Ruler" and w.viewer.explosion_label.text() == "Explode:"
        assert w.viewer.title.text() == "3D View"
        fallback = Viewport()
        set_language("es")
        fallback.retranslate_ui()
        set_language("en")
        fallback.retranslate_ui()
        assert fallback.fit_btn.text() == "Fit" and fallback.view_buttons["Isométrica"].text() == "Isometric"
        fallback.deleteLater()
    finally:
        set_language("es")
        w.retranslate_ui()


def _wait_mesh(w, seconds=60):
    import time
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        if not w.runner.busy() and w.runner._pending is None:
            app.processEvents()
            return
        time.sleep(0.02)
    raise AssertionError("OpenSCAD no terminó")


def test_malla_ya_calculada_sale_de_la_cache():
    w = window()
    if not w.runner.exe:
        print("     (sin OpenSCAD: se omite)")
        return
    cube = w.doc.children[0].children[0]
    w.viewer._render_timer.stop()          # el cálculo del arranque se lanza aquí mismo
    w._render_mesh()
    _wait_mesh(w)
    w.mesh_cache.clear()
    w._render_mesh()                      # primera vez: lo calcula OpenSCAD
    assert w.runner.busy()
    _wait_mesh(w)
    first = w.viewer.real
    assert first is not None and len(w.mesh_cache) == 1
    assert "en caché" not in w.viewer.status.text()
    size = cube.params["size"]
    cube.params["size"] = [s + 2 for s in size]
    w._render_mesh()                       # modelo distinto: otra vez OpenSCAD
    assert w.runner.busy()
    _wait_mesh(w)
    assert len(w.mesh_cache) == 2 and w.viewer.real is not first
    cube.params["size"] = size
    w._render_mesh()                       # vuelve al estado de antes: sin llamar a OpenSCAD
    assert not w.runner.busy()
    assert w.viewer.real is first and "en caché" in w.viewer.status.text()


def test_modos_de_visualizacion_del_visor():
    w = window()
    v = w.viewer
    tris = np.array([[[0, 0, 0], [10, 0, 0], [0, 10, 0]], [[10, 0, 0], [10, 10, 0], [0, 10, 0]]], float)
    v.set_mesh(tris)
    saved = w.settings.value("display_mode", "shaded", str)
    try:
        v.set_display_mode("shaded")
        assert v.model.visible() and not v.wire.visible()
        v.set_display_mode("wireframe")
        assert not v.model.visible() and v.wire.visible()
        assert w.display_actions["wireframe"].isChecked()
        assert w.settings.value("display_mode", "", str) == "wireframe"
        assert v.mode_combo.currentData() == "wireframe"
        v.set_display_mode("shaded_wire")
        assert v.model.visible() and v.wire.visible()
        v.set_display_mode("xray")
        assert v.model.visible() and not v.wire.visible()
        assert np.allclose(v.model.opts["meshdata"].vertexColors(indexed="faces")[..., 3], 0.28)
        v.edges_check.setChecked(False)
        v.set_display_mode("hidden_line")
        assert v.edges.visible()                  # los contornos salen aunque la casilla esté apagada
        v.set_display_mode("shaded")
        assert not v.edges.visible()
        v.edges_check.setChecked(True)
        assert v.edges.visible()
        QTest.keyClick(v.view, Qt.Key.Key_Z)      # Z: el modo siguiente
        assert v.display_mode == "shaded_wire"
        w.display_actions["xray"].trigger()       # desde el menú Ver › Visualización
        assert v.display_mode == "xray" and v.mode_combo.currentData() == "xray"
        v.mode_combo.setCurrentIndex(0)           # y desde la barra del visor
        assert v.display_mode == "shaded" and w.display_actions["shaded"].isChecked()
    finally:
        w.settings.setValue("display_mode", saved)


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print("FALLA", name, "->", repr(exc)[:300])
    sys.exit(1 if failures else 0)
