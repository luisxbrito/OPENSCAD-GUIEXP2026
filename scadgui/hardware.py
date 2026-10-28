"""Biblioteca de componentes estándar industriales (tornillería, tuercas, rodamientos y perfiles).

Sigue las especificaciones normalizadas internacionales:
- Tornillos: ISO 4762 (DIN 912), ISO 4017 (DIN 933), ISO 10642 (DIN 7991), ISO 7380.
- Holguras de paso: ISO 273 (fina, media, gruesa).
- Tuercas y arandelas: DIN 934, DIN 985, DIN 125, e insertos térmicos de latón (tipo Ruthex/CNC Kitchen).
- Rodamientos radiales de bolas: ISO 15 / DIN 625 (608, 623, 624, 625, 626, 688, 6900).
- Perfiles de aluminio extruido: 2020 y 2040 con ranura T de 6 mm.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Optional

from .model import Node, make_node


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

# Tornillo avellanado cónico 90° ISO 10642 / DIN 7991
# d: diámetro nominal, dk: diámetro cabeza máx, k: altura cabeza cónica, s: llave hexagonal
SCREWS_ISO_10642 = {
    "M2":   {"d": 2.0, "dk": 4.0,  "k": 1.2, "s": 1.25},
    "M2.5": {"d": 2.5, "dk": 5.0,  "k": 1.5, "s": 1.5},
    "M3":   {"d": 3.0, "dk": 6.0,  "k": 1.7, "s": 2.0},
    "M4":   {"d": 4.0, "dk": 8.0,  "k": 2.3, "s": 2.5},
    "M5":   {"d": 5.0, "dk": 10.0, "k": 2.8, "s": 3.0},
    "M6":   {"d": 6.0, "dk": 12.0, "k": 3.3, "s": 4.0},
    "M8":   {"d": 8.0, "dk": 16.0, "k": 4.4, "s": 5.0},
}

# Tornillo de cabeza abombada (botón) ISO 7380
# d: diámetro nominal, dk: diámetro cabeza, k: altura cabeza, s: llave hexagonal
SCREWS_ISO_7380 = {
    "M2":   {"d": 2.0, "dk": 3.5,  "k": 1.3,  "s": 1.25},
    "M2.5": {"d": 2.5, "dk": 4.5,  "k": 1.5,  "s": 1.5},
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

# Insertos roscados de latón para inserción térmica en termoplásticos (Ruthex / CNC Kitchen)
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
    "608":  {"d": 8.0,  "D": 22.0, "B": 7.0, "name": "Rodamiento 608 (Patinete / 3D)"},
    "623":  {"d": 3.0,  "D": 10.0, "B": 4.0, "name": "Rodamiento 623"},
    "624":  {"d": 4.0,  "D": 13.0, "B": 5.0, "name": "Rodamiento 624"},
    "625":  {"d": 5.0,  "D": 16.0, "B": 5.0, "name": "Rodamiento 625"},
    "626":  {"d": 6.0,  "D": 19.0, "B": 6.0, "name": "Rodamiento 626"},
    "688":  {"d": 8.0,  "D": 16.0, "B": 5.0, "name": "Rodamiento 688"},
    "6900": {"d": 10.0, "D": 22.0, "B": 6.0, "name": "Rodamiento 6900"},
}

STANDARD_LENGTHS = [6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]


def _inscribed_hex_radius(across_flats: float) -> float:
    """Calcula el radio circunscrito R necesario para que un hexágono regular tenga ancho s entre caras."""
    return round(across_flats / math.sqrt(3.0), 3)


# --------------------------------------------------------------------------- Constructores de nodos

def create_screw_node(
    standard: str,
    size: str,
    length: float = 16.0,
    mode: str = "solid",
    fit: str = "medium",
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Crea un nodo de tornillo normalizado en modo sólido o taladro/cajeado de resta."""
    u_fn = unique_fn or (lambda s: s)
    clearances = CLEARANCE_HOLES_ISO_273.get(size, {"fine": 3.2, "medium": 3.4, "coarse": 3.6})
    d_hole = clearances.get(fit, clearances["medium"])

    if standard == "iso4762":
        spec = SCREWS_ISO_4762.get(size, SCREWS_ISO_4762["M3"])
        d, dk, k, s, t = spec["d"], spec["dk"], spec["k"], spec["s"], spec["t"]
        norm_label = f"Tornillo {size}x{int(length)} ISO4762"

        if mode == "solid":
            grp = make_node("group", u_fn(norm_label))
            # Vástago cilíndrico
            shank = make_node("cylinder", u_fn(f"Vástago {size}"))
            shank.params["h"] = length
            shank.params["r"] = round(d / 2.0, 2)
            grp.children.append(shank)

            # Cabeza cilíndrica con hexágono interior
            tr_head = make_node("translate", u_fn(f"Posición cabeza {size}"))
            tr_head.params["v"] = [0.0, 0.0, length]
            diff_head = make_node("difference", u_fn("Cabeza Allen"))
            cyl_head = make_node("cylinder", u_fn("Cuerpo cabeza"))
            cyl_head.params["h"] = k
            cyl_head.params["r"] = round(dk / 2.0, 2)
            diff_head.children.append(cyl_head)

            # Hueco hexagonal de la llave
            tr_hex = make_node("translate", u_fn("Hueco llave"))
            tr_hex.params["v"] = [0.0, 0.0, round(k - t + 0.01, 2)]
            ext_hex = make_node("linear_extrude", u_fn("Hexágono"))
            ext_hex.params["height"] = round(t + 0.1, 2)
            circ_hex = make_node("circle", u_fn("Llave"))
            circ_hex.params["r"] = _inscribed_hex_radius(s)
            circ_hex.params["$fn"] = 6
            ext_hex.children.append(circ_hex)
            tr_hex.children.append(ext_hex)
            diff_head.children.append(tr_hex)

            tr_head.children.append(diff_head)
            grp.children.append(tr_head)

            root = make_node("color", u_fn(norm_label))
            root.params["c"] = "DimGray"
            root.children.append(grp)
            return root

        else:  # mode == "hole" (Máscara negativa para taladro de paso y cajeado)
            mask_grp = make_node("group", u_fn(f"Taladro {size}x{int(length)}"))
            # Agujero de paso pasante
            pass_cyl = make_node("cylinder", u_fn("Paso pasante"))
            pass_cyl.params["h"] = round(length + 2.0, 2)
            pass_cyl.params["r"] = round(d_hole / 2.0, 2)
            tr_pass = make_node("translate")
            tr_pass.params["v"] = [0.0, 0.0, -1.0]
            tr_pass.children.append(pass_cyl)
            mask_grp.children.append(tr_pass)

            # Cajeado para la cabeza cilíndrica con holgura
            dk_tol = dk + (0.6 if fit == "medium" else 0.4 if fit == "fine" else 0.8)
            head_cyl = make_node("cylinder", u_fn("Cajeado cabeza"))
            head_cyl.params["h"] = round(k + 10.0, 2)  # Profundidad holgada hacia la superficie
            head_cyl.params["r"] = round(dk_tol / 2.0, 2)
            tr_cajeado = make_node("translate")
            tr_cajeado.params["v"] = [0.0, 0.0, length]
            tr_cajeado.children.append(head_cyl)
            mask_grp.children.append(tr_cajeado)
            return mask_grp

    elif standard == "din933":
        spec = SCREWS_DIN_933.get(size, SCREWS_DIN_933["M3"])
        d, s, k = spec["d"], spec["s"], spec["k"]
        norm_label = f"Tornillo {size}x{int(length)} DIN933"

        if mode == "solid":
            grp = make_node("group", u_fn(norm_label))
            shank = make_node("cylinder", u_fn(f"Vástago {size}"))
            shank.params["h"] = length
            shank.params["r"] = round(d / 2.0, 2)
            grp.children.append(shank)

            tr_head = make_node("translate", u_fn(f"Posición cabeza {size}"))
            tr_head.params["v"] = [0.0, 0.0, length]
            ext_head = make_node("linear_extrude", u_fn("Cabeza hexagonal"))
            ext_head.params["height"] = k
            c_hex = make_node("circle", u_fn("Hexágono"))
            c_hex.params["r"] = _inscribed_hex_radius(s)
            c_hex.params["$fn"] = 6
            ext_head.children.append(c_hex)
            tr_head.children.append(ext_head)
            grp.children.append(tr_head)

            root = make_node("color", u_fn(norm_label))
            root.params["c"] = "LightSlateGray"
            root.children.append(grp)
            return root
        else:
            mask_grp = make_node("group", u_fn(f"Taladro {size}x{int(length)} DIN933"))
            pass_cyl = make_node("cylinder", u_fn("Paso pasante"))
            pass_cyl.params["h"] = round(length + 2.0, 2)
            pass_cyl.params["r"] = round(d_hole / 2.0, 2)
            tr_pass = make_node("translate")
            tr_pass.params["v"] = [0.0, 0.0, -1.0]
            tr_pass.children.append(pass_cyl)
            mask_grp.children.append(tr_pass)

            s_tol = s + (0.4 if fit == "medium" else 0.2 if fit == "fine" else 0.6)
            tr_head = make_node("translate")
            tr_head.params["v"] = [0.0, 0.0, length]
            ext_head = make_node("linear_extrude", u_fn("Cajeado hexagonal"))
            ext_head.params["height"] = round(k + 10.0, 2)
            c_hex = make_node("circle")
            c_hex.params["r"] = _inscribed_hex_radius(s_tol)
            c_hex.params["$fn"] = 6
            ext_head.children.append(c_hex)
            tr_head.children.append(ext_head)
            mask_grp.children.append(tr_head)
            return mask_grp

    elif standard == "iso10642":
        spec = SCREWS_ISO_10642.get(size, SCREWS_ISO_10642["M3"])
        d, dk, k, s = spec["d"], spec["dk"], spec["k"], spec["s"]
        norm_label = f"Tornillo Avellanado {size}x{int(length)} ISO10642"

        if mode == "solid":
            grp = make_node("group", u_fn(norm_label))
            shank = make_node("cylinder", u_fn(f"Vástago {size}"))
            shank.params["h"] = round(length - k, 2)
            shank.params["r"] = round(d / 2.0, 2)
            grp.children.append(shank)

            tr_head = make_node("translate", u_fn("Cabeza cónica 90°"))
            tr_head.params["v"] = [0.0, 0.0, round(length - k, 2)]
            diff_head = make_node("difference", u_fn("Cono con Allen"))
            cone = make_node("cylinder", u_fn("Cono 90°"))
            cone.params["h"] = k
            cone.params["r1"] = round(d / 2.0, 2)
            cone.params["r2"] = round(dk / 2.0, 2)
            diff_head.children.append(cone)

            tr_hex = make_node("translate")
            tr_hex.params["v"] = [0.0, 0.0, round(k - 1.2, 2)]
            ext_hex = make_node("linear_extrude")
            ext_hex.params["height"] = 1.3
            circ_hex = make_node("circle")
            circ_hex.params["r"] = _inscribed_hex_radius(s)
            circ_hex.params["$fn"] = 6
            ext_hex.children.append(circ_hex)
            tr_hex.children.append(ext_hex)
            diff_head.children.append(tr_hex)

            tr_head.children.append(diff_head)
            grp.children.append(tr_head)

            root = make_node("color", u_fn(norm_label))
            root.params["c"] = "DarkSlateGray"
            root.children.append(grp)
            return root
        else:
            mask_grp = make_node("group", u_fn(f"Taladro avellanado {size}"))
            pass_cyl = make_node("cylinder", u_fn("Paso pasante"))
            pass_cyl.params["h"] = round(length + 2.0, 2)
            pass_cyl.params["r"] = round(d_hole / 2.0, 2)
            tr_pass = make_node("translate")
            tr_pass.params["v"] = [0.0, 0.0, -1.0]
            tr_pass.children.append(pass_cyl)
            mask_grp.children.append(tr_pass)

            tr_cone = make_node("translate")
            tr_cone.params["v"] = [0.0, 0.0, round(length - k, 2)]
            cone = make_node("cylinder", u_fn("Avellanado cónico"))
            cone.params["h"] = round(k + 0.1, 2)
            cone.params["r1"] = round(d_hole / 2.0, 2)
            cone.params["r2"] = round((dk + 0.5) / 2.0, 2)
            tr_cone.children.append(cone)
            mask_grp.children.append(tr_cone)
            return mask_grp

    else:  # iso7380 botón por defecto
        spec = SCREWS_ISO_7380.get(size, SCREWS_ISO_7380["M3"])
        d, dk, k = spec["d"], spec["dk"], spec["k"]
        norm_label = f"Tornillo Botón {size}x{int(length)} ISO7380"
        grp = make_node("group", u_fn(norm_label))
        shank = make_node("cylinder", u_fn("Vástago"))
        shank.params["h"] = length
        shank.params["r"] = round(d / 2.0, 2)
        grp.children.append(shank)

        tr_head = make_node("translate")
        tr_head.params["v"] = [0.0, 0.0, length]
        head_cyl = make_node("cylinder", u_fn("Cabeza botón"))
        head_cyl.params["h"] = k
        head_cyl.params["r1"] = round(dk / 2.0, 2)
        head_cyl.params["r2"] = round(dk * 0.75 / 2.0, 2)
        tr_head.children.append(head_cyl)
        grp.children.append(tr_head)
        return grp


