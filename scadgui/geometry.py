"""Geometría para el visor 3D (solo numpy, sin Qt).

* ``load_stl``: lee la malla final que exporta OpenSCAD.
* ``build_ghosts``: calcula en Python una malla aproximada de cada pieza del árbol
  (cubo, cilindro, extrusiones…) con sus transformaciones. Sirve para resaltar la
  selección al instante y para saber qué pieza hay bajo el ratón, sin volver a
  ejecutar OpenSCAD.
* ``feature_edges``: aristas vivas para dibujar el contorno como en FreeCAD.
* ``ray_hits`` / ``pick``: intersección rayo-triángulo (Möller–Trumbore).
"""

from __future__ import annotations

import math
import re
import struct
from typing import Optional

import numpy as np

from .model import Document, Expr, Node

Tris = np.ndarray  # (M, 3, 3)
EMPTY = np.zeros((0, 3, 3))

EXTRUDES = {"linear_extrude", "rotate_extrude"}


# --------------------------------------------------------------------------- STL

def load_stl(path: str) -> Tris:
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) >= 84:
        n = struct.unpack_from("<I", data, 80)[0]
        if len(data) == 84 + 50 * n:
            rec = np.dtype([("normal", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")])
            arr = np.frombuffer(data, dtype=rec, count=n, offset=84)
            return arr["v"].astype(np.float64)
    text = data.decode("ascii", errors="replace")
    nums = re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", text)
    if not nums:
        return EMPTY.copy()
    v = np.array(nums, dtype=np.float64)
    return v[: len(v) // 3 * 3].reshape(-1, 3, 3)


def bbox(tris: Tris):
    if tris is None or len(tris) == 0:
        return None
    pts = tris.reshape(-1, 3)
    return pts.min(axis=0), pts.max(axis=0)


def face_normals(tris: Tris) -> np.ndarray:
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    length = np.linalg.norm(n, axis=1, keepdims=True)
    length[length == 0] = 1
    return n / length


def feature_edges(tris: Tris, angle_deg: float = 25.0) -> np.ndarray:
    """Segmentos (K, 2, 3) donde las caras forman un ángulo mayor que ``angle_deg`` o hay borde."""
    if len(tris) == 0:
        return np.zeros((0, 2, 3))
    pts = tris.reshape(-1, 3)
    scale = max(float(np.abs(pts).max()), 1.0)
    keys = np.round(pts / (scale * 1e-7)).astype(np.int64)
    _, index, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    inverse = inverse.reshape(-1)
    verts = pts[index]
    faces = inverse.reshape(-1, 3)
    normals = face_normals(tris)
    good = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
    fid = np.nonzero(good)[0]
    f = faces[fid]
    edges = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    owner = np.concatenate([fid, fid, fid])
    edges.sort(axis=1)
    order = np.lexsort((edges[:, 1], edges[:, 0]))
    edges, owner = edges[order], owner[order]
    same_next = np.zeros(len(edges), dtype=bool)
    if len(edges) > 1:
        same_next[:-1] = np.all(edges[1:] == edges[:-1], axis=1)
    same_prev = np.zeros(len(edges), dtype=bool)
    same_prev[1:] = same_next[:-1]
    # pares de caras que comparten arista
    i = np.nonzero(same_next & ~same_prev)[0]
    dots = np.einsum("ij,ij->i", normals[owner[i]], normals[owner[i + 1]])
    sharp = i[dots < math.cos(math.radians(angle_deg))]
    border = np.nonzero(~same_next & ~same_prev)[0]
    sel = np.concatenate([sharp, border])
    return verts[edges[sel]]


# --------------------------------------------------------------------------- rayos

def ray_hits(origin, direction, tris: Tris) -> np.ndarray:
    """Distancia t de cada triángulo al origen del rayo (inf si no lo toca)."""
    if len(tris) == 0:
        return np.zeros(0)
    o = np.asarray(origin, dtype=np.float64)
    d = np.asarray(direction, dtype=np.float64)
    v0 = tris[:, 0]
    e1 = tris[:, 1] - v0
    e2 = tris[:, 2] - v0
    p = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, p)
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = 1.0 / det
        s = o - v0
        u = np.einsum("ij,ij->i", s, p) * inv
        q = np.cross(s, e1)
        v = (q @ d) * inv
        t = np.einsum("ij,ij->i", e2, q) * inv
        ok = (np.abs(det) > 1e-12) & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 1e-9)
    return np.where(ok, t, np.inf)


class Picker:
    """Decide qué pieza está bajo el ratón.

    Primero busca el punto que se ve en la malla real; luego elige la pieza
    cuya malla aproximada pasa más cerca de ese punto. Así un clic en la pared
    de un agujero selecciona el cilindro que se restó.
    """

    def __init__(self, real: Optional[Tris], ghosts: dict):
        self.real = real if real is not None and len(real) else None
        ids, parts = [], []
        for nid, tris in ghosts.items():
            if len(tris):
                parts.append(tris)
                ids.append(np.full(len(tris), nid))
        self.ghost_tris = np.concatenate(parts) if parts else EMPTY
        self.ghost_ids = np.concatenate(ids) if ids else np.zeros(0, dtype=int)
        box = bbox(self.real if self.real is not None else self.ghost_tris)
        self.size = float(np.linalg.norm(box[1] - box[0])) if box else 1.0

    def surface_point(self, origin, direction):
        if self.real is None:
            return None
        t = ray_hits(origin, direction, self.real)
        if not len(t) or not np.isfinite(t.min()):
            return None
        return np.asarray(origin) + np.asarray(direction) * t.min()

    def pick(self, origin, direction) -> tuple[Optional[int], Optional[np.ndarray]]:
        d = np.asarray(direction, dtype=np.float64)
        d = d / np.linalg.norm(d)
        o = np.asarray(origin, dtype=np.float64)
        tg = ray_hits(o, d, self.ghost_tris)
        if self.real is not None:
            tr = ray_hits(o, d, self.real)
            if not len(tr) or not np.isfinite(tr.min()):
                return None, None
            t_real = tr.min()
            hit = o + d * t_real
            if not len(tg):
                return None, hit
            diff = np.abs(tg - t_real)
            k = int(np.argmin(diff))
            if np.isfinite(diff[k]) and diff[k] <= max(1e-3, 0.03 * self.size):
                return int(self.ghost_ids[k]), hit
            return None, hit
        if not len(tg) or not np.isfinite(tg.min()):
            return None, None
        k = int(np.argmin(tg))
        return int(self.ghost_ids[k]), o + d * tg[k]


# --------------------------------------------------------------------------- utilidades numéricas

def _num(v, default=None):
    if isinstance(v, bool) or v is None or isinstance(v, Expr):
        return default
    if isinstance(v, (int, float)):
        return float(v)
    return default


def _vec(v, n=3, default=0.0, fill=None):
    """Convierte número o lista a vector de n componentes; None si no es literal."""
    if isinstance(v, bool) or isinstance(v, Expr) or v is None:
        return None
    if isinstance(v, (int, float)):
        return [float(v)] * n if fill is None else [float(v)] + [fill] * (n - 1)
    if isinstance(v, list) and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
        out = [float(x) for x in v[:n]]
        return out + [default] * (n - len(out))
    return None


def fragments(r: float, ctx: dict) -> int:
    """Misma fórmula que OpenSCAD (get_fragments_from_r)."""
    fn, fa, fs = ctx.get("fn", 0) or 0, ctx.get("fa", 12) or 12, ctx.get("fs", 2) or 2
    if r < 1e-9:
        return 3
    if fn > 0:
        return max(int(fn), 3)
    return int(math.ceil(max(min(360.0 / fa, r * 2 * math.pi / fs), 5)))


def _translate(v):
    m = np.eye(4)
    m[:3, 3] = v
    return m


def _rot_axis(axis, deg):
    a = np.asarray(axis, dtype=float)
    n = np.linalg.norm(a)
    if n == 0:
        return np.eye(4)
    x, y, z = a / n
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    C = 1 - c
    m = np.eye(4)
    m[:3, :3] = [[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                 [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                 [z * x * C - y * s, z * y * C + x * s, c + z * z * C]]
    return m


def node_matrix(node: Node, child_box=None) -> Optional[np.ndarray]:
    """Matriz 4×4 de una transformación; None si sus valores no son literales."""
    p = node.params
    k = node.kind
    if k == "translate":
        v = _vec(p.get("v", [0, 0, 0]))
        return None if v is None else _translate(v)
    if k == "rotate":
        a = p.get("a", 0)
        axis = p.get("v")
        if isinstance(a, list):
            r = _vec(a)
            if r is None:
                return None
            return _rot_axis([0, 0, 1], r[2]) @ _rot_axis([0, 1, 0], r[1]) @ _rot_axis([1, 0, 0], r[0])
        ang = _num(a)
        if ang is None:
            return None
        ax = _vec(axis) if axis is not None else [0, 0, 1]
        return None if ax is None else _rot_axis(ax, ang)
    if k == "scale":
        v = p.get("v", [1, 1, 1])
        s = _vec(v, default=1.0) if isinstance(v, list) else _vec(v)
        return None if s is None else np.diag([*s, 1.0])
    if k == "mirror":
        v = _vec(p.get("v", [1, 0, 0]))
        if v is None:
            return None
        n = np.asarray(v)
        if np.linalg.norm(n) == 0:
            return np.eye(4)
        n = n / np.linalg.norm(n)
        m = np.eye(4)
        m[:3, :3] -= 2 * np.outer(n, n)
        return m
    if k == "multmatrix":
        rows = p.get("m")
        if not isinstance(rows, list):
            return None
        m = np.eye(4)
        try:
            for i, row in enumerate(rows[:4]):
                for j, x in enumerate(row[:4]):
                    if isinstance(x, bool) or not isinstance(x, (int, float)):
                        return None
                    m[i, j] = x
        except TypeError:
            return None
        return m
    if k == "resize":
        size = _vec(p.get("newsize"))
        if size is None or child_box is None:
            return None
        lo, hi = child_box
        ext = hi - lo
        auto = p.get("auto", False)
        autos = auto if isinstance(auto, list) else [bool(auto)] * 3
        scales = [size[i] / ext[i] if size[i] > 0 and ext[i] > 0 else None for i in range(3)]
        known = [s for s in scales if s is not None]
        ref = max(known) if known else 1.0
        final = [s if s is not None else (ref if (i < len(autos) and autos[i]) else 1.0)
                 for i, s in enumerate(scales)]
        return np.diag([*final, 1.0])
    return np.eye(4)


def transform(tris: Tris, m: np.ndarray) -> Tris:
    if len(tris) == 0:
        return tris
    pts = tris.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
    return pts.reshape(-1, 3, 3)


def transform2d(poly: np.ndarray, m: np.ndarray) -> np.ndarray:
    pts = np.column_stack([poly, np.zeros(len(poly))]) @ m[:3, :3].T + m[:3, 3]
    return pts[:, :2]


# --------------------------------------------------------------------------- polígonos

def _area(poly: np.ndarray) -> float:
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def triangulate(poly: np.ndarray) -> list[tuple[int, int, int]]:
    """Recorte de orejas para un polígono simple. Devuelve índices."""
    n = len(poly)
    if n < 3:
        return []
    idx = list(range(n))
    if _area(poly) < 0:
        idx.reverse()
    result = []

    def inside(p, a, b, c):
        d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
        d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1])
        d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])
        neg = d1 < 0 or d2 < 0 or d3 < 0
        pos = d1 > 0 or d2 > 0 or d3 > 0
        return not (neg and pos)

    guard = 0
    while len(idx) > 3 and guard < n * n:
        guard += 1
        found = False
        for i in range(len(idx)):
            ia, ib, ic = idx[i - 1], idx[i], idx[(i + 1) % len(idx)]
            a, b, c = poly[ia], poly[ib], poly[ic]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= 1e-12:
                continue
            if any(inside(poly[j], a, b, c) for j in idx if j not in (ia, ib, ic)):
                continue
            result.append((ia, ib, ic))
            idx.pop(i)
            found = True
            break
        if not found:
            break
    if len(idx) == 3:
        result.append(tuple(idx))
    elif len(idx) > 3:  # polígono raro: abanico de lo que queda
        result += [(idx[0], idx[i], idx[i + 1]) for i in range(1, len(idx) - 1)]
    return result


