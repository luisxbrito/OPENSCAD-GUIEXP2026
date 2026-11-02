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
                     s_half: float, at=None, widen: float = 1.0) -> np.ndarray:
    """Contorno de evolvente (N × 2), antihorario, con un diente centrado en +X.

    r: radio primitivo; rb: de base; ra: exterior; rf: de raíz; alpha: ángulo de presión en el
    círculo primitivo (radianes); s_half: medio grueso del diente ahí, en radianes.

    Para el cónico, el perfil se calcula con el engranaje virtual de Tredgold y luego se lleva al
    plano exterior: ``at`` cambia cada radio por el que le toca ahí y ``widen`` multiplica los
    ángulos (ver ``bevel_polygon``).
    """
    r0 = max(rb, rf)
    place = at or (lambda R: R)

    def half(R: float) -> float:
        return max(0.0, s_half + _inv(alpha) - _inv(math.acos(min(1.0, rb / R)))) * widen

    flank = [r0 + (ra - r0) * k / FLANK_STEPS for k in range(FLANK_STEPS + 1)]
    pts = []
    for i in range(z):
        c = 2 * math.pi * i / z
        qf = place(rf)
        if rf < r0 - 1e-6:
            pts.append((qf * math.cos(c - half(r0)), qf * math.sin(c - half(r0))))
        pts += [(place(R) * math.cos(c - half(R)), place(R) * math.sin(c - half(R))) for R in flank]
        pts += [(place(R) * math.cos(c + half(R)), place(R) * math.sin(c + half(R)))
                for R in reversed(flank)]
        if rf < r0 - 1e-6:
            pts.append((qf * math.cos(c + half(r0)), qf * math.sin(c + half(r0))))
        mid = c + math.pi / z                              # fondo del hueco entre dientes
        pts.append((qf * math.cos(mid), qf * math.sin(mid)))
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

def rack_transverse(mod: float, pressure_angle: float = 20.0,
                    helix_angle: float = 0.0) -> tuple[float, float]:
    """Módulo y ángulo de presión de la cremallera en el plano de giro, que son los que ve el
    engranaje. Con el dentado recto son los mismos que se dan."""
    cos_psi = max(1e-9, math.cos(math.radians(helix_angle)))
    return mod / cos_psi, math.degrees(math.atan(math.tan(math.radians(pressure_angle)) / cos_psi))


def rack_shear(helix_angle: float) -> float:
    """Cuánto se corre el dentado en X por cada mm de grueso. El diente de una cremallera
    helicoidal es una recta que forma el ángulo de hélice con el eje del engranaje, así que el
    perfil del plano de giro se sesga con la altura (tan ψ por mm)."""
    return math.tan(math.radians(helix_angle))


def rack_dims(mod: float, teeth: int, pressure_angle: float = 20.0, base: float = 0.0,
              helix_angle: float = 0.0, thickness: float = 0.0) -> dict:
    """Medidas de la cremallera (mm). La línea primitiva está en y = 0 y los dientes miran a +Y."""
    z = max(1, int(round(teeth)))
    mt, at = rack_transverse(mod, pressure_angle, helix_angle)
    p = math.pi * mt
    return {
        "teeth": z,
        "pitch": p,
        "length": z * p,
        "addendum": mod,
        "dedendum": 1.25 * mod,
        "height": 2.25 * mod + max(0.0, base),
        "tooth_thickness": p / 2,
        "transverse_mod": mt,
        "transverse_angle": at,
        "shift": thickness * rack_shear(helix_angle),
    }


def rack_polygon(mod: float, teeth: int, pressure_angle: float = 20.0, backlash: float = 0.0,
                 base: float = 0.0, helix_angle: float = 0.0) -> np.ndarray:
    """Perfil de la cremallera (N × 2) en XY: línea primitiva en y = 0, dientes hacia +Y, de
    x = 0 a x = z·π·mt. Cada diente queda centrado en su paso, así que los huecos están en los
    múltiplos del paso (ahí se pone el engranaje que engrana).

    Si es helicoidal, este es el perfil del plano de giro: paso y flancos del módulo y el ángulo
    aparentes, pero cabeza y pie con el módulo normal, igual que en el engranaje helicoidal. El
    sesgo con la altura lo pone quien lo extruye (ver ``rack_shear``)."""
    z = max(1, int(round(teeth)))
    mt, at = rack_transverse(mod, pressure_angle, helix_angle)
    p = math.pi * mt
    length = z * p
    ha, hf = mod, 1.25 * mod
    t = math.tan(math.radians(at))
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


