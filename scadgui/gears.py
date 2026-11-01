"""Engranajes de evolvente y cremalleras por módulo (sin Qt).

Las mismas fórmulas que los módulos ``spur_gear``, ``helical_gear`` y ``rack`` de library.py,
para la vista aproximada, los datos del panel y los avisos. Proporciones del sistema por módulo
(ISO 53 / Machinery's Handbook 27, «Gears and Gearing» y «Helical Gearing», p. 2099; Casillas,
cap. III):

* diámetro primitivo  d  = m · z
* diámetro de base    db = d · cos α          (α: ángulo de presión, normalmente 20°)
* diámetro exterior   da = m · (z + 2)        (cabeza del diente = m)
* diámetro de raíz    df = m · (z − 2.5)      (pie del diente = 1.25 m)
* distancia entre centros de dos engranajes   a  = m · (z1 + z2) / 2
* dientes mínimos sin socavado                z_min = 2 / sin² α redondeado hacia arriba (18 con 20°, 32 con 14.5°, 12 con 25°)

El flanco es la evolvente del círculo de base: en el radio R, el medio grueso del diente (en
radianes) vale s/(2r) + inv(α) − inv(acos(rb/R)), con inv(x) = tan x − x y s el grueso en el
círculo primitivo (π·m/2 menos la mitad de la holgura).

**Cremallera** (``rack_*``): es el «dentado básico» del sistema, el que define la forma del
diente (Machinery's Handbook, «Basic Rack of the 20-Degree and 25-Degree Full-Depth Involute
Systems»). Sus flancos son rectos, inclinados el ángulo de presión; paso π·m, cabeza m, pie
1.25·m y grueso π·m/2 en la línea primitiva. Engrana con cualquier engranaje del mismo módulo,
con el centro del engranaje a su radio primitivo sobre la línea primitiva de la cremallera.

**Helicoidal** (``helical_*``): el mismo diente, pero el módulo y el ángulo de presión que se
dan son los *normales* (medidos perpendiculares al diente) y en el plano de giro valen más
(Machinery's Handbook, «Rules and Formulas for Helical Gear Calculations», y AGMA 908-B89,
ec. 2 y 4):

* módulo aparente         mt = m / cos ψ          (ψ: ángulo de hélice)
* ángulo de presión apar.  tan αt = tan α / cos ψ
* diámetro primitivo      d  = z · m / cos ψ
* cabeza y pie se siguen midiendo con el módulo normal: da = d + 2m, df = d − 2.5m
* distancia entre centros a  = m · (z1 + z2) / (2 cos ψ)
* dientes mínimos sin socavado  z_min = 2 cos ψ / sin² αt (menos que un recto: 12 con ψ = 30°)
* avance de la hélice     L  = π · d / tan ψ
* giro del perfil sobre el grueso b:  2 · b · sen ψ / (z · m) radianes

El perfil del plano de giro es el de un recto de módulo mt y ángulo αt, con la cabeza y el pie
del módulo normal; girarlo linealmente con la altura da el helicoide de evolvente exacto, que es
lo que hace ``linear_extrude(twist = …)``. OpenSCAD gira en sentido **horario** con twist
positivo, así que una hélice a derechas (el ángulo crece con z) lleva twist negativo.
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


def _involute_polygon(z: int, r: float, rb: float, ra: float, rf: float, alpha: float,
                     s_half: float) -> np.ndarray:
    """Contorno de evolvente (N × 2), antihorario, con un diente centrado en +X.

    r: radio primitivo; rb: de base; ra: exterior; rf: de raíz; alpha: ángulo de presión en el
    círculo primitivo (radianes); s_half: medio grueso del diente ahí, en radianes.
    """
    r0 = max(rb, rf)

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


def polygon(mod: float, teeth: int, pressure_angle: float = 20.0, backlash: float = 0.0) -> np.ndarray:
    """Contorno del engranaje recto (N × 2), antihorario, con un diente centrado en +X."""
    z = max(3, int(round(teeth)))
    alpha = math.radians(pressure_angle)
    r = mod * z / 2
    return _involute_polygon(z, r, r * math.cos(alpha), r + mod, max(r - 1.25 * mod, mod * 0.1),
                             alpha, (math.pi * mod / 2 - backlash / 2) / (2 * r))


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


# --- Cremallera -------------------------------------------------------------

def rack_dims(mod: float, teeth: int, pressure_angle: float = 20.0, base: float = 0.0) -> dict:
    """Medidas de la cremallera (mm). La línea primitiva está en y = 0 y los dientes miran a +Y."""
    z = max(1, int(round(teeth)))
    p = math.pi * mod
    return {
        "teeth": z,
        "pitch": p,
        "length": z * p,
        "addendum": mod,
        "dedendum": 1.25 * mod,
        "height": 2.25 * mod + max(0.0, base),
        "tooth_thickness": p / 2,
    }


def rack_polygon(mod: float, teeth: int, pressure_angle: float = 20.0, backlash: float = 0.0,
                 base: float = 0.0) -> np.ndarray:
    """Perfil de la cremallera (N × 2) en XY: línea primitiva en y = 0, dientes hacia +Y, de
    x = 0 a x = z·π·m. Cada diente queda centrado en su paso, así que los huecos están en los
    múltiplos del paso (ahí se pone el engranaje que engrana)."""
    z = max(1, int(round(teeth)))
    p = math.pi * mod
    length = z * p
    ha, hf = mod, 1.25 * mod
    t = math.tan(math.radians(pressure_angle))
    hp = p / 4 - backlash / 4                 # medio grueso del diente en la línea primitiva
    # Con un ángulo de presión grande los flancos de dos dientes vecinos se cortan antes de llegar
    # al fondo: el hueco acaba en V en vez de tener meseta.
    y_v = (2 * hp - p) / (2 * t) if t > 1e-9 else -hf
    y_bot = max(-hf, y_v)
    land = y_v <= -hf + 1e-12                 # ¿queda meseta en el fondo del hueco?
    hb = hp - y_bot * t                       # medio grueso en el fondo del hueco
    tip = hp - ha * t                         # medio grueso en la cabeza (si ≤ 0, acaba en punta)
    y_back = -hf - max(0.0, base)
    pts: list[tuple[float, float]] = [(0.0, y_bot)] if land else []
    for i in range(z):
        c = (i + 0.5) * p
        pts.append((c - hb, y_bot))
        if tip > 0:
            pts += [(c - tip, ha), (c + tip, ha)]
        else:
            pts.append((c, hp / t))
        pts.append((c + hb, y_bot))
    if land:
        pts.append((length, y_bot))
    pts += [(length, y_back), (0.0, y_back)]
    return np.array(pts, dtype=np.float64)


def rack_gear_position(mod: float, teeth: int, gear_teeth: int) -> tuple[float, float, float]:
    """Dónde poner un engranaje recto para que engrane con la cremallera: (x, y, giro en grados).

    El engranaje va con su centro a su radio primitivo sobre la línea primitiva (y = 0) y en el
    centro de un hueco de la cremallera; el giro pone uno de sus dientes mirando hacia abajo."""
    z = max(1, int(round(teeth)))
    zg = max(3, int(round(gear_teeth)))
    x = (z // 2) * math.pi * mod              # un hueco cerca de la mitad de la cremallera
    k = round(0.75 * zg)                      # el diente que queda más cerca de los 270°
    return x, mod * zg / 2, 270.0 - 360.0 * k / zg


def rack_warnings(mod: float, teeth: int, pressure_angle: float = 20.0, backlash: float = 0.0,
                  base: float = 0.0) -> list[tuple[str, dict]]:
    """Problemas de diseño de la cremallera: (texto en español, valores para format)."""
    out = []
    d = rack_dims(mod, teeth, pressure_angle, base)
    t = math.tan(math.radians(pressure_angle))
    if base < mod:
        out.append((N_("La base ({b} mm) es más fina que el módulo: la cremallera se dobla con la "
                    "carga. Dale al menos {n:g} mm por debajo de los dientes."),
                    {"b": f"{base:g}", "n": round(mod, 3)}))
    if math.pi * mod / 4 - mod * t <= 0:
        out.append((N_("Con {a}° de presión el diente acaba en punta y pierde la cabeza: usa un "
                    "ángulo menor (20° o 25°)."), {"a": f"{pressure_angle:g}"}))
    elif (2 * (math.pi * mod / 4) - math.pi * mod) / (2 * t) > -1.25 * mod:
        out.append((N_("Con {a}° de presión los flancos de dos dientes vecinos se cortan antes del "
                    "fondo: el hueco acaba en V y la cremallera no llega a su profundidad."),
                    {"a": f"{pressure_angle:g}"}))
    if backlash < 0 or backlash > mod * math.pi / 4:
        out.append((N_("La holgura ({j} mm) no es razonable para el módulo {m}: suele ser de 0 a 0.2 mm "
                    "(para impresión 3D, 0.1–0.3 mm)."), {"j": f"{backlash:g}", "m": f"{mod:g}"}))
    _ = d
    return out


# --- Engranaje helicoidal ---------------------------------------------------

def helical_min_teeth(helix_angle: float, pressure_angle: float = 20.0) -> int:
    """Dientes mínimos sin socavado: 2·cos ψ / sin² αt (menos que en un recto)."""
    psi = math.radians(helix_angle)
    at = math.atan(math.tan(math.radians(pressure_angle)) / max(1e-9, math.cos(psi)))
    s = math.sin(at)
    return max(3, int(math.ceil(2 * math.cos(psi) / (s * s) - 1e-9)))


def helix_twist(mod: float, teeth: int, helix_angle: float, thickness: float) -> float:
    """Giro del perfil (grados) sobre el grueso: 2·b·sen ψ / (z·m). Positivo = hélice a derechas
    (el ángulo crece con la altura)."""
    z = max(3, int(round(teeth)))
    return math.degrees(2 * thickness * math.sin(math.radians(helix_angle)) / (z * mod))


def helical_dims(mod: float, teeth: int, helix_angle: float, pressure_angle: float = 20.0,
                 thickness: float = 0.0) -> dict:
    """Diámetros y datos del engranaje helicoidal (mm). El módulo y el ángulo de presión que se
    dan son los normales; aquí salen también los aparentes, del plano de giro."""
    z = max(3, int(round(teeth)))
    psi = math.radians(helix_angle)
    cos_psi = max(1e-9, math.cos(psi))
    mt = mod / cos_psi
    at = math.atan(math.tan(math.radians(pressure_angle)) / cos_psi)
    d = mt * z
    sin_psi = math.sin(psi)
    return {
        "teeth": z,
        "normal_mod": mod,
        "transverse_mod": mt,
        "transverse_angle": math.degrees(at),
        "pitch_d": d,
        "base_d": d * math.cos(at),
        "tip_d": d + 2 * mod,
        "root_d": max(d - 2.5 * mod, mod * 0.2),
        "circular_pitch": math.pi * mt,
        "axial_pitch": math.pi * mod / sin_psi if sin_psi > 1e-9 else math.inf,
        "lead": math.pi * d / math.tan(psi) if sin_psi > 1e-9 else math.inf,
        "twist": helix_twist(mod, z, helix_angle, thickness),
        # Solape axial: cuántos pasos axiales cubre el grueso. Por debajo de 1 el diente no envuelve
        # un paso completo y el engranaje se comporta casi como un recto (Handbook, ec. 19 y 20).
        "axial_overlap": thickness * sin_psi / (math.pi * mod) if mod > 0 else 0.0,
        "min_teeth": helical_min_teeth(helix_angle, pressure_angle),
    }


def helical_center_distance(mod: float, z1: int, z2: int, helix_angle: float) -> float:
    return mod * (z1 + z2) / (2 * max(1e-9, math.cos(math.radians(helix_angle))))


def helical_polygon(mod: float, teeth: int, helix_angle: float, pressure_angle: float = 20.0,
                    backlash: float = 0.0) -> np.ndarray:
    """Perfil del plano de giro (N × 2), antihorario, con un diente centrado en +X. Es el de un
    recto de módulo aparente mt y ángulo aparente αt, con la cabeza y el pie del módulo normal."""
    z = max(3, int(round(teeth)))
    cos_psi = max(1e-9, math.cos(math.radians(helix_angle)))
    mt = mod / cos_psi
    at = math.atan(math.tan(math.radians(pressure_angle)) / cos_psi)
    r = mt * z / 2
    return _involute_polygon(z, r, r * math.cos(at), r + mod, max(r - 1.25 * mod, mod * 0.1),
                             at, (math.pi * mt / 2 - backlash / 2) / (2 * r))


def helical_warnings(mod: float, teeth: int, helix_angle: float, pressure_angle: float = 20.0,
                     backlash: float = 0.0, bore: float = 0.0,
                     thickness: float = 0.0) -> list[tuple[str, dict]]:
    """Problemas de diseño del helicoidal: (texto en español, valores para format)."""
    out = []
    d = helical_dims(mod, teeth, helix_angle, pressure_angle, thickness)
    if d["teeth"] < d["min_teeth"]:
        out.append((N_("Con {z} dientes, {a}° de presión y {h}° de hélice el pie del diente queda "
                    "socavado. Usa al menos {n} dientes, o más hélice (con {h}° bastan {n})."),
                    {"z": d["teeth"], "a": f"{pressure_angle:g}", "h": f"{helix_angle:g}",
                     "n": d["min_teeth"]}))
    if thickness > 0 and d["axial_overlap"] < 1:
        out.append((N_("El solape axial es {v:.2f} (menos de 1): el diente no envuelve un paso "
                    "completo y se pierde la suavidad del helicoidal. Dale un grueso de "
                    "{n:.1f} mm o más."),
                    {"v": d["axial_overlap"], "n": math.pi * mod / max(1e-9, math.sin(math.radians(helix_angle)))}))
    if helix_angle > 35:
        out.append((N_("Con {h}° de hélice el empuje axial sobre los cojinetes es muy grande: para "
                    "ejes paralelos se usan de 15° a 30°."), {"h": f"{helix_angle:g}"}))
    if bore and bore >= d["root_d"] - 2 * mod:
        out.append((N_("El agujero ({b} mm) casi llega al fondo de los dientes ({f:.1f} mm): deja al menos "
                    "dos módulos de material."), {"b": f"{bore:g}", "f": d["root_d"]}))
    if backlash < 0 or backlash > mod * math.pi / 4:
        out.append((N_("La holgura ({j} mm) no es razonable para el módulo {m}: suele ser de 0 a 0.2 mm "
                    "(para impresión 3D, 0.1–0.3 mm)."), {"j": f"{backlash:g}", "m": f"{mod:g}"}))
    return out
