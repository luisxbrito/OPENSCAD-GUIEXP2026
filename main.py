"""OpenSCAD GUI Mejorada — punto de entrada.

Uso:
    python main.py                 abre el ejemplo
    python main.py pieza.scad      abre un archivo
"""

import os
import sys

# Silenciar avisos no críticos del parser de perfiles ICC de monitores en Qt
rules = os.environ.get("QT_LOGGING_RULES", "")
if "qt.gui.icc" not in rules:
    os.environ["QT_LOGGING_RULES"] = (rules + ";qt.gui.icc=false").strip(";")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    try:
        from PySide6.QtCore import QLoggingCategory
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("Falta PySide6. Instálalo con:  python -m pip install PySide6")
        return 1

    QLoggingCategory.setFilterRules("qt.gui.icc=false")
    from scadgui.ui.mainwindow import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("OpenSCAD GUI Mejorada")
    app.setOrganizationName("OpenSCAD-GUI-Mejorada")
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    win = MainWindow(path)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
