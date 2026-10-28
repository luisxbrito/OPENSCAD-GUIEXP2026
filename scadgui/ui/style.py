"""Hoja de estilos (mismos colores que el mockup)."""

STYLESHEET = """
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
QToolButton#ribbonButton { background: #FAFBFC; border: 1px solid #E4E7EC; border-radius: 8px; padding: 4px 8px; font-size: 9pt; }
QToolButton#ribbonButton:hover { background: #EEF3FB; border-color: #9FB9E6; }
QToolButton#ribbonButton:pressed { background: #E3ECFA; }
QToolButton#ribbonButton[experimental="true"] { color: #6B4600; background: #FFF8E6; }
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

QWidget#viewport { background: #262B33; }
QWidget#viewBar { background: #262B33; }
QWidget#viewBar QLabel, QCheckBox#viewCheck { color: #FFFFFF; font-size: 9pt; }
QLabel#viewTitle { color: #FFFFFF; font-weight: 600; margin-right: 6px; }
QPushButton#viewButton { background: transparent; border: 1px solid #5A6372; color: #FFFFFF; padding: 3px 10px; font-size: 9pt; }
QPushButton#viewButton:hover { background: #343A44; color: #FFFFFF; }
QLabel#viewStatus { color: #FFFFFF; margin-left: 8px; }
QLabel#viewMessage { color: #C9D1DC; font-size: 10pt; background: transparent; }
QLabel#viewHint { color: #8C97A8; font-size: 8pt; background: transparent; }
QLabel#measureBadge { background: #12384A; color: #BFEFFF; border-radius: 6px; padding: 5px 10px; font-family: "IBM Plex Mono", Consolas, monospace; font-size: 9pt; }
QPushButton#viewButton:checked { background: #12384A; border-color: #5BD3FF; color: #FFFFFF; }
QLabel#selectionBadge { background: #343A44; color: #E8ECF1; border-radius: 6px; padding: 5px 10px; font-size: 9pt; }

QStatusBar { background: #FFFFFF; border-top: 1px solid #D5D9E0; color: #5A6474; }
QSplitter::handle { background: #E4E7EC; }
QSplitter::handle:vertical { height: 1px; }
"""