def flat_tris(poly: np.ndarray, z: float = 0.0) -> Tris:
    t = triangulate(poly)
    if not t:
        return EMPTY
    p3 = np.column_stack([poly, np.full(len(poly), z)])
    return p3[np.array(t)]


def circle_points(r: float, n: int) -> np.ndarray:
    a = np.arange(n) * 2 * math.pi / n
    return np.column_stack([r * np.cos(a), r * np.sin(a)])


def _quads(ring_a: np.ndarray, ring_b: np.ndarray, closed: bool = True) -> Tris:
    """Une dos anillos 3D con la misma cantidad de puntos."""
    n = len(ring_a)
    count = n if closed else n - 1
    i = np.arange(count)
    j = (i + 1) % n
    t1 = np.stack([ring_a[i], ring_a[j], ring_b[j]], axis=1)
    t2 = np.stack([ring_a[i], ring_b[j], ring_b[i]], axis=1)
    return np.concatenate([t1, t2])


# --------------------------------------------------------------------------- primitivas

def cube(p) -> Optional[Tris]:
    s = _vec(p.get("size", 1))
    if s is None:
        return None
    lo = -np.array(s) / 2 if p.get("center") is True else np.zeros(3)
    x0, y0, z0 = lo
    x1, y1, z1 = lo + np.array(s)
    v = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]])
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
         (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return v[np.array(f)]


def sphere(p, ctx) -> Optional[Tris]:
    r = _num(p.get("r"))
    if p.get("d") is not None:
        d = _num(p.get("d"))
        r = d / 2 if d is not None else None
    if r is None:
        r = 1.0 if "r" not in p and "d" not in p else None
    if r is None:
        return None
    n = fragments(r, ctx)
    rings = (n + 1) // 2
    out = []
    ring_pts = []
    for i in range(rings):
        phi = math.pi * (i + 0.5) / rings
        ring_pts.append(np.column_stack([circle_points(r * math.sin(phi), n), np.full(n, r * math.cos(phi))]))
    for upper, lower in zip(ring_pts, ring_pts[1:]):
        out.append(_quads(lower, upper))
    top, bottom = ring_pts[0], ring_pts[-1]
    out.append(np.stack([np.repeat(top[:1], n - 2, 0), top[1:-1], top[2:]], axis=1))
    out.append(np.stack([np.repeat(bottom[:1], n - 2, 0), bottom[2:], bottom[1:-1]], axis=1))
    return np.concatenate(out)


def cylinder(p, ctx) -> Optional[Tris]:
    h = _num(p.get("h", 1))
    r = _num(p.get("r"), None)
    if p.get("d") is not None:
        d = _num(p.get("d"))
        r = d / 2 if d is not None else None
    if r is None:
        r = 1.0
    r1 = _num(p.get("r1"), None) if "r1" in p else (_num(p.get("d1")) / 2 if _num(p.get("d1")) is not None else r)
    r2 = _num(p.get("r2"), None) if "r2" in p else (_num(p.get("d2")) / 2 if _num(p.get("d2")) is not None else r)
    if h is None or r1 is None or r2 is None:
        return None
    z0 = -h / 2 if p.get("center") is True else 0.0
    n = fragments(max(r1, r2), ctx)
    b = np.column_stack([circle_points(r1, n), np.full(n, z0)])
    t = np.column_stack([circle_points(r2, n), np.full(n, z0 + h)])
    out = [_quads(b, t)]
    if r1 > 0:
        out.append(np.stack([np.repeat(b[:1], n - 2, 0), b[2:], b[1:-1]], axis=1))
    if r2 > 0:
        out.append(np.stack([np.repeat(t[:1], n - 2, 0), t[1:-1], t[2:]], axis=1))
    return np.concatenate(out)


def polyhedron(p) -> Optional[Tris]:
    pts, faces = p.get("points"), p.get("faces", p.get("triangles"))
    if not isinstance(pts, list) or not isinstance(faces, list):
        return None
    try:
        v = np.array(pts, dtype=float)
        out = []
        for f in faces:
            idx = [int(i) for i in f]
            out += [(idx[0], idx[k], idx[k + 1]) for k in range(1, len(idx) - 1)]
        return v[np.array(out)] if out else EMPTY
    except (ValueError, TypeError, IndexError):
        return None


def shape2d(node: Node, ctx) -> Optional[list]:
    """Polígonos 2D (lista de arrays Nx2) de un square/circle/polygon."""
    p = node.params
    if node.kind == "square":
        s = _vec(p.get("size", 1), 2)
        if s is None:
            return None
        lo = -np.array(s) / 2 if p.get("center") is True else np.zeros(2)
        x0, y0 = lo
        x1, y1 = lo + np.array(s)
        return [np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])]
    if node.kind == "circle":
        r = _num(p.get("r", 1))
        if p.get("d") is not None:
            d = _num(p.get("d"))
            r = d / 2 if d is not None else None
        return None if r is None else [circle_points(r, fragments(r, ctx))]
    if node.kind == "polygon":
        pts = p.get("points")
        if not isinstance(pts, list):
            return None
        try:
            v = np.array(pts, dtype=float)[:, :2]
        except (ValueError, TypeError, IndexError):
            return None
        paths = p.get("paths")
        if isinstance(paths, list) and paths and isinstance(paths[0], list):
            try:
                return [v[np.array([int(i) for i in paths[0]])]]
            except (ValueError, IndexError):
                return [v]
        return [v]
    return None


