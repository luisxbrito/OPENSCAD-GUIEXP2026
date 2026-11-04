"""Caché de las mallas finales que calcula OpenSCAD para el visor.

Cada malla se guarda bajo una huella (SHA-256) de todo lo que decide su forma: el código
generado, las opciones de la línea de comandos, el motor (CGAL/Manifold), el ejecutable y la
carpeta del documento. Si el modelo vuelve a un estado ya calculado (deshacer, rehacer, ocultar
y volver a mostrar una pieza…), la malla sale de aquí sin volver a llamar a OpenSCAD.

El código que lee archivos externos (``include``, ``use``, ``import()``, ``surface()``) no se
guarda: esos archivos pueden cambiar en disco sin que cambie el código, y la malla quedaría vieja.

Sin Qt: se prueba en tests/test_core.py.
"""

from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from typing import Optional

EMPTY = "empty"   # el modelo no tiene geometría (también se recuerda)

# Lecturas de archivos externos. Los comentarios y cadenas no se quitan antes de buscar: en el peor
# caso una palabra suelta en un comentario hace que ese modelo no se guarde, que no es un error.
_EXTERNAL = re.compile(r"\b(include|use)\s*<|\b(import|surface)\s*\(")

MAX_BYTES = 256 * 1024 * 1024     # memoria total de las mallas guardadas
MAX_ENTRIES = 24


def cacheable(code: str) -> bool:
    return not _EXTERNAL.search(code)


def mesh_key(code: str, args: list, backend: str = "", exe: str = "", base_dir: str = "") -> str:
    h = hashlib.sha256()
    for part in (code, "\0".join(args), backend, exe, base_dir):
        h.update(part.encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()


def _size(value) -> int:
    if value == EMPTY:
        return 0
    tris, colors = value
    return int(getattr(tris, "nbytes", 0)) + int(getattr(colors, "nbytes", 0) if colors is not None else 0)


class MeshCache:
    """LRU por memoria: se descartan primero las mallas usadas hace más tiempo."""

    def __init__(self, max_bytes: int = MAX_BYTES, max_entries: int = MAX_ENTRIES):
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self._items: OrderedDict[str, object] = OrderedDict()
        self._bytes = 0

    def __len__(self) -> int:
        return len(self._items)

    @property
    def bytes(self) -> int:
        return self._bytes

    def get(self, key: str) -> Optional[object]:
        """(triángulos, colores por cara o None), EMPTY, o None si no está."""
        value = self._items.get(key)
        if value is not None:
            self._items.move_to_end(key)
        return value

    def put(self, key: str, value) -> None:
        size = _size(value)
        if size > self.max_bytes:
            return                       # una sola malla más grande que toda la caché: no se guarda
        if key in self._items:
            self._bytes -= _size(self._items.pop(key))
        self._items[key] = value
        self._bytes += size
        while self._items and (self._bytes > self.max_bytes or len(self._items) > self.max_entries):
            _, old = self._items.popitem(last=False)
            self._bytes -= _size(old)

    def clear(self) -> None:
        self._items.clear()
        self._bytes = 0
