from ._base import Dummy, BoundSignal
class _W(Dummy): pass
class QWidget(_W): pass
class QMainWindow(_W):
    messages = []
    def statusBar(self):
        sb = self.__dict__.setdefault("_sb", _StatusBar())
        return sb
class _StatusBar(Dummy):
    def showMessage(self, m, t=0): QMainWindow.messages.append(m)
class QScrollArea(_W):
    def setWidget(self, w): self.__dict__["_w"] = w
    def takeWidget(self): return self.__dict__.pop("_w", None)
    def widget(self): return self.__dict__.get("_w")
class QLineEdit(_W):
    def __init__(self, text="", *a): self._t = text
    def text(self): return self._t
    def setText(self, t): self._t = t
class QCheckBox(_W):
    def __init__(self, *a): self._c = False
    def isChecked(self): return self._c
    def setChecked(self, c): self._c = c
class QRadioButton(_W):
    def __init__(self, *a): self._c = False
    def isChecked(self): return self._c
    def setChecked(self, c): self._c = c
class QSpinBox(_W):
    def __init__(self, *a): self._v = 0
    def value(self): return self._v
    def setValue(self, v): self._v = int(v)
class QDoubleSpinBox(_W):
    def __init__(self, *a): self._v = 0.0
    def value(self): return self._v
    def setValue(self, v): self._v = float(v)
class QSlider(_W):
    def __init__(self, *a): self._v = 0
    def value(self): return self._v
    def setValue(self, v): self._v = int(v)
class QComboBox(_W):
    def __init__(self, *a): self._items = []; self._i = 0
    def addItem(self, text, data=None): self._items.append((text, data))
    def addItems(self, items): [self.addItem(t) for t in items]
    def clear(self): self._items = []; self._i = 0
    def findData(self, d): return next((i for i, x in enumerate(self._items) if x[1] == d), -1)
    def setCurrentIndex(self, i): self._i = i
    def currentData(self): return self._items[self._i][1] if self._items else None
    def currentText(self): return self._items[self._i][0] if self._items else ""
    def setCurrentText(self, t): pass
class QPlainTextEdit(_W):
    def __init__(self, text="", *a): self._t = text; self._line = 0
    def setPlainText(self, t): self._t = t
    def toPlainText(self): return self._t
    def appendHtml(self, h): self._t += h + "\n"
    def textCursor(self):
        c = Dummy(); line = self._line
        c.__dict__["blockNumber"] = lambda: line
        return c
class QTreeWidgetItem:
    def __init__(self, parent=None):
        self._data = {}; self._text = {}; self._kids = []; self._sel = False
        if parent is not None: parent._kids.append(self)
    def setData(self, c, r, v): self._data[c] = v
    def data(self, c, r): return self._data.get(c)
    def setText(self, c, t): self._text[c] = t
    def text(self, c): return self._text.get(c, "")
    def setSelected(self, s): self._sel = s
    def isSelected(self): return self._sel
    def childCount(self): return len(self._kids)
    def child(self, i): return self._kids[i]
    def font(self, c): return Dummy()
    def __getattr__(self, n):
        if n[:3] in ("set",): return lambda *a: None
        raise AttributeError(n)
class QTreeWidget(_W):
    def __init__(self, *a): self._root = QTreeWidgetItem()
    def invisibleRootItem(self): return self._root
    def clear(self): self._root = QTreeWidgetItem()
    def _all(self, item=None):
        item = item or self._root
        for k in item._kids:
            yield k
            yield from self._all(k)
    def selectedItems(self): return [i for i in self._all() if i._sel]
    def clearSelection(self):
        for i in self._all(): i._sel = False
class QMessageBox(_W):
    @staticmethod
    def question(*a): return QMessageBox.StandardButton.Discard
class QFileDialog(_W):
    next_open = ""; next_save = ""
    @staticmethod
    def getOpenFileName(*a): return (QFileDialog.next_open, "")
    @staticmethod
    def getSaveFileName(*a): return (QFileDialog.next_save, "STL (*.stl)")
class QDialog(_W): pass
class QApplication(_W): pass
class QTextEdit(_W): pass
def __getattr__(name):
    return type(name, (_W,), {})
