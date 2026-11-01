"""Hoja de estilos y temas (claro y oscuro).

Los colores se escriben una sola vez, los del tema claro. Con el tema oscuro, ``c()`` y
``themed()`` los traducen: primero la tabla ``DARK`` (la paleta base, ajustada a mano) y, para
el resto, una inversión del brillo que conserva el tono. Así los diálogos y el editor, que
tienen colores propios, también se ven bien en oscuro sin duplicar cada estilo.
El visor 3D es oscuro siempre y no pasa por aquí (``VIEWER_STYLES``, ``icon(..., fixed=True)``).
"""

import colorsys
import re
from functools import lru_cache

THEMES = ("light", "dark")
THEME = "light"
# Acento de los asistentes de la cinta (en oscuro se aclara: ver DARK).
ACCENT = "#D9822B"

# Tema claro -> oscuro. Fondos, bordes y textos de la paleta base.
DARK = {
    "#FFFFFF": "#20252D", "#F7F8FA": "#1B1F26", "#FAFBFC": "#232831", "#FBFBFC": "#1E232A",
    "#F8F9FA": "#232831", "#F3F4F6": "#22272F", "#F3F5F8": "#272D36", "#F5F8FD": "#2A313C",
    "#EEF0F3": "#2A3039", "#EEF3FB": "#2A3443", "#E4E7EC": "#2E3540", "#D5D9E0": "#343B47",
    "#CBD1DA": "#3A4250", "#E3ECFA": "#2B3F5E", "#B9D0F5": "#33507A", "#174A96": "#BCD3F5",
    "#1F5FBF": "#2F6FCC", "#1B2230": "#E6EAF0", "#5A6474": "#9AA4B2", "#3D4756": "#C9D1DB",
    "#9AA3AF": "#6E7884", "#FFF8E6": "#3A3222", "#E6C77A": "#8A6F2E", "#FFFDF6": "#232520",
    "#262B33": "#15181D", "#343A44": "#20252D", "#2F3540": "#1B1F26", "#3A414C": "#2E3540",
    "#5B9BFF": "#F2A65A", "#D9822B": "#F2A65A", "#F8FAFC": "#1E232A", "#F1F5F9": "#232831",
    "#E2E8F0": "#2E3540", "#CBD5E1": "#3A4250",
    "#FEF08A": "#4A4520", "#FDE047": "#7A5F10",  # resaltados de búsqueda
}


def set_theme(name: str) -> None:
    """Fija el tema; hay que llamarla antes de crear la ventana (no cambia los widgets ya hechos)."""
    global THEME
    THEME = name if name in THEMES else "light"


def _hls(color: str):
    h = color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def _hex(h, l, s) -> str:
    return "#" + "".join(f"{round(v * 255):02X}" for v in colorsys.hls_to_rgb(h, l, s))


@lru_cache(maxsize=1024)
def _dark(color: str, text: bool = False) -> str:
    """``text``: es un color de letra (no se deja por debajo de un brillo mínimo)."""
    key = color.upper()
    if len(key) == 4:
        key = "#" + "".join(ch * 2 for ch in key[1:])
    h, l, s = _hls(key)
    if text and l > 0.8:          # letra clara: ya iba sobre un fondo oscuro o de color
        return color
    if key in DARK:
        return DARK[key]
    if s > 0.45 and 0.3 < l < 0.7:  # colores de acento: se quedan (las letras, más claras)
        return _hex(h, max(l, 0.66), s) if text else color
    new_l = 0.12 + (1 - l) ** 0.8 * 0.8
    if text:
        new_l = max(new_l, 0.62)
    elif l > 0.7:                   # fondos claros de color: en oscuro, apagados
        s *= 0.5
    return _hex(h, new_l, s)


def c(color: str, text: bool = False) -> str:
    """El color en el tema actual (en claro, el mismo). ``text``: es un color de letra."""
    if THEME != "dark" or not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?", color):
        return color
    return _dark(color, text)


_DECL = re.compile(r"([\w-]+)(\s*:\s*)([^;{}]*)")
_HEX = re.compile(r"#[0-9A-Fa-f]{6}(?![0-9A-Za-z_-])|#[0-9A-Fa-f]{3}(?![0-9A-Za-z_-])")