# --------------------------------------------------------------------------- recorrido del árbol

def _ctx(ctx: dict, node) -> dict:
    p = getattr(node, "params", {})
    if any(k in p for k in ("$fn", "$fa", "$fs")):
        ctx = dict(ctx)
        for key in ("fn", "fa", "fs"):
            v = _num(p.get("$" + key))
            if v is not None:
                ctx[key] = v
    return ctx


def _merge(into: dict, other: dict, m: Optional[np.ndarray] = None) -> None:
    for k, v in other.items():
        into[k] = transform(v, m) if m is not None else v


def flat(node, ctx) -> dict:
    """Contexto 2D: id → lista de polígonos (coordenadas locales)."""
    if not isinstance(node, Node):
        return {}
    ctx = _ctx(ctx, node)
    if node.kind in ("square", "circle", "polygon"):
        polys = shape2d(node, ctx)
        return {node.id: polys} if polys else {}
    if node.kind in ("translate", "rotate", "scale", "mirror", "multmatrix"):
        m = node_matrix(node)
        if m is None:
            return {}
        out = {}
        for c in node.children:
            for k, polys in flat(c, ctx).items():
                out[k] = [transform2d(pl, m) for pl in polys]
        return out
    out = {}
    if node.is_container:
        for c in node.children:
            out.update(flat(c, ctx))
    return out


