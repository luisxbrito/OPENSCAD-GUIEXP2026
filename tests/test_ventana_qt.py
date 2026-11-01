"""Pruebas con el Qt real (PySide6 y pyqtgraph instalados), sin mostrar la ventana.

Mandan eventos de ratón de verdad a la vista 3D, que es lo que las simulaciones de
tests/simulacion no pueden comprobar. Si falta PySide6 o pyqtgraph, se omiten.

Usa la configuración guardada del programa (solo la lee): si el visor está puesto en
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
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
except ImportError as exc:
    print(f"Falta {exc.name}: se omiten estas pruebas")
    sys.exit(0)

app = QApplication.instance() or QApplication(sys.argv)
import scadgui.ui.mainwindow as mw  # noqa: E402

LEFT, NONE = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier


def window():
    w = mw.MainWindow("")
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