def themed(css: str) -> str:
    """Hoja de estilos (o estilo de un widget) con los colores del tema actual."""
    if THEME != "dark" or not isinstance(css, str):
        return css

    def decl(m):
        text = m.group(1) == "color"
        value = _HEX.sub(lambda h: _dark(h.group(), text), m.group(3))
        return m.group(1) + m.group(2) + value
    return _DECL.sub(decl, css)


def stylesheet() -> str:
    """Hoja de estilos de la ventana para el tema actual."""
    return themed(THEMED_STYLES) + VIEWER_STYLES


def dark_palette():
    """Paleta de Qt para los controles que no cubre la hoja de estilos (diálogos del sistema...)."""
    from PySide6.QtGui import QColor, QPalette
    p = QPalette()
    R = QPalette.ColorRole
    for role, col in ((R.Window, "#20252D"), (R.WindowText, "#E6EAF0"), (R.Base, "#1B1F26"),
                      (R.AlternateBase, "#232831"), (R.Text, "#E6EAF0"), (R.Button, "#2A3039"),
                      (R.ButtonText, "#E6EAF0"), (R.Highlight, "#2F6FCC"), (R.HighlightedText, "#FFFFFF"),
                      (R.ToolTipBase, "#2A3039"), (R.ToolTipText, "#E6EAF0"), (R.PlaceholderText, "#8F99A7"),
                      (R.Link, "#7FB0F0"), (R.BrightText, "#FFFFFF")):
        p.setColor(role, QColor(col))
    for role in (R.WindowText, R.Text, R.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor("#6E7884"))
    return p