def linear_extrude(node: Node, ctx) -> dict:
    p = node.params
    h = _num(p.get("height", p.get("h")))
    if h is None and isinstance(p.get("v"), list):
        v = _vec(p.get("v"))
        h = float(np.linalg.norm(v)) if v else None
    if h is None:
        h = 100.0 if not any(k in p for k in ("height", "h", "v")) else None
    if h is None:
        return {}
    twist = _num(p.get("twist", 0), 0.0) or 0.0
    sc = p.get("scale", 1)
    s2 = _vec(sc, 2, default=1.0) if isinstance(sc, list) else ([_num(sc, 1.0)] * 2)
    if s2 is None or None in s2:
        s2 = [1.0, 1.0]
    slices = _num(p.get("slices"))
    if slices is None:
        slices = max(1, int(math.ceil(abs(twist) / 5))) if twist else (1 if s2 == [1.0, 1.0] else 1)
    slices = max(1, int(slices))
    z0 = -h / 2 if p.get("center") is True else 0.0
    out = {}
    for nid, polys in flat_children(node, ctx).items():
        parts = []
        for poly in polys:
            if len(poly) < 3:
                continue
            if _area(poly) < 0:
                poly = poly[::-1]
            layers = []
            for k in range(slices + 1):
                t = k / slices
                ang = -math.radians(twist * t)
                sx = 1 + (s2[0] - 1) * t
                sy = 1 + (s2[1] - 1) * t
                c, s = math.cos(ang), math.sin(ang)
                xy = poly * [sx, sy]
                xy = np.column_stack([xy[:, 0] * c - xy[:, 1] * s, xy[:, 0] * s + xy[:, 1] * c])
                layers.append(np.column_stack([xy, np.full(len(xy), z0 + h * t)]))
            for a, b in zip(layers, layers[1:]):
                parts.append(_quads(a, b))
            tri = triangulate(poly)
            if tri:
                idx = np.array(tri)
                parts.append(layers[0][idx][:, ::-1])
                parts.append(layers[-1][idx])
        if parts:
            out[nid] = np.concatenate(parts)
    return out


