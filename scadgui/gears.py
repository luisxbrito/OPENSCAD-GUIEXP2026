"""Engranajes rectos de evolvente por módulo (sin Qt).

Las mismas fórmulas que el módulo ``spur_gear`` de library.py, para la vista aproximada, los
datos del panel y los avisos. Proporciones del sistema por módulo (ISO 53 / Machinery's
Handbook, «Gears and Gearing»; Casillas, cap. III):

* diámetro primitivo  d  = m · z
* diámetro de base    db = d · cos α          (α: ángulo de presión, normalmente 20°)
* diámetro exterior   da = m · (z + 2)        (cabeza del diente = m)
* diámetro de raíz    df = m · (z − 2.5)      (pie del diente = 1.25 m)
* distancia entre centros de dos engranajes   a  = m · (z1 + z2) / 2
* dientes mínimos sin socavado                z_min = 2 / sin² α redondeado hacia arriba (18 con 20°, 32 con 14.5°, 12 con 25°)

El flanco es la evolvente del círculo de base: en el radio R, el medio grueso del diente (en
radianes) vale s/(2r) + inv(α) − inv(acos(rb/R)), con inv(x) = tan x − x y s el grueso en el
círculo primitivo (π·m/2 menos la mitad de la holgura).
"""

from __future__ import annotations

import math

import numpy as np

FLANK_STEPS = 8   # puntos por flanco (los mismos que el módulo OpenSCAD)
N_ = str          # texto que la interfaz traduce después con tr() (lo recoge test_i18n)


def _inv(a_rad: float) -> float:
    return math.tan(a_rad) - a_rad


def dims(mod: float, teeth: int, pressure_angle: float = 20.0) -> dict:
    """Diámetros y datos del engranaje (mm)."""
    z = max(3, int(round(teeth)))
    alpha = math.radians(pressure_angle)
    d = mod * z
    return {
        "teeth": z,
        "pitch_d": d,
        "base_d": d * math.cos(alpha),
        "tip_d": mod * (z + 2),
        "root_d": max(mod * (z - 2.5), mod * 0.2),
        "circular_pitch": math.pi * mod,
        "min_teeth": min_teeth(pressure_angle),
    }


def min_teeth(pressure_angle: float = 20.0) -> int:
    """Menos dientes que esto y el pie del diente queda socavado al tallarlo (o interfiere)."""
    s = math.sin(math.radians(pressure_angle))
    return int(math.ceil(2 / (s * s) - 1e-9))


def center_distance(mod: float, z1: int, z2: int) -> float:
    return mod * (z1 + z2) / 2


def mesh_rotation(teeth: int) -> float:
    """Giro (grados) de un engranaje colocado en +X de otro con un diente en +X, para que un hueco
    suyo quede mirando al diente del primero."""
    z = max(3, int(round(teeth)))
    return 180.0 / z if z % 2 == 0 else 0.0


def polygon(mod: float, teeth: int, pressure_angle: float = 20.0, backlash: float = 0.0) -> np.ndarray:
    """Contorno del engranaje (N × 2), en sentido antihorario, con un diente centrado en +X."""
    z = max(3, int(round(teeth)))
    alpha = math.radians(pressure_angle)
    r = mod * z / 2
    rb = r * math.cos(alpha)
    ra = r + mod
    rf = max(r - 1.25 * mod, mod * 0.1)
    r0 = max(rb, rf)
    s_half = (math.pi * mod / 2 - backlash / 2) / (2 * r)

    def half(R: float) -> float:
        return max(0.0, s_half + _inv(alpha) - _inv(math.acos(min(1.0, rb / R))))

    flank = [r0 + (ra - r0) * k / FLANK_STEPS for k in range(FLANK_STEPS + 1)]
    pts = []
    for i in range(z):
        c = 2 * math.pi * i / z
        if rf < r0 - 1e-6:
            pts.append((rf * math.cos(c - half(r0)), rf * math.sin(c - half(r0))))
        pts += [(R * math.cos(c - half(R)), R * math.sin(c - half(R))) for R in flank]
        pts += [(R * math.cos(c + half(R)), R * math.sin(c + half(R))) for R in reversed(flank)]
        if rf < r0 - 1e-6:
            pts.append((rf * math.cos(c + half(r0)), rf * math.sin(c + half(r0))))
        mid = c + math.pi / z                              # fondo del hueco entre dientes
        pts.append((rf * math.cos(mid), rf * math.sin(mid)))
    return np.array(pts, dtype=np.float64)


def warnings(mod: float, teeth: int, pressure_angle: float = 20.0, backlash: float = 0.0,
             bore: float = 0.0) -> list[tuple[str, dict]]:
    """Problemas de diseño: (texto en español, valores para format). La interfaz traduce el texto."""
    out = []
    d = dims(mod, teeth, pressure_angle)
    if d["teeth"] < d["min_teeth"]:
        out.append((N_("Con {z} dientes y {a}° de presión el pie del diente queda socavado: el engranaje "
                    "se debilita y puede interferir. Usa al menos {n} dientes o un ángulo mayor (25°)."),
                    {"z": d["teeth"], "a": f"{pressure_angle:g}", "n": d["min_teeth"]}))
    if bore and bore >= d["root_d"] - 2 * mod:
        out.append((N_("El agujero ({b} mm) casi llega al fondo de los dientes ({f:.1f} mm): deja al menos "
                    "dos módulos de material."), {"b": f"{bore:g}", "f": d["root_d"]}))
    if backlash < 0 or backlash > mod * math.pi / 4:
        out.append((N_("La holgura ({j} mm) no es razonable para el módulo {m}: suele ser de 0 a 0.2 mm "
                    "(para impresión 3D, 0.1–0.3 mm)."), {"j": f"{backlash:g}", "m": f"{mod:g}"}))
    return out