THEMED_STYLES = """
* { font-family: "IBM Plex Sans", "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size: 10pt; color: #1B2230; }
QMainWindow, QDockWidget > QWidget { background: #FFFFFF; }
QMainWindow::separator { background: #D5D9E0; width: 1px; height: 1px; }
QMenuBar { background: #FFFFFF; border-bottom: 1px solid #D5D9E0; padding: 2px 6px; }
QMenuBar::item { padding: 5px 10px; border-radius: 6px; }
QMenuBar::item:selected { background: #EEF0F3; }
QMenu { background: #FFFFFF; border: 1px solid #D5D9E0; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 26px; border-radius: 4px; }
QMenu::item:selected { background: #E3ECFA; color: #174A96; }
QMenu::separator { height: 1px; background: #E4E7EC; margin: 4px 6px; }

QToolBar#mainToolbar { background: #F7F8FA; border: 0; border-bottom: 1px solid #D5D9E0; padding: 4px 8px; spacing: 2px; }
QToolBar#mainToolbar QToolButton { padding: 5px 9px; border-radius: 6px; border: 1px solid transparent; }
QToolBar#mainToolbar QToolButton:hover { background: #FFFFFF; border-color: #D5D9E0; }
QToolBar#ribbonToolbar { background: #FFFFFF; border: 0; border-bottom: 1px solid #D5D9E0; padding: 0; }

QTabWidget#ribbon { background: #262B33; }
QTabWidget#ribbon::pane { border: 0; border-top: 1px solid #3A414C; }
QTabWidget#ribbon QTabBar { background: #262B33; qproperty-drawBase: 0; }
QTabWidget#ribbon QTabBar::tab { padding: 8px 16px; border: 0; border-bottom: 2px solid transparent; color: #FFFFFF; background: #262B33; }
QTabWidget#ribbon QTabBar::tab:selected { color: #FFFFFF; border-bottom: 2px solid #5B9BFF; background: #343A44; font-weight: 600; }
QTabWidget#ribbon QTabBar::tab:hover:!selected { background: #2F3540; }
QWidget#ribbonPage { background: #FFFFFF; }
QToolButton#ribbonButton { background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 4px 6px; font-size: 9pt; }
QToolButton#ribbonButton[command="true"] { font-family: "IBM Plex Mono", Consolas, "Courier New", monospace; }
QToolButton#ribbonButton:hover { background: #EEF3FB; border-color: #CBD1DA; }
QToolButton#ribbonButton:pressed { background: #E3ECFA; }
QToolButton#ribbonButton[experimental="true"] { color: #6B4600; }
QLabel#ribbonGroupTitle { color: #5A6474; font-size: 8pt; letter-spacing: 1px; }
QFrame#ribbonSep { background: #E4E7EC; border: 0; }
QLabel#ribbonHint { color: #5A6474; font-size: 9pt; }

QDockWidget::title { background: #F7F8FA; padding: 6px 10px; border-bottom: 1px solid #E4E7EC; font-weight: 600; color: #5A6474; }
QWidget#panelHead { background: #FFFFFF; }
QLabel#sectionTitle { font-size: 9pt; font-weight: 600; color: #5A6474; letter-spacing: 1px; }
QLabel#accentMono { font-family: "IBM Plex Mono", Consolas, monospace; color: #1F5FBF; }
QLabel#caption, QCheckBox#captionCheck { color: #5A6474; font-size: 9pt; }
QLabel#hint { color: #5A6474; font-size: 9pt; }
QLabel#warnText { color: #8A5A00; font-size: 9pt; }
QLabel#warnBox { background: #FFF3D6; color: #6B4600; border-radius: 8px; padding: 10px 12px; font-size: 9pt; }
QLabel#panelFoot { color: #5A6474; font-size: 9pt; padding: 8px 12px; border-top: 1px solid #E4E7EC; }
QLabel#okBadge { background: #E6F4EA; color: #1E6B34; border-radius: 9px; padding: 2px 9px; font-size: 8pt; font-weight: 600; }
QLabel#warnBadge { background: #FFF3D6; color: #6B4600; border-radius: 9px; padding: 2px 9px; font-size: 8pt; font-weight: 600; }
QLabel#axisX { color: #C0392B; font-weight: 600; }
QLabel#axisY { color: #1E7B3C; font-weight: 600; }
QLabel#axisZ { color: #1F5FBF; font-weight: 600; }

QToolButton#modButton { font-family: "IBM Plex Mono", Consolas, monospace; font-weight: 600; min-width: 24px; min-height: 24px; border: 1px solid #E4E7EC; border-radius: 6px; background: #FFFFFF; }
QToolButton#modButton:checked { background: #FDE7D5; border-color: #F08A24; color: #9A4A00; }
QToolButton#modButton:disabled { color: #B8BEC8; }
QToolButton#treeTool { border: 1px solid transparent; border-radius: 6px; padding: 3px; }
QToolButton#treeTool:hover { background: #EEF0F3; border-color: #E4E7EC; }

QTreeWidget#modelTree { border: 0; border-top: 1px solid #E4E7EC; background: #FFFFFF; outline: 0; }
QTreeWidget#modelTree::item { height: 28px; border-radius: 6px; }
QTreeWidget#modelTree::item:selected { background: #E3ECFA; color: #174A96; }
QTreeWidget#modelTree::item:hover:!selected { background: #F3F5F8; }
QHeaderView::section { background: #FFFFFF; border: 0; border-bottom: 1px solid #E4E7EC; padding: 4px 8px; color: #5A6474; font-size: 9pt; }

QScrollArea#propsPanel, QWidget#propsBody { background: #FBFBFC; border: 0; border-top: 1px solid #D5D9E0; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #FFFFFF; border: 1px solid #CBD1DA; border-radius: 6px; padding: 4px 6px; min-height: 20px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #1F5FBF; }
QLineEdit#exprEdit { font-family: "IBM Plex Mono", Consolas, monospace; background: #FFF8E6; border-color: #E6C77A; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: #9AA3AF; background: #F3F4F6; }
QPushButton { background: #FFFFFF; border: 1px solid #CBD1DA; border-radius: 6px; padding: 5px 12px; }
QPushButton:hover { border-color: #9FB9E6; background: #F5F8FD; }
QPushButton#primary { background: #1F5FBF; border-color: #1F5FBF; color: #FFFFFF; font-weight: 600; }
QPushButton#primary:hover { background: #174A96; }
QPushButton#fxButton { border: 1px solid #CBD1DA; border-radius: 4px; background: #F8F9FA; color: #174A96; font-weight: bold; font-size: 10pt; padding: 1px; min-width: 24px; }
QPushButton#fxButton:hover { background: #E3ECFA; border-color: #174A96; }
QWidget#variablesPanel { background: #FFFFFF; }
QTableWidget { gridline-color: #E4E7EC; background: #FFFFFF; color: #1B2230; font-size: 9pt; }
QTableWidget::item:selected { background: #E3ECFA; color: #174A96; }
QPlainTextEdit#rawView { font-family: "IBM Plex Mono", Consolas, monospace; background: #FFFFFF; border: 1px solid #E4E7EC; border-radius: 6px; }

QPlainTextEdit#codeText { border: 0; background: #FFFFFF; selection-background-color: #B9D0F5; padding: 6px; }
QPlainTextEdit#codeText[editing="true"] { background: #FFFDF6; border-left: 3px solid #E6C77A; }
QPlainTextEdit#console { border: 0; background: #FFFFFF; padding: 4px 8px; }


QStatusBar { background: #FFFFFF; border-top: 1px solid #D5D9E0; color: #5A6474; }
QSplitter::handle { background: #E4E7EC; }
QSplitter::handle:vertical { height: 1px; }
"""