def rotate_extrude(node: Node, ctx) -> dict:
    p = node.params
    angle = _num(p.get("angle", 360), None)
    start = _num(p.get("start", 0), 0.0) or 0.0
    if angle is None:
        return {}
    angle = max(-360.0, min(360.0, angle))
    full = abs(angle) >= 360
    out = {}
    for nid, polys in flat_children(node, ctx).items():
        parts = []
        for poly in polys:
            if len(poly) < 2:
                continue
            rmax = float(np.abs(poly[:, 0]).max())
            n = max(3, int(math.ceil(fragments(rmax, ctx) * abs(angle) / 360)))
            steps = n if full else n + 1
            rings = []
            for k in range(steps):
                a = math.radians(start + angle * k / n)
                rings.append(np.column_stack([poly[:, 0] * math.cos(a), poly[:, 0] * math.sin(a), poly[:, 1]]))
            pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if full else [])
            for a, b in pairs:
                parts.append(_quads(a, b))
            if not full:
                tri = triangulate(poly)
                if tri:
                    idx = np.array(tri)
                    parts.append(rings[0][idx])
                    parts.append(rings[-1][idx][:, ::-1])
        if parts:
            out[nid] = np.concatenate(parts)
    return out


def flat_children(node: Node, ctx) -> dict:
    out = {}
    for c in node.children:
        out.update(flat(c, ctx))
    return out


