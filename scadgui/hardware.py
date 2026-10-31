"""Biblioteca de componentes estándar industriales (tornillería, tuercas, rodamientos y perfiles).

Sigue las especificaciones normalizadas internacionales:
- Tornillos: ISO 4762 (DIN 912), ISO 4017 (DIN 933), DIN 7991 (avellanado) e ISO 7380 (botón).
- Holguras de paso: ISO 273 (fina, media, gruesa).
- Tuercas y arandelas: DIN 934, DIN 985, DIN 125, e insertos térmicos de latón (tipo Ruthex/CNC Kitchen).
- Rodamientos radiales de bolas: ISO 15 / DIN 625 (608, 623, 624, 625, 626, 688, 6900).
- Perfiles de aluminio extruido 2020 y 2040 (ranura de 6 mm simplificada, sin el ala interior en T).

Las piezas son modelos para encaje y visualización: sin rosca, con la geometría exterior
de la norma. Los diámetros de taladro siguen ISO 273.

Los nombres de las piezas y los textos de describe() pasan por tr(): salen en el idioma
de la interfaz en el momento de crear la pieza.
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from .i18n import tr
from .model import Node, format_number, make_node


# --------------------------------------------------------------------------- Tablas de dimensiones estándar

# Tornillo cilíndrico con hexágono interior (Allen) ISO 4762 / DIN 912
# d: diámetro nominal, dk: diámetro cabeza, k: altura cabeza, s: llave hexagonal, t: profundidad hexágono
SCREWS_ISO_4762 = {
    "M2":   {"d": 2.0, "dk": 3.8,  "k": 2.0,  "s": 1.5, "t": 1.0},
    "M2.5": {"d": 2.5, "dk": 4.5,  "k": 2.5,  "s": 2.0, "t": 1.2},
    "M3":   {"d": 3.0, "dk": 5.5,  "k": 3.0,  "s": 2.5, "t": 1.3},
    "M4":   {"d": 4.0, "dk": 7.0,  "k": 4.0,  "s": 3.0, "t": 2.0},
    "M5":   {"d": 5.0, "dk": 8.5,  "k": 5.0,  "s": 4.0, "t": 2.5},
    "M6":   {"d": 6.0, "dk": 10.0, "k": 6.0,  "s": 5.0, "t": 3.0},
    "M8":   {"d": 8.0, "dk": 13.0, "k": 8.0,  "s": 6.0, "t": 4.0},
    "M10":  {"d": 10.0, "dk": 16.0, "k": 10.0, "s": 8.0, "t": 5.0},
}

# Tornillo con cabeza hexagonal ISO 4017 / DIN 933
# d: diámetro nominal, s: ancho entre caras, k: altura cabeza
SCREWS_DIN_933 = {
    "M2":   {"d": 2.0, "s": 4.0,  "k": 1.4},
    "M2.5": {"d": 2.5, "s": 5.0,  "k": 1.7},
    "M3":   {"d": 3.0, "s": 5.5,  "k": 2.0},
    "M4":   {"d": 4.0, "s": 7.0,  "k": 2.8},
    "M5":   {"d": 5.0, "s": 8.0,  "k": 3.5},
    "M6":   {"d": 6.0, "s": 10.0, "k": 4.0},
    "M8":   {"d": 8.0, "s": 13.0, "k": 5.3},
    "M10":  {"d": 10.0, "s": 17.0, "k": 6.4},
}

# Tornillo avellanado cónico 90° con hexágono interior. Valores de DIN 7991; la ISO 10642
# da un diámetro de cabeza teórico algo mayor (p. ej. 6.72 mm en M3), por eso el avellanado
# del modo "taladro" añade holgura.
# d: diámetro nominal, dk: diámetro cabeza, k: altura cabeza cónica, s: llave hexagonal
SCREWS_ISO_10642 = {
    "M2":   {"d": 2.0, "dk": 4.0,  "k": 1.2, "s": 1.25},
    "M2.5": {"d": 2.5, "dk": 5.0,  "k": 1.5, "s": 1.5},
    "M3":   {"d": 3.0, "dk": 6.0,  "k": 1.7, "s": 2.0},
    "M4":   {"d": 4.0, "dk": 8.0,  "k": 2.3, "s": 2.5},
    "M5":   {"d": 5.0, "dk": 10.0, "k": 2.8, "s": 3.0},
    "M6":   {"d": 6.0, "dk": 12.0, "k": 3.3, "s": 4.0},
    "M8":   {"d": 8.0, "dk": 16.0, "k": 4.4, "s": 5.0},
}

# Tornillo de cabeza abombada (botón) ISO 7380-1. La norma empieza en M3.
# d: diámetro nominal, dk: diámetro cabeza, k: altura cabeza, s: llave hexagonal
SCREWS_ISO_7380 = {
    "M3":   {"d": 3.0, "dk": 5.7,  "k": 1.65, "s": 2.0},
    "M4":   {"d": 4.0, "dk": 7.6,  "k": 2.2,  "s": 2.5},
    "M5":   {"d": 5.0, "dk": 9.5,  "k": 2.75, "s": 3.0},
    "M6":   {"d": 6.0, "dk": 10.5, "k": 3.3,  "s": 4.0},
    "M8":   {"d": 8.0, "dk": 14.0, "k": 4.4,  "s": 5.0},
}

# Diámetros de taladro de paso según ISO 273 (Clearance holes)
CLEARANCE_HOLES_ISO_273 = {
    "M2":   {"fine": 2.2, "medium": 2.4, "coarse": 2.6},
    "M2.5": {"fine": 2.7, "medium": 2.9, "coarse": 3.1},
    "M3":   {"fine": 3.2, "medium": 3.4, "coarse": 3.6},
    "M4":   {"fine": 4.3, "medium": 4.5, "coarse": 4.8},
    "M5":   {"fine": 5.3, "medium": 5.5, "coarse": 5.8},
    "M6":   {"fine": 6.4, "medium": 6.6, "coarse": 7.0},
    "M8":   {"fine": 8.4, "medium": 9.0, "coarse": 10.0},
    "M10":  {"fine": 10.5, "medium": 11.0, "coarse": 12.0},
}

# Tuercas hexagonales DIN 934 / ISO 4032 (s: entre caras, m: altura, d: métrica)
NUTS_DIN_934 = {
    "M2":   {"d": 2.0, "s": 4.0,  "m": 1.6},
    "M2.5": {"d": 2.5, "s": 5.0,  "m": 2.0},
    "M3":   {"d": 3.0, "s": 5.5,  "m": 2.4},
    "M4":   {"d": 4.0, "s": 7.0,  "m": 3.2},
    "M5":   {"d": 5.0, "s": 8.0,  "m": 4.0},
    "M6":   {"d": 6.0, "s": 10.0, "m": 5.0},
    "M8":   {"d": 8.0, "s": 13.0, "m": 6.5},
    "M10":  {"d": 10.0, "s": 17.0, "m": 8.0},
}

# Tuercas autoblocantes DIN 985 (s: entre caras, m: altura total con anillo, d: métrica)
NUTS_DIN_985 = {
    "M2":   {"d": 2.0, "s": 4.0,  "m": 2.6},
    "M2.5": {"d": 2.5, "s": 5.0,  "m": 3.2},
    "M3":   {"d": 3.0, "s": 5.5,  "m": 4.0},
    "M4":   {"d": 4.0, "s": 7.0,  "m": 5.0},
    "M5":   {"d": 5.0, "s": 8.0,  "m": 5.0},
    "M6":   {"d": 6.0, "s": 10.0, "m": 6.0},
    "M8":   {"d": 8.0, "s": 13.0, "m": 8.0},
}

# Arandelas planas DIN 125 / ISO 7089 (d1: interior, d2: exterior, h: grosor)
WASHERS_DIN_125 = {
    "M2":   {"d1": 2.2, "d2": 5.0,  "h": 0.3},
    "M2.5": {"d1": 2.7, "d2": 6.0,  "h": 0.5},
    "M3":   {"d1": 3.2, "d2": 7.0,  "h": 0.5},
    "M4":   {"d1": 4.3, "d2": 9.0,  "h": 0.8},
    "M5":   {"d1": 5.3, "d2": 10.0, "h": 1.0},
    "M6":   {"d1": 6.4, "d2": 12.0, "h": 1.6},
    "M8":   {"d1": 8.4, "d2": 16.0, "h": 1.6},
}

# Insertos roscados de latón para inserción térmica en termoplásticos. No hay norma: las medidas
# son las habituales de fabricantes (Ruthex, CNC Kitchen); compruébalas con las de tu proveedor.
# d_ext: diámetro exterior estriado, L: longitud, d_hole: diámetro recomendado del taladro
HEAT_SET_INSERTS = {
    "M2":   {"d": 2.0, "d_ext": 3.2, "L": 4.0, "d_hole": 3.0},
    "M2.5": {"d": 2.5, "d_ext": 4.2, "L": 5.0, "d_hole": 4.0},
    "M3":   {"d": 3.0, "d_ext": 4.6, "L": 5.7, "d_hole": 4.0},
    "M4":   {"d": 4.0, "d_ext": 6.3, "L": 8.1, "d_hole": 5.6},
    "M5":   {"d": 5.0, "d_ext": 7.1, "L": 9.5, "d_hole": 6.4},
}

# Rodamientos radiales rígidos de bolas ISO 15 / DIN 625
# d: diámetro interior (eje), D: diámetro exterior, B: anchura/espesor
BEARINGS_ISO = {
    "608":  {"d": 8.0,  "D": 22.0, "B": 7.0},
    "623":  {"d": 3.0,  "D": 10.0, "B": 4.0},
    "624":  {"d": 4.0,  "D": 13.0, "B": 5.0},
    "625":  {"d": 5.0,  "D": 16.0, "B": 5.0},
    "626":  {"d": 6.0,  "D": 19.0, "B": 6.0},
    "688":  {"d": 8.0,  "D": 16.0, "B": 5.0},
    "6900": {"d": 10.0, "D": 22.0, "B": 6.0},
}

STANDARD_LENGTHS = [6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]


# Qué tabla usa cada norma (para ofrecer solo las métricas que existen en ella).
SCREW_TABLES = {
    "iso4762": SCREWS_ISO_4762,
    "din933": SCREWS_DIN_933,
    "iso10642": SCREWS_ISO_10642,
    "iso7380": SCREWS_ISO_7380,
}
NUT_TABLES = {"din934": NUTS_DIN_934, "din985": NUTS_DIN_985}

# Holgura extra (mm) sobre el diámetro o el ancho entre caras para alojamientos impresos.
FIT_ALLOWANCE = {"fine": 0.2, "medium": 0.4, "coarse": 0.6}
PROFILE_SLOT_WIDTH = 6.2   # boca de la ranura de un perfil 20xx
PROFILE_SLOT_DEPTH = 6.0
PROFILE_CORE_HOLE_R = 2.1  # taladro central (para roscar M5)


def available_sizes(category: str, standard: str = "") -> list[str]:
    """Métricas o modelos que existen en la tabla de esa norma, en orden."""
    if category == "screw":
        return list(SCREW_TABLES[standard])
    if category == "nut":
        return list(NUT_TABLES[standard])
    if category == "washer":
        return list(WASHERS_DIN_125)
    if category == "insert":
        return list(HEAT_SET_INSERTS)
    if category == "bearing":
        return list(BEARINGS_ISO)
    if category == "profile":
        return ["2020", "2040"]
    raise ValueError(f"Categoría desconocida: {category}")


def _lookup(table: dict, key: str, what: str) -> dict:
    """Busca una medida; si no está en la norma es un error (nunca se sustituye por otra)."""
    try:
        return table[key]
    except KeyError:
        raise ValueError(tr("{what} {key} no está en la tabla ({options})").format(
            what=what, key=key, options=", ".join(table))) from None


def _hex_circumradius(across_flats: float) -> float:
    """Radio del círculo circunscrito de un hexágono con ancho entre caras ``s``.

    ``circle(r, $fn = 6)`` dibuja el hexágono con ese radio en los vértices.
    """
    return round(across_flats / math.sqrt(3.0), 3)


def _hexagon(name: str, across_flats: float, height: float, u_fn) -> Node:
    ext = make_node("linear_extrude", u_fn(name))
    ext.params["height"] = round(height, 3)
    c = make_node("circle", u_fn(tr("Hexágono")))
    c.params["r"] = _hex_circumradius(across_flats)
    c.params["$fn"] = 6
    ext.children.append(c)
    return ext


def _cylinder(name: str, h: float, r: float, u_fn, r2: Optional[float] = None) -> Node:
    cyl = make_node("cylinder", u_fn(name))
    cyl.params["h"] = round(h, 3)
    if r2 is None:
        cyl.params["r"] = round(r, 3)
    else:
        cyl.params.pop("r", None)
        cyl.params["r1"] = round(r, 3)
        cyl.params["r2"] = round(r2, 3)
    return cyl


def _at(z: float, child: Node, u_fn=None, name: str = "") -> Node:
    move = make_node("translate", u_fn(name) if (u_fn and name) else "")
    move.params["v"] = [0.0, 0.0, round(z, 3)]
    move.children.append(child)
    return move


def _colored(name: str, color: str, child: Node, u_fn) -> Node:
    root = make_node("color", u_fn(name))
    root.params["c"] = color
    root.children.append(child)
    return root


def _through_hole(d_hole: float, length: float, u_fn) -> Node:
    """Taladro de paso que sobresale 1 mm por cada lado para que la resta quede limpia."""
    return _at(-1.0, _cylinder(tr("Paso pasante"), length + 2.0, d_hole / 2.0, u_fn))


def create_screw_node(
    standard: str,
    size: str,
    length: float = 16.0,
    mode: str = "solid",
    fit: str = "medium",
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Tornillo normalizado (``mode="solid"``) o su taladro con cajeado (``mode="hole"``).

    El vástago va de z = 0 a z = length y la cabeza queda encima, salvo en el avellanado,
    donde la longitud nominal incluye la cabeza (como marca la norma).
    """
    u_fn = unique_fn or (lambda s: s)
    table = SCREW_TABLES.get(standard)
    if table is None:
        raise ValueError(f"Norma de tornillo desconocida: {standard}")
    spec = _lookup(table, size, tr("Métrica"))
    d = spec["d"]
    d_hole = _lookup(CLEARANCE_HOLES_ISO_273, size, tr("Métrica"))[fit]
    extra = FIT_ALLOWANCE[fit]
    L = format_number(length)

    if standard == "iso4762":
        dk, k, s, t = spec["dk"], spec["k"], spec["s"], spec["t"]
        label = tr("Tornillo {size}x{length} ISO4762").format(size=size, length=L)
        if mode == "solid":
            head = make_node("difference", u_fn(tr("Cabeza Allen")))
            head.children.append(_cylinder(tr("Cuerpo cabeza"), k, dk / 2.0, u_fn))
            head.children.append(_at(k - t, _hexagon(tr("Hueco llave"), s, t + 0.1, u_fn)))
            grp = make_node("group", u_fn(label))
            grp.children += [_cylinder(tr("Vástago {size}").format(size=size), length, d / 2.0, u_fn), _at(length, head, u_fn, tr("Posición cabeza"))]
            return _colored(label, "DimGray", grp, u_fn)
        mask = make_node("group", u_fn(tr("Taladro {size}x{length}").format(size=size, length=L)))
        mask.children += [_through_hole(d_hole, length, u_fn),
                          _at(length, _cylinder(tr("Cajeado cabeza"), k + 10.0, (dk + 2 * extra) / 2.0, u_fn))]
        return mask

    if standard == "din933":
        s, k = spec["s"], spec["k"]
        label = tr("Tornillo {size}x{length} DIN933").format(size=size, length=L)
        if mode == "solid":
            grp = make_node("group", u_fn(label))
            grp.children += [_cylinder(tr("Vástago {size}").format(size=size), length, d / 2.0, u_fn),
                             _at(length, _hexagon(tr("Cabeza hexagonal"), s, k, u_fn), u_fn, tr("Posición cabeza"))]
            return _colored(label, "LightSlateGray", grp, u_fn)
        mask = make_node("group", u_fn(tr("Taladro {size}x{length} DIN933").format(size=size, length=L)))
        mask.children += [_through_hole(d_hole, length, u_fn),
                          _at(length, _hexagon(tr("Cajeado hexagonal"), s + extra, k + 10.0, u_fn))]
        return mask

    if standard == "iso10642":
        dk, k, s = spec["dk"], spec["k"], spec["s"]
        label = tr("Tornillo avellanado {size}x{length} DIN7991").format(size=size, length=L)
        shank_h = length - k
        if mode == "solid":
            head = make_node("difference", u_fn(tr("Cono con Allen")))
            head.children.append(_cylinder(tr("Cono 90°"), k, d / 2.0, u_fn, r2=dk / 2.0))
            socket_depth = min(1.3, k * 0.7)
            head.children.append(_at(k - socket_depth, _hexagon(tr("Hueco llave"), s, socket_depth + 0.1, u_fn)))
            grp = make_node("group", u_fn(label))
            grp.children += [_cylinder(tr("Vástago {size}").format(size=size), shank_h, d / 2.0, u_fn),
                             _at(shank_h, head, u_fn, tr("Cabeza cónica"))]
            return _colored(label, "DarkSlateGray", grp, u_fn)
        mask = make_node("group", u_fn(tr("Taladro avellanado {size}").format(size=size)))
        mask.children += [_through_hole(d_hole, length, u_fn),
                          _at(shank_h, _cylinder(tr("Avellanado 90°"), k + 0.1, d_hole / 2.0, u_fn,
                                                 r2=(dk + 2 * extra) / 2.0))]
        return mask

    # iso7380: cabeza de botón (aproximada con un tronco de cono)
    dk, k = spec["dk"], spec["k"]
    label = tr("Tornillo botón {size}x{length} ISO7380").format(size=size, length=L)
    if mode == "solid":
        grp = make_node("group", u_fn(label))
        grp.children += [_cylinder(tr("Vástago"), length, d / 2.0, u_fn),
                         _at(length, _cylinder(tr("Cabeza botón"), k, dk / 2.0, u_fn, r2=dk * 0.375))]
        return _colored(label, "DimGray", grp, u_fn)
    mask = make_node("group", u_fn(tr("Taladro {size}x{length} ISO7380").format(size=size, length=L)))
    mask.children += [_through_hole(d_hole, length, u_fn),
                      _at(length, _cylinder(tr("Cajeado cabeza"), k + 10.0, (dk + 2 * extra) / 2.0, u_fn))]
    return mask


