import inspect, re, glob, os

SRC = os.environ.get("SCADGUI_SRC", "")
OWN = set()
for f in glob.glob(os.path.join(SRC, "scadgui", "**", "*.py"), recursive=True):
    t = open(f, encoding="utf-8").read()
    OWN |= set(re.findall(r"self\.(\w+)\s*=", t)) | {d for d in re.findall(r"def (\w+)", t) if "_" in d}

class _Meta(type):
    _cache = {}
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        key = (cls, name)
        if key not in _Meta._cache:
            _Meta._cache[key] = _Meta(name, (Dummy,), {})
        return _Meta._cache[key]
    def __or__(cls, o): return cls
    __ror__ = __and__ = __or__
    def __invert__(cls): return cls
    def __int__(cls): return 0
    def __index__(cls): return 0

def _qtish(name):
    return name[:1].islower() and "_" not in name.rstrip("_") and name not in OWN

class BoundSignal:
    def __init__(self): self.slots = []
    def connect(self, fn): self.slots.append(fn)
    def disconnect(self, *a): self.slots.clear()
    def emit(self, *args):
        for fn in list(self.slots):
            try:
                n = len(inspect.signature(fn).parameters)
            except (TypeError, ValueError):
                n = len(args)
            fn(*args[:n])

class Signal:
    def __init__(self, *types): self.name = None
    def __set_name__(self, owner, name): self.name = name
    def __get__(self, obj, owner):
        if obj is None: return self
        return obj.__dict__.setdefault("_sig_" + self.name, BoundSignal())

class Dummy(metaclass=_Meta):
    def __init__(self, *a, **k): pass
    def __getattr__(self, name):
        if name.startswith("_") or not _qtish(name):
            raise AttributeError(f"{type(self).__name__}.{name}")
        sig_like = name in ("clicked", "toggled", "triggered", "valueChanged", "editingFinished",
                            "currentTextChanged", "currentIndexChanged", "timeout", "activated",
                            "cursorPositionChanged", "itemSelectionChanged", "accepted", "rejected",
                            "customContextMenuRequested", "itemDoubleClicked", "finished",
                            "readyReadStandardOutput", "errorOccurred")
        if sig_like:
            return self.__dict__.setdefault("_sig_" + name, BoundSignal())
        return Dummy()
    def __call__(self, *a, **k): return Dummy()
    def __iter__(self): return iter(())
    def __bool__(self): return True
    def __int__(self): return 0
    def __float__(self): return 0.0
    def __index__(self): return 0
    def __len__(self): return 0
    def __str__(self): return ""
    def __format__(self, spec): return ""
    def __add__(self, o): return Dummy()
    __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = __rtruediv__ = __iadd__ = __floordiv__ = __rfloordiv__ = __mod__ = __neg__ = __add__
    def __lt__(self, o): return False
    __gt__ = __le__ = __ge__ = __lt__
    __hash__ = object.__hash__