def solid(node, ctx) -> dict:
    """Contexto 3D: id → triángulos (coordenadas locales del nodo)."""
    if not isinstance(node, Node) or node.modifier == "*":
        return {}
    ctx = _ctx(ctx, node)
    k = node.kind
    p = node.params
    mesh = None
    if k == "cube":
        mesh = cube(p)
    elif k == "sphere":
        mesh = sphere(p, ctx)
    elif k == "cylinder":
        mesh = cylinder(p, ctx)
    elif k == "polyhedron":
        mesh = polyhedron(p)
    elif k in ("square", "circle", "polygon"):
        polys = shape2d(node, ctx)
        if polys:
            mesh = np.concatenate([flat_tris(pl) for pl in polys] or [EMPTY])
    elif k == "linear_extrude":
        return linear_extrude(node, ctx)
    elif k == "rotate_extrude":
        return rotate_extrude(node, ctx)
    elif node.is_container:
        out: dict = {}
        for c in node.children:
            out.update(solid(c, ctx))
        if k in ("translate", "rotate", "scale", "mirror", "multmatrix", "resize"):
            box = bbox(np.concatenate(list(out.values()))) if out and k == "resize" else None
            m = node_matrix(node, box)
            if m is None:
                return {}
            out = {key: transform(v, m) for key, v in out.items()}
        return out
    if mesh is None or len(mesh) == 0:
        return {}
    return {node.id: mesh}


def build_ghosts(doc: Document) -> dict:
    """Malla aproximada de cada pieza visible, en coordenadas del mundo."""
    ctx = {"fn": doc.fn or 0, "fa": 12, "fs": 2}
    out: dict = {}
    for n in doc.children:
        out.update(solid(n, ctx))
    return out


def pick_target(doc: Document, leaf_id: int) -> int:
    """Al hacer clic en un perfil 2D que está dentro de una extrusión, se selecciona la extrusión."""
    target = leaf_id
    for n, _, _ in doc.walk():
        if isinstance(n, Node) and n.kind in EXTRUDES and doc.is_descendant(leaf_id, n.id):
            target = n.id
    return target


def collect(doc: Document, ghosts: dict, ids) -> Tris:
    """Triángulos de las piezas indicadas (y de todo lo que contienen)."""
    parts = []
    for nid in ids:
        if nid in ghosts:
            parts.append(ghosts[nid])
        node = doc.find(nid)
        if node is None:
            continue
        stack = list(node.children)
        while stack:
            c = stack.pop()
            if c.id in ghosts:
                parts.append(ghosts[c.id])
            stack.extend(c.children)
    return np.concatenate(parts) if parts else EMPTY


