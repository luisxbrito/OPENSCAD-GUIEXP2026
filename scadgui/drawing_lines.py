"""Líneas de un plano a partir de la malla: aristas vivas y contorno, visibles y ocultas.

``projection()`` de OpenSCAD solo da la silueta rellena. Aquí, con la malla final que calcula
OpenSCAD, se sacan las aristas que se dibujan en un plano (donde las caras forman ángulo vivo,
los bordes y el contorno aparente de las superficies curvas) y se decide qué tramos se ven y
cuáles quedan tapados con un z-buffer de la vista. Sin Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

CREASE_DEG = 25.0      # ángulo entre caras a partir del cual la arista se dibuja (como en el visor)
RASTER = 1400          # píxeles del z-buffer en el lado mayor de la vista

# Giros de cada vista (los mismos que drawing.VIEW_TRANSFORMS), en el orden en que se aplican.
VIEW_TURNS = {
    "front": (("x", -90),),
    "top": (),
    "side": (("z", 90), ("x", -90)),
    "isometric": (("z", -45), ("x", -54.7356)),
}


def view_matrix(key: str) -> np.ndarray:
    """Matriz que lleva el mundo a la vista: X a la derecha, Y arriba y Z hacia el observador."""
    m = np.eye(3)
    for axis, deg in VIEW_TURNS[key]:
        c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        r = (np.array([[1, 0, 0], [0, c, -s], [0, s, c]]) if axis == "x" else
             np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]))
        m = r @ m
    return m


@dataclass
class MeshEdges:
    """Aristas únicas de la malla con sus dos caras (f2 = -1 si es un borde)."""
    verts: np.ndarray       # (V, 3)
    edges: np.ndarray       # (E, 2) índices de vértice
    f1: np.ndarray          # (E,) cara a un lado
    f2: np.ndarray          # (E,) cara al otro lado, o -1
    normals: np.ndarray     # (F, 3) normal de cada triángulo
    crease: np.ndarray      # (E,) arista viva o borde: se dibuja en todas las vistas


def mesh_edges(tris: np.ndarray, crease_deg: float = CREASE_DEG) -> MeshEdges:
    pts = tris.reshape(-1, 3)
    scale = max(float(np.abs(pts).max()), 1.0) if len(pts) else 1.0
    keys = np.round(pts / (scale * 1e-7)).astype(np.int64)
    _, index, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    faces = inverse.reshape(-1, 3)
    verts = pts[index]
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    length = np.linalg.norm(n, axis=1, keepdims=True)
    good = (length[:, 0] > 0) & (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & \
        (faces[:, 0] != faces[:, 2])
    length[length == 0] = 1
    normals = n / length
    fid = np.nonzero(good)[0]
    f = faces[fid]
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    owner = np.concatenate([fid, fid, fid])
    e.sort(axis=1)
    order = np.lexsort((e[:, 1], e[:, 0]))
    e, owner = e[order], owner[order]
    start = np.ones(len(e), dtype=bool)
    if len(e) > 1:
        start[1:] = np.any(e[1:] != e[:-1], axis=1)
    first = np.nonzero(start)[0]
    count = np.diff(np.append(first, len(e)))
    edges = e[first]
    f1 = owner[first]
    f2 = np.where(count >= 2, owner[np.minimum(first + 1, len(e) - 1)], -1)
    dots = np.where(f2 >= 0, np.einsum("ij,ij->i", normals[f1], normals[np.maximum(f2, 0)]), -1.0)
    crease = (count != 2) | (dots < math.cos(math.radians(crease_deg)))
    return MeshEdges(verts, edges, f1, f2, normals, crease)


def _zbuffer(tri2: np.ndarray, z: np.ndarray, origin, px: float, shape) -> np.ndarray:
    """Profundidad máxima (lo más cercano) por píxel. tri2: (T, 3, 2) en la vista; z: (T, 3)."""
    h, w = shape
    buf = np.full((h, w), -np.inf)
    g = (tri2 - origin) / px                       # en píxeles
    lo = np.floor(g.min(axis=1)).astype(int)
    hi = np.ceil(g.max(axis=1)).astype(int)
    lo = np.clip(lo, 0, [w - 1, h - 1])
    hi = np.clip(hi, 0, [w - 1, h - 1])
    # Coordenadas baricéntricas y profundidad como funciones lineales de (x, y): l = p·x + q·y + r.
    a, b, c = g[:, 0], g[:, 1], g[:, 2]
    d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    ok = np.abs(d) > 1e-12
    d = np.where(ok, d, 1.0)
    p1, q1 = (b[:, 1] - c[:, 1]) / d, (c[:, 0] - b[:, 0]) / d
    p2, q2 = (c[:, 1] - a[:, 1]) / d, (a[:, 0] - c[:, 0]) / d
    r1, r2 = -(p1 * c[:, 0] + q1 * c[:, 1]), -(p2 * c[:, 0] + q2 * c[:, 1])
    zp = p1 * (z[:, 0] - z[:, 2]) + p2 * (z[:, 1] - z[:, 2])
    zq = q1 * (z[:, 0] - z[:, 2]) + q2 * (z[:, 1] - z[:, 2])
    zr = r1 * (z[:, 0] - z[:, 2]) + r2 * (z[:, 1] - z[:, 2]) + z[:, 2]
    tol = -1e-6
    for t in np.nonzero(ok)[0]:
        (x0, y0), (x1, y1) = lo[t], hi[t]
        xs = np.arange(x0, x1 + 1) + 0.5
        ys = (np.arange(y0, y1 + 1) + 0.5)[:, None]
        l1 = p1[t] * xs + (q1[t] * ys + r1[t])
        l2 = p2[t] * xs + (q2[t] * ys + r2[t])
        inside = (l1 >= tol) & (l2 >= tol) & (l1 + l2 <= 1 - tol)
        region = buf[y0:y1 + 1, x0:x1 + 1]
        depth = zp[t] * xs + (zq[t] * ys + zr[t])
        np.maximum(region, np.where(inside, depth, -np.inf), out=region)
    return buf


def _chain(segments: list) -> list:
    """Une tramos que se tocan en polilíneas (para que el discontinuo no reempiece en cada tramo)."""
    if not segments:
        return []
    key = lambda p: (round(p[0], 4), round(p[1], 4))        # noqa: E731
    ends: dict = {}
    for i, (a, b) in enumerate(segments):
        ends.setdefault(key(a), []).append(i)
        ends.setdefault(key(b), []).append(i)
    used = [False] * len(segments)
    lines = []
    for i in range(len(segments)):
        if used[i]:
            continue
        used[i] = True
        line = [segments[i][0], segments[i][1]]
        for forward in (True, False):
            while True:
                tip = key(line[-1] if forward else line[0])
                nxt = next((j for j in ends.get(tip, ()) if not used[j]), None)
                if nxt is None:
                    break
                used[nxt] = True
                a, b = segments[nxt]
                p = b if key(a) == tip else a
                if forward:
                    line.append(p)
                else:
                    line.insert(0, p)
        lines.append(line)
    return lines


def view_lines(me: MeshEdges, tris: np.ndarray, key: str, hidden: bool = True, raster: int = RASTER):
    """Líneas de la vista en sus coordenadas 2D (sin escalar): (visibles, ocultas), cada una una
    lista de polilíneas [(x, y), ...]. Las ocultas que caen debajo de una visible no se dibujan."""
    if not len(me.edges):
        return [], []
    m = view_matrix(key)
    v = me.verts @ m.T
    nz = me.normals @ m.T[:, 2]
    tol = 1e-9
    front1 = nz[me.f1] > tol
    front2 = np.where(me.f2 >= 0, nz[np.maximum(me.f2, 0)] > tol, ~front1)
    # Contorno aparente: una cara mira al observador y la otra no. En las caras vistas de canto
    # (nz ≈ 0) solo cuenta si la otra mira de frente, para no duplicar.
    side1, side2 = np.abs(nz[me.f1]) <= tol, np.where(me.f2 >= 0, np.abs(nz[np.maximum(me.f2, 0)]) <= tol, False)
    silhouette = (me.f2 >= 0) & (front1 != front2) & ~(side1 & side2)
    sel = np.nonzero(me.crease | silhouette)[0]
    seg = v[me.edges[sel]]                                   # (K, 2, 3)
    d2 = np.linalg.norm(seg[:, 1, :2] - seg[:, 0, :2], axis=1)
    lo2, hi2 = v[:, :2].min(axis=0), v[:, :2].max(axis=0)
    size = float(max(hi2 - lo2)) or 1.0
    keep = d2 > size * 1e-6                                  # aristas en la dirección de la vista: un punto
    seg, d2 = seg[keep], d2[keep]
    if not len(seg):
        return [], []

    px = size / raster
    origin = lo2 - 2 * px
    shape = (int(math.ceil((hi2[1] - lo2[1]) / px)) + 5, int(math.ceil((hi2[0] - lo2[0]) / px)) + 5)
    t3 = tris @ m.T
    e1, e2 = t3[:, 1, :2] - t3[:, 0, :2], t3[:, 2, :2] - t3[:, 0, :2]
    # En una malla cerrada lo más cercano siempre es una cara que mira al observador: las de espaldas
    # y las de canto no hacen falta.
    facing = (e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) > 0
    buf = _zbuffer(t3[facing][:, :, :2], t3[facing][:, :, 2], origin, px, shape)
    # Un punto de una arista se ve si en su entorno de 3×3 píxeles hay alguno que no está claramente
    # por delante: su propia cara (a su misma profundidad) o el fondo. Con el máximo fallarían los
    # contornos de los cilindros, donde la cara de al lado está casi de canto y se acerca enseguida.
    pad = np.pad(buf, 1, constant_values=-np.inf)
    near = np.min([pad[1 + dy:1 + dy + shape[0], 1 + dx:1 + dx + shape[1]]
                   for dy in (-1, 0, 1) for dx in (-1, 0, 1)], axis=0)
    eps = 2.5 * px + size * 1e-6

    step = 1.2 * px
    n = np.maximum(1, np.ceil(d2 / step).astype(int))
    seg_id = np.repeat(np.arange(len(seg)), n)
    k = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    t0, t1 = k / n[seg_id], (k + 1) / n[seg_id]
    a, b = seg[seg_id, 0], seg[seg_id, 1]
    mid = a + (b - a) * ((t0 + t1) / 2)[:, None]
    ij = np.floor((mid[:, :2] - origin) / px).astype(int)
    ij[:, 0] = np.clip(ij[:, 0], 0, shape[1] - 1)
    ij[:, 1] = np.clip(ij[:, 1], 0, shape[0] - 1)
    seen = near[ij[:, 1], ij[:, 0]] <= mid[:, 2] + eps

    # Tramos ocultos que caen sobre una línea visible: manda la visible.
    covered = np.zeros(shape, dtype=bool)
    covered[ij[seen, 1], ij[seen, 0]] = True
    covered = np.pad(covered, 1)
    covered = np.any([covered[1 + dy:1 + dy + shape[0], 1 + dx:1 + dx + shape[1]]
                      for dy in (-1, 0, 1) for dx in (-1, 0, 1)], axis=0)
    under = ~seen & covered[ij[:, 1], ij[:, 0]]

    visible, hid = [], []
    pa = a[:, :2] + (b - a)[:, :2] * t0[:, None]
    pb = a[:, :2] + (b - a)[:, :2] * t1[:, None]
    state = np.where(seen, 1, np.where(under, 0, 2))         # 1 visible, 2 oculta, 0 nada
    # Tramos seguidos del mismo segmento y el mismo estado se juntan en uno.
    brk = np.ones(len(state), dtype=bool)
    brk[1:] = (seg_id[1:] != seg_id[:-1]) | (state[1:] != state[:-1])
    starts = np.nonzero(brk)[0]
    stops = np.append(starts[1:], len(state)) - 1
    # Aristas distintas que se proyectan en el mismo sitio (el borde delantero y el trasero de un
    # taladro visto de lado) se dibujan una vez.
    q = size * 1e-5
    done: set = set()
    for s0, s1 in zip(starts, stops):
        if state[s0] == 0 or (state[s0] == 2 and not hidden):
            continue
        piece = (tuple(map(float, pa[s0])), tuple(map(float, pb[s1])))
        ka, kb = (tuple(np.round(np.array(p) / q).astype(np.int64)) for p in piece)
        k = (state[s0], min(ka, kb), max(ka, kb))
        if k in done or ka == kb:
            continue
        done.add(k)
        (visible if state[s0] == 1 else hid).append(piece)
    return _chain(visible), _chain(hid)


def mesh_volume(tris: np.ndarray) -> float:
    return abs(float(np.einsum("ij,ij->i", tris[:, 0], np.cross(tris[:, 1], tris[:, 2])).sum()) / 6)
