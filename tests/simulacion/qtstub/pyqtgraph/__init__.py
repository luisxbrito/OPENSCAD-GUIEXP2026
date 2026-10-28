class Vector:
    def __init__(self, x=0, y=0, z=0): self._v = (float(x), float(y), float(z))
    def x(self): return self._v[0]
    def y(self): return self._v[1]
    def z(self): return self._v[2]
def mkColor(*a): return a
