import numpy as np
from PySide6.QtWidgets import QWidget
from pyqtgraph import Vector

class GLViewWidget(QWidget):
    def __init__(self, parent=None):
        self.opts = {"center": Vector(0, 0, 0), "distance": 10.0, "elevation": 30.0, "azimuth": 45.0, "fov": 60}
        self.items = []
    def setCameraPosition(self, pos=None, distance=None, elevation=None, azimuth=None):
        if pos is not None: self.opts["center"] = pos
        if distance is not None: self.opts["distance"] = distance
        if elevation is not None: self.opts["elevation"] = elevation
        if azimuth is not None: self.opts["azimuth"] = azimuth
    def addItem(self, i): self.items.append(i)
    def width(self): return 800
    def height(self): return 600
    def mousePressEvent(self, ev): pass
    def mouseReleaseEvent(self, ev): pass

class _Item:
    def __init__(self, *a, **k): self._vis = True; self.kw = k; self.data = None
    def setVisible(self, v): self._vis = bool(v)
    def visible(self): return self._vis
    def setDepthValue(self, d): pass
    def setData(self, **k): self.data = k
    def setMeshData(self, meshdata=None): self.data = meshdata
    def resetTransform(self): pass
    def translate(self, *a): pass
    def setSize(self, *a): pass
    def setSpacing(self, *a): pass
    def setColor(self, *a): pass

class MeshData:
    def __init__(self, vertexes=None, faces=None, vertexColors=None, faceColors=None):
        self.vertexes = vertexes
        self.vertexColors = vertexColors
        if vertexes is not None:
            assert vertexes.ndim == 3 and vertexes.shape[1:] == (3, 3) and vertexes.dtype == np.float32
        if vertexColors is not None:
            assert vertexColors.shape == (len(vertexes), 3, 4) and vertexColors.dtype == np.float32
            assert np.isfinite(vertexColors).all() and vertexColors.min() >= 0 and vertexColors.max() <= 1

class GLMeshItem(_Item): pass
class GLLinePlotItem(_Item):
    def setData(self, **k):
        assert k["pos"].ndim == 2 and k["pos"].shape[1] == 3
        self.data = k
class GLScatterPlotItem(_Item): pass
class GLGridItem(_Item): pass