def with_modifier(doc: Document, ghosts: dict, mod: str) -> Tris:
    ids = [n.id for n, _, _ in doc.walk() if isinstance(n, Node) and n.modifier == mod]
    return collect(doc, ghosts, ids)


# --------------------------------------------------------------------------- colores e iluminación

DEFAULT_COLOR = (0.80, 0.82, 0.86, 1.0)

# Luces fijas en el mundo (z hacia arriba): principal desde arriba-delante, relleno lateral y contraluz.
_LIGHTS = [
    (np.array([0.35, -0.55, 0.85]), 0.50),
    (np.array([-0.80, -0.35, 0.30]), 0.22),
    (np.array([0.60, 0.70, -0.20]), 0.14),
]
_AMBIENT = 0.40


def shade(normals: np.ndarray, colors: np.ndarray) -> np.ndarray:
    """Color final por cara (N, 4) aplicando luz ambiente + 3 luces direccionales."""
    k = np.full(len(normals), _AMBIENT)
    for direction, strength in _LIGHTS:
        d = direction / np.linalg.norm(direction)
        k += strength * np.clip(normals @ d, 0, None)
    out = np.array(colors, dtype=np.float64, copy=True)
    out[:, :3] = np.clip(out[:, :3] * k[:, None], 0, 1)
    return out


