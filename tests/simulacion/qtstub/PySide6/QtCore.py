from ._base import Dummy, Signal, BoundSignal, _Meta
class QObject(Dummy): pass
class Qt(Dummy): pass
class QSize(Dummy): pass
class QRectF(Dummy): pass
class QPointF:
    def __init__(self, x=0, y=0): self.x_, self.y_ = x, y
    def __add__(self, o): return QPointF(self.x_ + o.x_, self.y_ + o.y_)
    def __sub__(self, o): return QPointF(self.x_ - o.x_, self.y_ - o.y_)
    def x(self): return self.x_
    def y(self): return self.y_
class QByteArray:
    def __init__(self, data=b""): self._data = data
    def data(self): return self._data
class QEvent(Dummy): pass
class QItemSelectionModel(Dummy): pass
class QSettings:
    store = {}
    def __init__(self, *a): pass
    def value(self, key, default=None, type=None): return QSettings.store.get(key, default)
    def setValue(self, key, v): QSettings.store[key] = v
class QTimer(Dummy):
    @staticmethod
    def singleShot(ms, fn): fn()
class QProcess(Dummy):
    started_args = []
    def start(self, exe, args): QProcess.started_args.append((exe, list(args)))
    def state(self): return QProcess.ProcessState.NotRunning
    def waitForFinished(self, ms=0): return True
    def readAllStandardOutput(self): return QByteArray(b"")
def __getattr__(name): return getattr(Dummy, name)