def create_nut_node(
    standard: str,
    size: str,
    mode: str = "solid",
    fit: str = "medium",
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Tuerca hexagonal (DIN 934 o DIN 985) o el alojamiento para embutirla."""
    u_fn = unique_fn or (lambda s: s)
    table = NUT_TABLES.get(standard)
    if table is None:
        raise ValueError(f"Norma de tuerca desconocida: {standard}")
    spec = _lookup(table, size, tr("Métrica"))
    d, s, m = spec["d"], spec["s"], spec["m"]
    label = tr("Tuerca {size} {standard}").format(size=size, standard=standard.upper())

    if mode == "solid":
        diff = make_node("difference", u_fn(label))
        diff.children += [_hexagon(tr("Prisma hexagonal"), s, m, u_fn),
                          _at(-0.2, _cylinder(tr("Agujero interior"), m + 0.4, d / 2.0, u_fn))]
        return _colored(label, "LightGray", diff, u_fn)
    grp = make_node("group", u_fn(tr("Alojamiento tuerca {size}").format(size=size)))
    grp.children.append(_hexagon(tr("Cajeado tuerca"), s + FIT_ALLOWANCE[fit], m + 0.3, u_fn))
    return grp


def create_heat_set_node(
    size: str,
    mode: str = "solid",
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Inserto roscado de latón o el taladro ciego donde se funde con el soldador."""
    u_fn = unique_fn or (lambda s: s)
    spec = _lookup(HEAT_SET_INSERTS, size, tr("Inserto"))
    d, d_ext, length, d_hole = spec["d"], spec["d_ext"], spec["L"], spec["d_hole"]

    if mode == "solid":
        diff = make_node("difference", u_fn(tr("Inserto {size}x{length}").format(size=size, length=format_number(length))))
        diff.children += [_cylinder(tr("Cuerpo moleteado"), length, d_ext / 2.0, u_fn),
                          _at(-0.2, _cylinder(tr("Agujero interior"), length + 0.4, d / 2.0, u_fn))]
        return _colored(tr("Inserto térmico {size}").format(size=size), "Gold", diff, u_fn)
    grp = make_node("group", u_fn(tr("Taladro inserto {size}").format(size=size)))
    # 1 mm más de profundidad para el material que desplaza el inserto, y un chaflán de entrada.
    grp.children += [_cylinder(tr("Taladro térmico"), length + 1.0, d_hole / 2.0, u_fn),
                     _at(length, _cylinder(tr("Guía de entrada"), 0.8, d_hole / 2.0, u_fn, r2=(d_hole + 0.8) / 2.0))]
    return grp


def create_washer_node(
    size: str,
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Arandela plana DIN 125 / ISO 7089."""
    u_fn = unique_fn or (lambda s: s)
    spec = _lookup(WASHERS_DIN_125, size, tr("Métrica"))
    d1, d2, h = spec["d1"], spec["d2"], spec["h"]
    diff = make_node("difference", u_fn(tr("Arandela plana")))
    diff.children += [_cylinder(tr("Exterior"), h, d2 / 2.0, u_fn),
                      _at(-0.1, _cylinder(tr("Paso interior"), h + 0.2, d1 / 2.0, u_fn))]
    return _colored(tr("Arandela {size} DIN125").format(size=size), "Silver", diff, u_fn)


def create_bearing_node(
    model: str = "608",
    mode: str = "solid",
    fit: str = "medium",
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Rodamiento rígido de bolas (anillo macizo, sin bolas) o su alojamiento con paso de eje."""
    u_fn = unique_fn or (lambda s: s)
    spec = _lookup(BEARINGS_ISO, model, tr("Rodamiento"))
    d, d_ext, b = spec["d"], spec["D"], spec["B"]

    if mode == "solid":
        diff = make_node("difference", u_fn(tr("Anillo rodamiento {model}").format(model=model)))
        diff.children += [_cylinder(tr("Pista exterior"), b, d_ext / 2.0, u_fn),
                          _at(-0.2, _cylinder(tr("Eje interior"), b + 0.4, d / 2.0, u_fn))]
        return _colored(tr("Rodamiento {model}").format(model=model), "Silver", diff, u_fn)
    # Un alojamiento impreso necesita algo menos de holgura que un taladro de paso.
    tol = {"fine": 0.2, "medium": 0.35, "coarse": 0.5}[fit]
    grp = make_node("group", u_fn(tr("Alojamiento rodamiento {model}").format(model=model)))
    grp.children += [_cylinder(tr("Cajeado rodamiento"), b + 0.2, (d_ext + tol) / 2.0, u_fn),
                     _at(-10.0, _cylinder(tr("Paso libre eje"), b + 20.0, (d + 1.0) / 2.0, u_fn))]
    return grp


def create_profile_node(
    model: str = "2020",
    length: float = 100.0,
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Perfil de aluminio 2020 o 2040, centrado en el origen y a lo largo de Z.

    Lleva una ranura de 6 mm por cada módulo de 20 mm de cara y el taladro central de cada
    módulo. La ranura es recta (sin la forma en T interior): sirve para encajes y planos.
    """
    if model not in ("2020", "2040"):
        raise ValueError(f"Perfil desconocido: {model}")
    u_fn = unique_fn or (lambda s: s)
    w, h = 20.0, (40.0 if model == "2040" else 20.0)
    modules_y = [-10.0, 10.0] if model == "2040" else [0.0]   # centros de cada módulo de 20 mm
    cut_len = round(length + 2.0, 3)

    diff = make_node("difference", u_fn(tr("Perfil de aluminio")))
    box = make_node("cube", u_fn(tr("Cuerpo exterior")))
    box.params["size"] = [w, h, round(length, 3)]
    box.params["center"] = True
    diff.children.append(box)

    def cut(name: str, x: float, y: float, size_xy: list) -> None:
        move = make_node("translate")
        move.params["v"] = [round(x, 3), round(y, 3), 0.0]
        c = make_node("cube", u_fn(name))
        c.params["size"] = [round(size_xy[0], 3), round(size_xy[1], 3), cut_len]
        c.params["center"] = True
        move.children.append(c)
        diff.children.append(move)

    depth = PROFILE_SLOT_DEPTH
    for i, y in enumerate(modules_y, 1):
        bore = make_node("translate")
        bore.params["v"] = [0.0, y, 0.0]
        core = make_node("cylinder", u_fn(tr("Taladro central {i}").format(i=i)))
        core.params["h"] = cut_len
        core.params["r"] = PROFILE_CORE_HOLE_R
        core.params["center"] = True
        bore.children.append(core)
        diff.children.append(bore)
        # Ranuras en las caras laterales (±X), una por módulo.
        cut(tr("Ranura X+ {i}").format(i=i), w / 2 - depth / 2, y, [depth, PROFILE_SLOT_WIDTH])
        cut(tr("Ranura X- {i}").format(i=i), -w / 2 + depth / 2, y, [depth, PROFILE_SLOT_WIDTH])
    # Ranuras en las caras de 20 mm de los extremos (±Y).
    cut(tr("Ranura Y+"), 0.0, h / 2 - depth / 2, [PROFILE_SLOT_WIDTH, depth])
    cut(tr("Ranura Y-"), 0.0, -h / 2 + depth / 2, [PROFILE_SLOT_WIDTH, depth])

    return _colored(tr("Perfil {model}x{length}mm").format(model=model, length=format_number(length)), "LightGray", diff, u_fn)


def describe(category: str, standard: str, size: str, length: float, fit: str) -> list[str]:
    """Líneas de texto con las medidas que usará la pieza (las mismas que los constructores).

    La primera línea es el título; el diálogo la muestra en negrita.
    """
    fmt = format_number
    extra = FIT_ALLOWANCE[fit]
    if category == "screw":
        spec = _lookup(SCREW_TABLES[standard], size, tr("Métrica"))
        clr, dk, k, s = fmt(CLEARANCE_HOLES_ISO_273[size][fit]), spec["dk"], spec["k"], spec["s"]
        if standard == "iso4762":
            return [tr("Tornillo Allen {size}×{length} (ISO 4762 / DIN 912)").format(size=size, length=fmt(length)),
                    tr("Cabeza Ø{dk} × {k} mm, llave {s} mm").format(dk=fmt(dk), k=fmt(k), s=fmt(s)),
                    tr("Taladro de paso (ISO 273): Ø{hole} mm · cajeado Ø{recess} mm").format(
                        hole=clr, recess=fmt(dk + 2 * extra))]
        if standard == "din933":
            return [tr("Tornillo hexagonal {size}×{length} (DIN 933 / ISO 4017)").format(size=size, length=fmt(length)),
                    tr("Cabeza {s} mm entre caras × {k} mm").format(s=fmt(s), k=fmt(k)),
                    tr("Taladro de paso (ISO 273): Ø{hole} mm · cajeado {recess} mm entre caras").format(
                        hole=clr, recess=fmt(s + extra))]
        if standard == "iso10642":
            return [tr("Tornillo avellanado 90° {size}×{length} (DIN 7991)").format(size=size, length=fmt(length)),
                    tr("Cabeza Ø{dk} × {k} mm (la longitud incluye la cabeza)").format(dk=fmt(dk), k=fmt(k)),
                    tr("Taladro de paso: Ø{hole} mm · avellanado hasta Ø{recess} mm").format(
                        hole=clr, recess=fmt(dk + 2 * extra))]
        return [tr("Tornillo de botón {size}×{length} (ISO 7380)").format(size=size, length=fmt(length)),
                tr("Cabeza Ø{dk} × {k} mm").format(dk=fmt(dk), k=fmt(k)),
                tr("Taladro de paso (ISO 273): Ø{hole} mm · cajeado Ø{recess} mm").format(
                    hole=clr, recess=fmt(dk + 2 * extra))]
    if category == "nut":
        spec = _lookup(NUT_TABLES[standard], size, tr("Métrica"))
        title = (tr("Tuerca hexagonal autoblocante {size} DIN 985") if standard == "din985"
                 else tr("Tuerca hexagonal {size} DIN 934"))
        return [title.format(size=size),
                tr("{s} mm entre caras × {m} mm de alto").format(s=fmt(spec["s"]), m=fmt(spec["m"])),
                tr("Alojamiento: {s} mm entre caras × {m} mm").format(s=fmt(spec["s"] + extra),
                                                                       m=fmt(spec["m"] + 0.3))]
    if category == "insert":
        spec = _lookup(HEAT_SET_INSERTS, size, tr("Inserto"))
        return [tr("Inserto de latón {size} para impresión 3D").format(size=size),
                tr("Exterior Ø{d} × {length} mm").format(d=fmt(spec["d_ext"]), length=fmt(spec["L"])),
                tr("Taladro: Ø{d} × {depth} mm (medidas de fabricante, compruébalas)").format(
                    d=fmt(spec["d_hole"]), depth=fmt(spec["L"] + 1.0))]
    if category == "washer":
        spec = _lookup(WASHERS_DIN_125, size, tr("Métrica"))
        return [tr("Arandela plana {size} (DIN 125 / ISO 7089)").format(size=size),
                f"Ø{fmt(spec['d1'])} / Ø{fmt(spec['d2'])} × {fmt(spec['h'])} mm"]
    if category == "bearing":
        spec = _lookup(BEARINGS_ISO, size, tr("Rodamiento"))
        tol = {"fine": 0.2, "medium": 0.35, "coarse": 0.5}[fit]
        return [tr("Rodamiento {model} (ISO 15)").format(model=size),
                f"d = {fmt(spec['d'])} · D = {fmt(spec['D'])} · B = {fmt(spec['B'])} mm",
                tr("Alojamiento: Ø{d} × {depth} mm").format(d=fmt(spec["D"] + tol), depth=fmt(spec["B"] + 0.2))]
    if category == "profile":
        section = "20×40" if size == "2040" else "20×20"
        return [tr("Perfil de aluminio {model} ({section} mm) × {length} mm").format(
                    model=size, section=section, length=fmt(length)),
                tr("Ranura recta de {slot} mm (sin el ala en T) y taladro central Ø{hole} mm para roscar M5").format(
                    slot=fmt(PROFILE_SLOT_WIDTH), hole=fmt(2 * PROFILE_CORE_HOLE_R))]
    raise ValueError(f"Categoría desconocida: {category}")