def rack_gear_position(mod: float, teeth: int, gear_teeth: int,
                       helix_angle: float = 0.0) -> tuple[float, float, float]:
    """Dónde poner el engranaje que engrana con la cremallera: (x, y, giro en grados).

    El engranaje va con su centro a su radio primitivo sobre la línea primitiva (y = 0) y en el
    centro de un hueco de la cremallera; el giro pone uno de sus dientes mirando hacia abajo. Si
    la cremallera es helicoidal, las dos medidas salen del módulo aparente, que es el que marca
    tanto su paso como el diámetro del engranaje."""
    z = max(1, int(round(teeth)))
    zg = max(3, int(round(gear_teeth)))
    mt, _at = rack_transverse(mod, 20.0, helix_angle)
    x = (z // 2) * math.pi * mt               # un hueco cerca de la mitad de la cremallera
    k = round(0.75 * zg)                      # el diente que queda más cerca de los 270°
    return x, mt * zg / 2, 270.0 - 360.0 * k / zg


def rack_warnings(mod: float, teeth: int, pressure_angle: float = 20.0, backlash: float = 0.0,
                  base: float = 0.0, helix_angle: float = 0.0) -> list[tuple[str, dict]]:
    """Problemas de diseño de la cremallera: (texto en español, valores para format)."""
    out = []
    d = rack_dims(mod, teeth, pressure_angle, base, helix_angle)
    t = math.tan(math.radians(d["transverse_angle"]))
    if helix_angle > 35:
        out.append((N_("Con {h}° de hélice el empuje axial sobre los cojinetes es muy grande: para "
                    "ejes paralelos se usan de 15° a 30°."), {"h": f"{helix_angle:g}"}))
    if base < mod:
        out.append((N_("La base ({b} mm) es más fina que el módulo: la cremallera se dobla con la "
                    "carga. Dale al menos {n:g} mm por debajo de los dientes."),
                    {"b": f"{base:g}", "n": round(mod, 3)}))
    if d["pitch"] / 4 - mod * t <= 0:
        out.append((N_("Con {a}° de presión el diente acaba en punta y pierde la cabeza: usa un "
                    "ángulo menor (20° o 25°)."), {"a": f"{pressure_angle:g}"}))
    elif -d["pitch"] / (4 * t) > -1.25 * mod:
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


# --- Engranaje cónico recto -------------------------------------------------

def bevel_dims(mod: float, teeth: int, mate_teeth: int, shaft_angle: float = 90.0,
               pressure_angle: float = 20.0, face_width: float = 0.0) -> dict:
    """Medidas del cónico (mm y grados). Machinery's Handbook 27, «Rules and Formulas for
    Calculating Dimensions of Milled Bevel Gears», p. 2087-2088."""
    z = max(3, int(round(teeth)))
    zm = max(3, int(round(mate_teeth)))
    sigma = math.radians(shaft_angle)
    gamma = math.atan2(math.sin(sigma), zm / z + math.cos(sigma))   # ángulo del cono primitivo
    d = mod * z
    cone = d / (2 * max(1e-9, math.sin(gamma)))                     # distancia de cono exterior
    theta = math.atan(mod / cone)                                   # ángulo de cabeza
    phi = math.atan(1.25 * mod / cone)                              # ángulo de pie
    cos_g = math.cos(gamma)
    return {
        "teeth": z,
        "mate_teeth": zm,
        "gamma": math.degrees(gamma),
        "mate_gamma": shaft_angle - math.degrees(gamma),
        "cone": cone,
        "pitch_d": d,
        "tip_d": d + 2 * mod * cos_g,                               # O = D + 2·S·cos α
        "addendum_angle": math.degrees(theta),
        "dedendum_angle": math.degrees(phi),
        "face_angle": math.degrees(gamma + theta),                  # cono de cabeza
        "root_angle": math.degrees(gamma - phi),                    # cono de pie
        "virtual_teeth": z / max(1e-9, cos_g),                      # N' = N / cos α (Tredgold)
        "min_teeth": min_teeth(pressure_angle) * cos_g,
        "max_face": min(cone / 3, 8 * mod),                         # C/3 u 8·m, el menor
        # El blanco se tornea como un tronco de cono con la cara trasera plana, en el plano donde
        # el cono de cabeza llega al diámetro exterior: es la «vertex distance» J del Handbook,
        # J = (O/2)·cot(cono de cabeza). La delantera queda una cara más acá, medida sobre el
        # cono primitivo.
        "outer_z": (d / 2 + mod * cos_g) / math.tan(gamma + theta),
        "inner_z": (d / 2 + mod * cos_g) / math.tan(gamma + theta) - max(0.0, face_width) * cos_g,
        "circular_pitch": math.pi * mod,
    }


def bevel_polygon(mod: float, teeth: int, mate_teeth: int, shaft_angle: float = 90.0,
                  pressure_angle: float = 20.0, backlash: float = 0.0) -> np.ndarray:
    """Perfil del cónico (N × 2) en el plano exterior, perpendicular al eje, con el vértice del
    cono en el origen y un diente centrado en +X.

    El diente se saca del engranaje virtual de Tredgold (recto, del mismo módulo y con N/cos α
    dientes, el que se obtiene al desarrollar el cono posterior sobre un plano):

    * un punto que en el virtual está a ρ del centro queda a h = ρ − rv del cono primitivo,
      medidos perpendiculares a él, o sea sobre el cono de ángulo α + atan(h/C); su radio en la
      cara trasera es zo·tan(ese ángulo);
    * los ángulos alrededor del eje salen de dividir por cos α los del desarrollo (así el paso
      del virtual, 2π/N', se convierte en el de verdad, 2π/N).

    Como la cara trasera está justo en el plano del círculo de cabeza, la cabeza queda en
    D + 2·m·cos α, que es el diámetro exterior del Handbook. Barrer el perfil hacia el vértice da
    los conos de cabeza, primitivo y pie exactos.
    """
    z = max(3, int(round(teeth)))
    d = bevel_dims(mod, teeth, mate_teeth, shaft_angle, pressure_angle)
    gamma, cone, outer_z = math.radians(d["gamma"]), d["cone"], d["outer_z"]
    alpha = math.radians(pressure_angle)
    rv = mod * d["virtual_teeth"] / 2                               # radio primitivo del virtual
    rbv = rv * math.cos(alpha)
    rf = max(rv - 1.25 * mod, mod * 0.1)
    return _involute_polygon(z, rv, rbv, rv + mod, rf, alpha,
                             (math.pi * mod / 2 - backlash / 2) / (2 * rv),
                             at=lambda p: outer_z * math.tan(gamma + math.atan((p - rv) / cone)),
                             widen=1 / math.cos(gamma))


def bevel_warnings(mod: float, teeth: int, mate_teeth: int, shaft_angle: float = 90.0,
                   pressure_angle: float = 20.0, backlash: float = 0.0, bore: float = 0.0,
                   face_width: float = 0.0) -> list[tuple[str, dict]]:
    """Problemas de diseño del cónico: (texto en español, valores para format)."""
    out = []
    d = bevel_dims(mod, teeth, mate_teeth, shaft_angle, pressure_angle, face_width)
    if d["face_angle"] >= 88:
        out.append((N_("Con estos dientes y {s}° entre ejes el cono queda casi plano ({g:.1f}°) y el "
                    "diente no cabe: usa menos ángulo entre ejes o más dientes en esta rueda."),
                    {"s": f"{shaft_angle:g}", "g": d["gamma"]}))
    if face_width > d["max_face"]:
        out.append((N_("La cara ({f} mm) pasa del máximo {n:.1f} mm (un tercio de la distancia de cono "
                    "o ocho módulos): hacia el vértice el diente se queda sin sitio."),
                    {"f": f"{face_width:g}", "n": d["max_face"]}))
    if d["teeth"] < d["min_teeth"]:
        out.append((N_("Con {z} dientes y {a}° de presión el pie del diente queda socavado: el "
                    "cónico talla como un recto de {v:.1f} dientes y hacen falta {n:.0f}."),
                    {"z": d["teeth"], "a": f"{pressure_angle:g}", "v": d["virtual_teeth"],
                     "n": math.ceil(d["min_teeth"])}))
    if bore and bore >= 2 * d["inner_z"] * math.tan(math.radians(d["root_angle"])) - 2 * mod:
        out.append((N_("El agujero ({b} mm) no cabe por el extremo estrecho, donde el fondo del diente "
                    "mide {f:.1f} mm: deja al menos dos módulos de material."),
                    {"b": f"{bore:g}",
                     "f": 2 * d["inner_z"] * math.tan(math.radians(d["root_angle"]))}))
    if backlash < 0 or backlash > mod * math.pi / 4:
        out.append((N_("La holgura ({j} mm) no es razonable para el módulo {m}: suele ser de 0 a 0.2 mm "
                    "(para impresión 3D, 0.1–0.3 mm)."), {"j": f"{backlash:g}", "m": f"{mod:g}"}))
    return out


# --- Poleas dentadas (correas síncronas) ------------------------------------
# Secciones trapeciales clásicas ANSI/RMA IP-24 (Machinery's Handbook 27, "Synchronous Belt
# Nominal Tooth and Section Dimensions", tabla 40, y "... Standard Pulley Diameters", tabla 44).
# El hueco de la polea es el negativo del diente de la correa: paso p, ángulo de diente, altura
# ht y grueso bt (medido en la línea primitiva). La circunferencia primitiva PD = z·p/π queda por
# encima de la exterior (la de los lomos entre huecos): Ø exterior = PD − 2·PLD. Los flancos son
# rectos (como en la cremallera): no se modelan los redondeos ra/rr de la tabla, igual que la
# cremallera tampoco los lleva.
PULLEY_SECTIONS = {
    # sección: (paso, ángulo de diente, ht, bt, PLD), todo en mm.
    "MXL": (2.032, 40.0, 0.508, 1.143, 0.254),
    "XL": (5.08, 50.0, 1.27, 2.5654, 0.254),
    "L": (9.525, 40.0, 1.905, 4.6482, 0.381),
    "H": (12.7, 40.0, 2.286, 6.1214, 0.6858),
    "XH": (22.225, 40.0, 6.35, 12.573, 1.397),
}


def pulley_dims(section: str, teeth: int) -> dict:
    """Medidas de la polea (mm)."""
    p, angle, ht, bt, pld = PULLEY_SECTIONS.get(section, PULLEY_SECTIONS["XL"])
    z = max(3, int(round(teeth)))
    pitch_d = z * p / math.pi
    outer_d = pitch_d - 2 * pld
    root_d = outer_d - 2 * ht
    t = math.tan(math.radians(angle / 2))
    tip_half = bt / 2 - (ht + pld) * t      # medio grueso del hueco en el fondo
    opening_half = bt / 2 - pld * t         # medio grueso del hueco en la boca (Ø exterior)
    return {
        "teeth": z, "section": section, "pitch": p, "tooth_angle": angle, "tooth_height": ht,
        "tooth_width": bt, "pld": pld, "pitch_d": pitch_d, "outer_d": outer_d, "root_d": root_d,
        "tip_half": tip_half, "opening_half": opening_half, "circular_pitch": p,
    }


def pulley_polygon(section: str, teeth: int) -> np.ndarray:
    """Contorno de la polea (N × 2), antihorario: un cilindro de Ø exterior con z huecos
    trapeciales tallados, uno de ellos centrado en +X."""
    d = pulley_dims(section, teeth)
    z = d["teeth"]
    r_out = d["outer_d"] / 2
    r_root = max(0.1, d["root_d"] / 2)
    half_step = math.pi / z
    top_a = min(max(0.0, d["opening_half"]) / max(1e-6, r_out), half_step - 1e-6)
    bot_a = min(max(0.0, d["tip_half"]) / r_root, half_step - 1e-6)
    pts = []
    for i in range(z):
        c = 2 * math.pi * i / z
        pts.append((r_out * math.cos(c - top_a), r_out * math.sin(c - top_a)))
        pts.append((r_root * math.cos(c - bot_a), r_root * math.sin(c - bot_a)))
        pts.append((r_root * math.cos(c + bot_a), r_root * math.sin(c + bot_a)))
        pts.append((r_out * math.cos(c + top_a), r_out * math.sin(c + top_a)))
    return np.array(pts, dtype=np.float64)


def pulley_warnings(section: str, teeth: int, bore: float = 0.0) -> list[tuple[str, dict]]:
    """Problemas de diseño de la polea: (texto en español, valores para format)."""
    out = []
    d = pulley_dims(section, teeth)
    z = d["teeth"]
    if d["tip_half"] <= 0.05:
        out.append((N_("Con {z} dientes el fondo del hueco queda a filo para la sección {s}: usa "
                    "más dientes."), {"z": z, "s": section}))
    if z < 10:
        out.append((N_("Con {z} dientes la correa se dobla mucho en cada vuelta; se recomiendan "
                    "10 o más."), {"z": z}))
    if bore and bore >= d["root_d"] - 1.0:
        out.append((N_("El agujero ({b} mm) casi llega al fondo del hueco ({f:.1f} mm): deja algo "
                    "de material alrededor."), {"b": f"{bore:g}", "f": d["root_d"]}))
    return out


# --- Poleas trapeciales (correas en V) --------------------------------------
# Secciones clásicas ANSI/RMA IP-20 (Machinery's Handbook 27, tabla 9, "Classical V-Belt Sheave
# and Groove Dimensions ANSI/RMA IP-20, 1988"). Las variantes de muesca moldeada AX/BX/CX/DX
# comparten exactamente la misma ranura que su letra base, así que no se modelan aparte (la letra
# "Z" del sistema ISO no está en esta tabla, no se ofrece). El ángulo de la ranura (α) y su ancho
# en la boca (bg) cambian por tramos según el Ø primitivo/datum; hg (profundidad), Sg (separación
# entre ranuras) y Se (margen hasta el borde) son fijos por sección. No se modela el redondeo del
# fondo (RB de la tabla): la ranura queda con fondo plano, igual que la cremallera y la polea
# dentada no llevan tampoco sus propios redondeos.
V_BELT_SECTIONS = {
    # sección: (hg, Se, Sg, Ø datum mínimo recomendado, [(hasta Ø datum, ángulo, bg), ...]) en mm.
    "A": (11.684, 9.525, 15.875, 76.2,
          [(137.16, 34.0, 12.5476), (math.inf, 38.0, 12.8016)]),
    "B": (13.97, 12.7, 19.05, 137.16,
          [(177.8, 34.0, 16.1798), (math.inf, 38.0, 16.51)]),
    "C": (19.05, 17.4752, 25.4, 228.6,
          [(202.946, 34.0, 22.3266), (304.8, 36.0, 22.5298), (math.inf, 38.0, 22.733)]),
    "D": (25.908, 22.225, 36.5252, 330.2,
          [(329.946, 34.0, 31.9886), (431.8, 36.0, 32.2834), (math.inf, 38.0, 32.5782)]),
}


def v_pulley_dims(section: str, datum_d: float, grooves: int) -> dict:
    """Medidas de la polea trapecial (mm)."""
    hg, se, sg, min_d, tiers = V_BELT_SECTIONS.get(section, V_BELT_SECTIONS["A"])
    d = max(1.0, float(datum_d))
    angle, bg = tiers[-1][1], tiers[-1][2]
    for limit, a, b in tiers:
        if d <= limit:
            angle, bg = a, b
            break
    ng = max(1, int(round(grooves)))
    width = sg * (ng - 1) + 2 * se
    t = math.tan(math.radians(angle / 2))
    bottom_half = bg / 2 - hg * t
    return {
        "section": section, "datum_d": d, "grooves": ng, "groove_angle": angle,
        "groove_width": bg, "groove_depth": hg, "groove_spacing": sg, "edge_distance": se,
        "face_width": width, "bottom_half": bottom_half, "min_datum": min_d,
        "outer_d": d, "root_d": d - 2 * hg,
    }


def v_pulley_profile(section: str, datum_d: float, grooves: int) -> np.ndarray:
    """Perfil (radio, altura) de medio corte, para girar alrededor de Z (rotate_extrude): un
    disco liso de Ø primitivo con tantas ranuras en V como ``grooves``."""
    d = v_pulley_dims(section, datum_d, grooves)
    r_top = d["outer_d"] / 2
    r_bot = r_top - d["groove_depth"]
    half = d["groove_width"] / 2
    bottom_half = d["bottom_half"]
    t = math.tan(math.radians(d["groove_angle"] / 2))
    pts = [(r_top, 0.0)]
    for k in range(d["grooves"]):
        z = d["edge_distance"] + k * d["groove_spacing"]
        if bottom_half > 0:
            pts += [(r_top, z - half), (r_bot, z - bottom_half),
                    (r_bot, z + bottom_half), (r_top, z + half)]
        else:
            pts += [(r_top, z - half), (r_top - half / t, z), (r_top, z + half)]
    pts += [(r_top, d["face_width"]), (0.0, d["face_width"]), (0.0, 0.0)]
    return np.array(pts, dtype=np.float64)


def v_pulley_warnings(section: str, datum_d: float, grooves: int,
                       bore: float = 0.0) -> list[tuple[str, dict]]:
    """Problemas de diseño de la polea trapecial: (texto en español, valores para format)."""
    out = []
    d = v_pulley_dims(section, datum_d, grooves)
    if d["datum_d"] < d["min_datum"]:
        out.append((N_("Con Ø {d:g} mm la correa se dobla más de lo recomendado para la sección "
                    "{s}: lo mínimo son {m:g} mm."),
                    {"d": f"{d['datum_d']:g}", "s": section, "m": round(d["min_datum"], 1)}))
    if d["root_d"] <= 0 or (bore and bore >= d["root_d"] - 2.0):
        out.append((N_("El agujero ({b} mm) casi llega al fondo de la ranura (Ø {f:.1f} mm): deja "
                    "algo de material alrededor."), {"b": f"{bore:g}", "f": max(0.0, d["root_d"])}))
    return out