# El visor 3D es oscuro en los dos temas: estos colores no se traducen.
VIEWER_STYLES = """
QWidget#viewport { background: #262B33; }
QWidget#viewBar { background: #262B33; }
QWidget#viewBar QLabel, QCheckBox#viewCheck { color: #FFFFFF; font-size: 9pt; }
QLabel#viewTitle { color: #FFFFFF; font-weight: 600; margin-right: 6px; }
QPushButton#viewButton { background: transparent; border: 1px solid #5A6372; color: #FFFFFF; padding: 3px 10px; font-size: 9pt; }
QPushButton#viewButton:hover { background: #343A44; color: #FFFFFF; }
QLabel#viewStatus { color: #FFFFFF; margin-left: 8px; }
QLabel#viewMessage { color: #C9D1DC; font-size: 10pt; background: transparent; }
QLabel#viewHint { color: #8C97A8; font-size: 8pt; background: transparent; }
QLabel#viewName { color: #C9D1DC; font-size: 9pt; font-weight: 600; background: transparent; }
QLabel#measureBadge { background: #12384A; color: #BFEFFF; border-radius: 6px; padding: 5px 10px; font-family: "IBM Plex Mono", Consolas, monospace; font-size: 9pt; }
QPushButton#viewButton:checked { background: #12384A; border-color: #5BD3FF; color: #FFFFFF; }
QLabel#selectionBadge { background: #343A44; color: #E8ECF1; border-radius: 6px; padding: 5px 10px; font-size: 9pt; }
QFrame#treeOverlay { background: transparent; border: 0; }
QFrame#treeOverlay QLabel#sectionTitle { background: transparent; color: #C9D1DB; }
QFrame#treeOverlay QWidget#treeTools { background: transparent; }
QFrame#treeOverlay QTreeWidget#modelTree { background: transparent; border: 0; color: #EEF2F6; }
QFrame#treeOverlay QTreeWidget#modelTree::item:selected { background: rgba(77, 140, 230, 110); color: #FFFFFF; }
QFrame#treeOverlay QTreeWidget#modelTree::item:hover:!selected { background: rgba(255, 255, 255, 28); }
QFrame#treeOverlay QHeaderView::section { background: transparent; color: #AEB7C3; border: 0; border-bottom: 1px solid rgba(255, 255, 255, 40); }
QFrame#treeOverlay QToolButton#treeTool:hover { background: rgba(255, 255, 255, 30); border-color: rgba(255, 255, 255, 50); }
QFrame#treeOverlay QScrollBar:vertical { background: transparent; width: 8px; margin: 0; border: 0; }
QFrame#treeOverlay QScrollBar::handle:vertical { background: rgba(255, 255, 255, 70); border-radius: 4px; min-height: 24px; margin: 1px; }
QFrame#treeOverlay QScrollBar::add-line:vertical, QFrame#treeOverlay QScrollBar::sub-line:vertical { height: 0; }
QFrame#treeOverlay QScrollBar::add-page:vertical, QFrame#treeOverlay QScrollBar::sub-page:vertical { background: transparent; }
QPushButton#overlayButton { background: transparent; border: 0; color: #DDE3EA; font-size: 11pt; padding: 0 6px; }
QPushButton#overlayButton:hover { background: rgba(255, 255, 255, 30); border-radius: 4px; }
QFrame#edgePanel { background: #1E232B; border: 1px solid #FF8A33; border-radius: 6px; }
QFrame#edgePanel QLabel { color: #E8ECF1; font-size: 9pt; background: transparent; }
QFrame#edgePanel QDoubleSpinBox { min-width: 70px; }
"""