def load_off(path: str):
    """Lee un .off de OpenSCAD. Devuelve (triángulos, colores por cara o None)."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        words = []
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if line:
                words.append(line.split())
    if not words or not words[0][0].upper().endswith("OFF"):
        raise ValueError("No es un archivo OFF")
    head = words[0][1:] if len(words[0]) > 1 else []
    rows = words[1:]
    if not head:
        head, rows = rows[0], rows[1:]
    nv, nf = int(head[0]), int(head[1])
    verts = np.array([[float(x) for x in r[:3]] for r in rows[:nv]], dtype=np.float64).reshape(-1, 3)
    tris, colors, has_color = [], [], False
    for r in rows[nv:nv + nf]:
        n = int(r[0])
        idx = [int(x) for x in r[1:1 + n]]
        extra = r[1 + n:]
        rgba = None
        if len(extra) >= 3:
            vals = [float(x) for x in extra[:4]]
            if any(v > 1.0 for v in vals) or all(x.isdigit() for x in extra[:4]):
                vals = [v / 255.0 for v in vals]
            rgba = (vals + [1.0])[:4]
            has_color = True
        for k in range(1, n - 1):
            tris.append((idx[0], idx[k], idx[k + 1]))
            colors.append(rgba)
    if not tris:
        return EMPTY.copy(), None
    out = verts[np.array(tris)]
    if not has_color:
        return out, None
    return out, np.array([c if c is not None else DEFAULT_COLOR for c in colors], dtype=np.float64)


def load_mesh(path: str):
    if path.lower().endswith(".off"):
        return load_off(path)
    return load_stl(path), None


_BASIC_COLORS = {  # por si no hay Qt para resolver nombres (pruebas)
    "red": (1, 0, 0), "green": (0, 0.5, 0), "blue": (0, 0, 1), "yellow": (1, 1, 0),
    "white": (1, 1, 1), "black": (0, 0, 0), "gray": (0.5, 0.5, 0.5), "grey": (0.5, 0.5, 0.5),
    "orange": (1, 0.647, 0), "steelblue": (0.275, 0.510, 0.706), "gold": (1, 0.843, 0),
    "tomato": (1, 0.388, 0.278), "seagreen": (0.180, 0.545, 0.341),
}


def parse_color(c, alpha=None, resolve=None):
    """Convierte el argumento de color() a (r, g, b, a) entre 0 y 1. None si no se puede."""
    rgba = None
    if isinstance(c, list) and 3 <= len(c) <= 4 and all(_num(x) is not None for x in c):
        rgba = [float(x) for x in c] + [1.0] * (4 - len(c))
    elif isinstance(c, str):
        s = c.strip()
        if re.fullmatch(r"#?[0-9a-fA-F]{3,8}", s) and s.startswith("#"):
            h = s[1:]
            if len(h) in (3, 4):
                h = "".join(ch * 2 for ch in h)
            if len(h) in (6, 8):
                vals = [int(h[i:i + 2], 16) / 255 for i in range(0, len(h), 2)]
                rgba = vals + [1.0] * (4 - len(vals))
        if rgba is None and resolve is not None:
            r = resolve(s)
            if r is not None:
                rgba = list(r) + [1.0] * (4 - len(r))
        if rgba is None and s.lower() in _BASIC_COLORS:
            rgba = list(_BASIC_COLORS[s.lower()]) + [1.0]
    if rgba is None:
        return None
    a = _num(alpha)
    if a is not None:
        rgba[3] = a
    return tuple(float(min(1, max(0, x))) for x in rgba)


def node_colors(doc: Document, resolve=None) -> dict:
    """Color de cada pieza: el color() más cercano por encima de ella (como OpenSCAD)."""
    out = {}

    def rec(items, current):
        for n in items:
            col = current
            if isinstance(n, Node) and n.kind == "color":
                parsed = parse_color(n.params.get("c"), n.params.get("alpha"), resolve)
                col = parsed if parsed is not None else current
            out[n.id] = col
            rec(n.children, col)
    rec(doc.children, DEFAULT_COLOR)
    return out


def assign_faces(real: Tris, ghosts: dict) -> np.ndarray:
    """A qué pieza pertenece cada cara de la malla real (id, o -1 si no se sabe).

    Busca, para cada cara, una cara aproximada casi coplanar y cercana; así la
    pared de un agujero queda asociada al cilindro que se restó.
    """
    owner = np.full(len(real), -1, dtype=np.int64)
    if len(real) == 0 or not ghosts:
        return owner
    centers = real.mean(axis=1)
    normals = face_normals(real)
    box = bbox(real)
    tol = max(1e-3, 0.004 * float(np.linalg.norm(box[1] - box[0])))
    best = np.full(len(real), np.inf)
    for nid, g in ghosts.items():
        if len(g) == 0:
            continue
        lo, hi = g.reshape(-1, 3).min(axis=0) - tol, g.reshape(-1, 3).max(axis=0) + tol
        cand = np.nonzero(np.all((centers >= lo) & (centers <= hi), axis=1))[0]
        if not len(cand):
            continue
        gn = face_normals(g)
        g0 = g[:, 0]
        glo, ghi = g.min(axis=1) - tol, g.max(axis=1) + tol
        chunk = max(1, 2_000_000 // max(len(g), 1))
        for s in range(0, len(cand), chunk):
            c = cand[s:s + chunk]
            pc = centers[c]
            dist = np.abs(np.einsum("ijk,jk->ij", pc[:, None, :] - g0[None], gn))
            aligned = np.abs(normals[c] @ gn.T) > 0.9
            inside = np.all((pc[:, None, :] >= glo[None]) & (pc[:, None, :] <= ghi[None]), axis=2)
            dist = np.where(aligned & inside, dist, np.inf).min(axis=1)
            better = dist < np.minimum(best[c], tol)
            best[c[better]] = dist[better]
            owner[c[better]] = nid
    return owner


def colored(tris: Tris, owner: Optional[np.ndarray], colors: dict, face_colors=None) -> np.ndarray:
    """Colores por cara ya iluminados, listos para el visor."""
    if face_colors is not None:
        base = face_colors
    else:
        base = np.tile(np.array(DEFAULT_COLOR), (len(tris), 1))
        if owner is not None:
            for nid in np.unique(owner[owner >= 0]):
                base[owner == nid] = colors.get(int(nid), DEFAULT_COLOR)
    return shade(face_normals(tris), base)


def ghost_colors(ghosts: dict, colors: dict):
    """Triángulos y colores iluminados de la vista aproximada."""
    if not ghosts:
        return EMPTY, np.zeros((0, 4))
    tris = np.concatenate(list(ghosts.values()))
    base = np.concatenate([np.tile(np.array(colors.get(nid, DEFAULT_COLOR)), (len(t), 1))
                           for nid, t in ghosts.items()])
    return tris, shade(face_normals(tris), base)
