"""Pruebas unitarias para la posición configurable de la barra de herramientas 3D."""

import os
import pytest
from PySide6.QtWidgets import QApplication

# Asegurar QApplication para widgets Qt
app = QApplication.instance() or QApplication([])

from scadgui.ui.viewer3d import Viewer3D
from scadgui.ui.viewer import Viewport


def test_viewer3d_bar_position():
    v = Viewer3D()
    assert v._bar_position == "top"
    assert v.pos_btn.text() == "▼"

    events = []
    v.barPositionChanged.connect(lambda p: events.append(p))

    # Mover abajo
    v.set_bar_position("bottom")
    assert v._bar_position == "bottom"
    assert v.pos_btn.text() == "▲"
    assert events == ["bottom"]

    # Toggle vuelve arriba
    v.toggle_bar_position()
    assert v._bar_position == "top"
    assert v.pos_btn.text() == "▼"
    assert events == ["bottom", "top"]


def test_viewport_bar_position():
    vp = Viewport()
    assert vp._bar_position == "top"
    assert vp.pos_btn.text() == "▼"

    events = []
    vp.barPositionChanged.connect(lambda p: events.append(p))

    vp.set_bar_position("bottom")
    assert vp._bar_position == "bottom"
    assert vp.pos_btn.text() == "▲"
    assert events == ["bottom"]

    vp.toggle_bar_position()
    assert vp._bar_position == "top"
    assert vp.pos_btn.text() == "▼"
    assert events == ["bottom", "top"]