def create_nut_node(
    standard: str,
    size: str,
    mode: str = "solid",
    fit: str = "medium",
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Crea una tuerca hexagonal normalizada (DIN 934 o DIN 985) o su cajeado de embutir."""
    u_fn = unique_fn or (lambda s: s)
    spec_table = NUTS_DIN_985 if standard == "din985" else NUTS_DIN_934
    spec = spec_table.get(size, spec_table["M3"])
    d, s, m = spec["d"], spec["s"], spec["m"]
    norm_name = f"Tuerca {size} {'DIN985' if standard == 'din985' else 'DIN934'}"

    if mode == "solid":
        root = make_node("color", u_fn(norm_name))
        root.params["c"] = "LightGray"
        diff = make_node("difference", u_fn(norm_name))
        ext = make_node("linear_extrude", u_fn("Prisma hexagonal"))
        ext.params["height"] = m
        c = make_node("circle", u_fn("Hexágono"))
        c.params["r"] = _inscribed_hex_radius(s)
        c.params["$fn"] = 6
        ext.children.append(c)
        diff.children.append(ext)

        hole = make_node("cylinder", u_fn("Roscado interior"))
        hole.params["h"] = round(m + 0.4, 2)
        hole.params["r"] = round(d / 2.0, 2)
        tr_hole = make_node("translate")
        tr_hole.params["v"] = [0.0, 0.0, -0.2]
        tr_hole.children.append(hole)
        diff.children.append(tr_hole)
        root.children.append(diff)
        return root
    else:  # Cajeado negativo para embutir la tuerca en la pared de una pieza
        s_tol = s + (0.4 if fit == "medium" else 0.25 if fit == "fine" else 0.6)
        m_tol = round(m + 0.3, 2)
        grp = make_node("group", u_fn(f"Alojamiento tuerca {size}"))
        ext = make_node("linear_extrude", u_fn("Cajeado tuerca"))
        ext.params["height"] = m_tol
        c = make_node("circle")
        c.params["r"] = _inscribed_hex_radius(s_tol)
        c.params["$fn"] = 6
        ext.children.append(c)
        grp.children.append(ext)
        return grp


def create_heat_set_node(
    size: str,
    mode: str = "solid",
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Crea un inserto roscado de latón para impresión 3D o su taladro de inserción."""
    u_fn = unique_fn or (lambda s: s)
    spec = HEAT_SET_INSERTS.get(size, HEAT_SET_INSERTS["M3"])
    d, d_ext, length, d_hole = spec["d"], spec["d_ext"], spec["L"], spec["d_hole"]

    if mode == "solid":
        root = make_node("color", u_fn(f"Inserto térmico {size}"))
        root.params["c"] = "Gold"
        diff = make_node("difference", u_fn(f"Inserto {size}x{length}"))
        body = make_node("cylinder", u_fn("Cuerpo moleteado"))
        body.params["h"] = length
        body.params["r"] = round(d_ext / 2.0, 2)
        diff.children.append(body)

        hole = make_node("cylinder", u_fn("Roscado interior"))
        hole.params["h"] = round(length + 0.4, 2)
        hole.params["r"] = round(d / 2.0, 2)
        tr_hole = make_node("translate")
        tr_hole.params["v"] = [0.0, 0.0, -0.2]
        tr_hole.children.append(hole)
        diff.children.append(tr_hole)
        root.children.append(diff)
        return root
    else:  # Taladro ciego recomendado para soldador térmico
        grp = make_node("group", u_fn(f"Taladro inserto {size}"))
        cyl = make_node("cylinder", u_fn("Taladro térmico"))
        cyl.params["h"] = round(length + 1.0, 2)  # 1 mm extra de profundidad para rebabas
        cyl.params["r"] = round(d_hole / 2.0, 2)
        grp.children.append(cyl)
        # Pequeño chaflán superior de entrada
        ch = make_node("translate")
        ch.params["v"] = [0.0, 0.0, length]
        cone = make_node("cylinder", u_fn("Guía de entrada"))
        cone.params["h"] = 0.8
        cone.params["r1"] = round(d_hole / 2.0, 2)
        cone.params["r2"] = round((d_hole + 0.8) / 2.0, 2)
        ch.children.append(cone)
        grp.children.append(ch)
        return grp


def create_washer_node(
    size: str,
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Crea una arandela plana normalizada DIN 125 / ISO 7089."""
    u_fn = unique_fn or (lambda s: s)
    spec = WASHERS_DIN_125.get(size, WASHERS_DIN_125["M3"])
    d1, d2, h = spec["d1"], spec["d2"], spec["h"]

    root = make_node("color", u_fn(f"Arandela {size} DIN125"))
    root.params["c"] = "Silver"
    diff = make_node("difference", u_fn("Arandela plana"))
    ext = make_node("cylinder", u_fn("Exterior"))
    ext.params["h"] = h
    ext.params["r"] = round(d2 / 2.0, 2)
    diff.children.append(ext)

    hole = make_node("cylinder", u_fn("Paso interior"))
    hole.params["h"] = round(h + 0.2, 2)
    hole.params["r"] = round(d1 / 2.0, 2)
    tr_hole = make_node("translate")
    tr_hole.params["v"] = [0.0, 0.0, -0.1]
    tr_hole.children.append(hole)
    diff.children.append(tr_hole)
    root.children.append(diff)
    return root


def create_bearing_node(
    model: str = "608",
    mode: str = "solid",
    fit: str = "medium",
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Crea un rodamiento rígido de bolas normalizado ISO 15 / DIN 625 o su alojamiento."""
    u_fn = unique_fn or (lambda s: s)
    spec = BEARINGS_ISO.get(model, BEARINGS_ISO["608"])
    d, d_ext, b = spec["d"], spec["D"], spec["B"]

    if mode == "solid":
        root = make_node("color", u_fn(f"Rodamiento {model}"))
        root.params["c"] = "Silver"
        diff = make_node("difference", u_fn(spec["name"]))
        outer = make_node("cylinder", u_fn("Pista exterior"))
        outer.params["h"] = b
        outer.params["r"] = round(d_ext / 2.0, 2)
        diff.children.append(outer)

        inner = make_node("cylinder", u_fn("Eje interior"))
        inner.params["h"] = round(b + 0.4, 2)
        inner.params["r"] = round(d / 2.0, 2)
        tr = make_node("translate")
        tr.params["v"] = [0.0, 0.0, -0.2]
        tr.children.append(inner)
        diff.children.append(tr)
        root.children.append(diff)
        return root
    else:  # Alojamiento para rodamiento
        tol = 0.2 if fit == "fine" else 0.35 if fit == "medium" else 0.5
        grp = make_node("group", u_fn(f"Alojamiento rodamiento {model}"))
        cyl = make_node("cylinder", u_fn("Cajeado rodamiento"))
        cyl.params["h"] = round(b + 0.2, 2)
        cyl.params["r"] = round((d_ext + tol) / 2.0, 2)
        grp.children.append(cyl)
        # Taladro pasante central para el eje libre
        shaft = make_node("cylinder", u_fn("Paso libre eje"))
        shaft.params["h"] = round(b + 20.0, 2)
        shaft.params["r"] = round((d + 1.0) / 2.0, 2)
        tr_shaft = make_node("translate")
        tr_shaft.params["v"] = [0.0, 0.0, -10.0]
        tr_shaft.children.append(shaft)
        grp.children.append(tr_shaft)
        return grp


def create_profile_node(
    model: str = "2020",
    length: float = 100.0,
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Crea un perfil de aluminio estructural extruido (2020 o 2040) con ranuras T estándar de 6 mm."""
    u_fn = unique_fn or (lambda s: s)
    w = 20.0
    h = 40.0 if model == "2040" else 20.0

    root = make_node("color", u_fn(f"Perfil {model}x{int(length)}mm"))
    root.params["c"] = "LightGray"

    diff = make_node("difference", u_fn("Perfil de aluminio"))
    box = make_node("cube", u_fn("Cuerpo exterior"))
    box.params["size"] = [w, h, length]
    box.params["center"] = True
    diff.children.append(box)

    # Agujero central para roscar M5 (radio 2.1 mm)
    bore1 = make_node("cylinder", u_fn("Taladro central"))
    bore1.params["h"] = round(length + 2.0, 2)
    bore1.params["r"] = 2.1
    bore1.params["center"] = True
    diff.children.append(bore1)

    if model == "2040":
        # Segundo taladro central a 20 mm
        tr_b2 = make_node("translate")
        tr_b2.params["v"] = [0.0, 10.0, 0.0]
        b2 = make_node("cylinder", u_fn("Taladro 2"))
        b2.params["h"] = round(length + 2.0, 2)
        b2.params["r"] = 2.1
        b2.params["center"] = True
        tr_b2.children.append(b2)
        diff.children.append(tr_b2)

    root.children.append(diff)
    return root
