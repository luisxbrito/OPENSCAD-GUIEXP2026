"""Biblioteca de componentes estándar industriales (tornillería, tuercas, rodamientos y perfiles).

Sigue las especificaciones normalizadas internacionales:
- Tornillos: ISO 4762 (DIN 912), ISO 4017 (DIN 933), DIN 7991 (avellanado) e ISO 7380 (botón).
- Holguras de paso: ISO 273 (fina, media, gruesa).
- Tuercas y arandelas: DIN 934, DIN 985, DIN 125, e insertos térmicos de latón (tipo Ruthex/CNC Kitchen).
- Rodamientos radiales de bolas: ISO 15 / DIN 625 (608, 623, 624, 625, 626, 688, 6900).
- Perfiles de aluminio extruido 2020 y 2040 (ranura de 6 mm simplificada, sin el ala interior en T).
- Ranuras para anillos de retención métricos (ANSI B27.7, series 3AM1 y 3BM1) y para o-ring (AS568).

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
# Ranuras para anillos de retención métricos ANSI B27.7-1977 (Machinery's Handbook 27, tablas 1 y 2,
# pp. 1685-1686). Por Ø del eje o del agujero: D, Ø libre del anillo; t, su grueso; G, Ø de la ranura;
# W, su ancho; d, su profundidad (de referencia: manda G); Z, margen mínimo hasta el borde.
# Serie 3AM1, exterior (para eje)
RETAINING_RINGS_3AM1 = {
    "4": {"D": 3.6, "t": 0.25, "G": 3.8, "W": 0.32, "d": 0.1, "Z": 0.3},
    "5": {"D": 4.55, "t": 0.4, "G": 4.75, "W": 0.5, "d": 0.13, "Z": 0.4},
    "6": {"D": 5.45, "t": 0.4, "G": 5.7, "W": 0.5, "d": 0.15, "Z": 0.5},
    "7": {"D": 6.35, "t": 0.6, "G": 6.6, "W": 0.7, "d": 0.2, "Z": 0.6},
    "8": {"D": 7.15, "t": 0.6, "G": 7.5, "W": 0.7, "d": 0.25, "Z": 0.8},
    "9": {"D": 8.15, "t": 0.6, "G": 8.45, "W": 0.7, "d": 0.28, "Z": 0.8},
    "10": {"D": 9, "t": 0.6, "G": 9.4, "W": 0.7, "d": 0.3, "Z": 0.9},
    "11": {"D": 10, "t": 0.6, "G": 10.35, "W": 0.7, "d": 0.33, "Z": 1},
    "12": {"D": 10.85, "t": 0.6, "G": 11.35, "W": 0.7, "d": 0.33, "Z": 1},
    "13": {"D": 11.9, "t": 0.9, "G": 12.3, "W": 1, "d": 0.35, "Z": 1},
    "14": {"D": 12.9, "t": 0.9, "G": 13.25, "W": 1, "d": 0.38, "Z": 1.2},
    "15": {"D": 13.8, "t": 0.9, "G": 14.15, "W": 1, "d": 0.43, "Z": 1.3},
    "16": {"D": 14.7, "t": 0.9, "G": 15.1, "W": 1, "d": 0.45, "Z": 1.4},
    "17": {"D": 15.75, "t": 0.9, "G": 16.1, "W": 1, "d": 0.45, "Z": 1.4},
    "18": {"D": 16.65, "t": 1.1, "G": 17, "W": 1.2, "d": 0.5, "Z": 1.5},
    "19": {"D": 17.6, "t": 1.1, "G": 17.95, "W": 1.2, "d": 0.53, "Z": 1.6},
    "20": {"D": 18.35, "t": 1.1, "G": 18.85, "W": 1.2, "d": 0.58, "Z": 1.7},
    "21": {"D": 19.4, "t": 1.1, "G": 19.8, "W": 1.2, "d": 0.6, "Z": 1.8},
    "22": {"D": 20.3, "t": 1.1, "G": 20.7, "W": 1.2, "d": 0.65, "Z": 1.9},
    "23": {"D": 21.25, "t": 1.1, "G": 21.65, "W": 1.2, "d": 0.67, "Z": 2},
    "24": {"D": 22.2, "t": 1.1, "G": 22.6, "W": 1.2, "d": 0.7, "Z": 2.1},
    "25": {"D": 23.1, "t": 1.1, "G": 23.5, "W": 1.2, "d": 0.75, "Z": 2.3},
    "26": {"D": 24.05, "t": 1.1, "G": 24.5, "W": 1.2, "d": 0.75, "Z": 2.3},
    "27": {"D": 24.95, "t": 1.3, "G": 25.45, "W": 1.4, "d": 0.78, "Z": 2.3},
    "28": {"D": 25.8, "t": 1.3, "G": 26.4, "W": 1.4, "d": 0.8, "Z": 2.4},
    "30": {"D": 27.9, "t": 1.3, "G": 28.35, "W": 1.4, "d": 0.83, "Z": 2.5},
    "32": {"D": 29.6, "t": 1.3, "G": 30.2, "W": 1.4, "d": 0.9, "Z": 2.7},
    "34": {"D": 31.4, "t": 1.3, "G": 32, "W": 1.4, "d": 1, "Z": 3},
    "35": {"D": 32.3, "t": 1.3, "G": 32.9, "W": 1.4, "d": 1.05, "Z": 3.1},
    "36": {"D": 33.25, "t": 1.3, "G": 33.85, "W": 1.4, "d": 1.06, "Z": 3.2},
    "38": {"D": 35.2, "t": 1.3, "G": 35.8, "W": 1.4, "d": 1.1, "Z": 3.3},
    "40": {"D": 36.75, "t": 1.6, "G": 37.7, "W": 1.75, "d": 1.15, "Z": 3.4},
    "42": {"D": 38.8, "t": 1.6, "G": 39.6, "W": 1.75, "d": 1.2, "Z": 3.6},
    "43": {"D": 39.65, "t": 1.6, "G": 40.5, "W": 1.75, "d": 1.25, "Z": 3.8},
    "45": {"D": 41.6, "t": 1.6, "G": 42.4, "W": 1.75, "d": 1.3, "Z": 3.9},
    "46": {"D": 42.55, "t": 1.6, "G": 43.3, "W": 1.75, "d": 1.35, "Z": 4},
    "48": {"D": 44.4, "t": 1.6, "G": 45.2, "W": 1.75, "d": 1.4, "Z": 4.2},
    "50": {"D": 46.2, "t": 1.6, "G": 47.2, "W": 1.75, "d": 1.4, "Z": 4.2},
    "52": {"D": 48.4, "t": 2, "G": 49.1, "W": 2.15, "d": 1.45, "Z": 4.3},
    "54": {"D": 49.9, "t": 2, "G": 51, "W": 2.15, "d": 1.5, "Z": 4.5},
    "55": {"D": 50.6, "t": 2, "G": 51.8, "W": 2.15, "d": 1.6, "Z": 4.8},
    "57": {"D": 52.9, "t": 2, "G": 53.8, "W": 2.15, "d": 1.6, "Z": 4.8},
    "58": {"D": 53.6, "t": 2, "G": 54.7, "W": 2.15, "d": 1.65, "Z": 4.9},
    "60": {"D": 55.8, "t": 2, "G": 56.7, "W": 2.15, "d": 1.65, "Z": 4.9},
    "62": {"D": 57.3, "t": 2, "G": 58.6, "W": 2.15, "d": 1.7, "Z": 5.1},
    "65": {"D": 60.4, "t": 2, "G": 61.6, "W": 2.15, "d": 1.7, "Z": 5.1},
    "68": {"D": 63.1, "t": 2, "G": 64.5, "W": 2.15, "d": 1.75, "Z": 5.3},
    "70": {"D": 64.6, "t": 2.4, "G": 66.4, "W": 2.55, "d": 1.8, "Z": 5.4},
    "72": {"D": 66.6, "t": 2.4, "G": 68.3, "W": 2.55, "d": 1.85, "Z": 5.5},
    "75": {"D": 69, "t": 2.4, "G": 71.2, "W": 2.55, "d": 1.9, "Z": 5.7},
    "78": {"D": 72, "t": 2.4, "G": 74, "W": 2.55, "d": 2, "Z": 6},
    "80": {"D": 74.2, "t": 2.4, "G": 75.9, "W": 2.55, "d": 2.05, "Z": 6.1},
    "82": {"D": 76.4, "t": 2.4, "G": 77.8, "W": 2.55, "d": 2.1, "Z": 6.3},
    "85": {"D": 78.6, "t": 2.4, "G": 80.6, "W": 2.55, "d": 2.2, "Z": 6.6},
    "88": {"D": 81.4, "t": 2.8, "G": 83.5, "W": 2.95, "d": 2.25, "Z": 6.7},
    "90": {"D": 83.2, "t": 2.8, "G": 85.4, "W": 2.95, "d": 2.3, "Z": 6.9},
    "95": {"D": 88.1, "t": 2.8, "G": 90.2, "W": 2.95, "d": 2.4, "Z": 7.2},
    "100": {"D": 92.5, "t": 2.8, "G": 95, "W": 2.95, "d": 2.5, "Z": 7.5},
}

# Serie 3BM1, interior (para agujero)
RETAINING_RINGS_3BM1 = {
    "8": {"D": 8.8, "t": 0.4, "G": 8.4, "W": 0.5, "d": 0.2, "Z": 0.6},
    "9": {"D": 10, "t": 0.6, "G": 9.45, "W": 0.7, "d": 0.23, "Z": 0.7},
    "10": {"D": 11.1, "t": 0.6, "G": 10.5, "W": 0.7, "d": 0.25, "Z": 0.8},
    "11": {"D": 12.2, "t": 0.6, "G": 11.6, "W": 0.7, "d": 0.3, "Z": 0.9},
    "12": {"D": 13.3, "t": 0.6, "G": 12.65, "W": 0.7, "d": 0.33, "Z": 1},
    "13": {"D": 14.25, "t": 0.9, "G": 13.7, "W": 1, "d": 0.35, "Z": 1.1},
    "14": {"D": 15.45, "t": 0.9, "G": 14.8, "W": 1, "d": 0.4, "Z": 1.2},
    "15": {"D": 16.6, "t": 0.9, "G": 15.85, "W": 1, "d": 0.43, "Z": 1.3},
    "16": {"D": 17.7, "t": 0.9, "G": 16.9, "W": 1, "d": 0.45, "Z": 1.4},
    "17": {"D": 18.9, "t": 0.9, "G": 18, "W": 1, "d": 0.5, "Z": 1.5},
    "18": {"D": 20.05, "t": 0.9, "G": 19.05, "W": 1, "d": 0.53, "Z": 1.6},
    "19": {"D": 21.1, "t": 0.9, "G": 20.1, "W": 1, "d": 0.55, "Z": 1.7},
    "20": {"D": 22.25, "t": 0.9, "G": 21.15, "W": 1, "d": 0.57, "Z": 1.7},
    "21": {"D": 23.3, "t": 0.9, "G": 22.2, "W": 1, "d": 0.6, "Z": 1.8},
    "22": {"D": 24.4, "t": 1.1, "G": 23.3, "W": 1.2, "d": 0.65, "Z": 1.9},
    "23": {"D": 25.45, "t": 1.1, "G": 24.35, "W": 1.2, "d": 0.67, "Z": 2},
    "24": {"D": 26.55, "t": 1.1, "G": 25.4, "W": 1.2, "d": 0.7, "Z": 2.1},
    "25": {"D": 27.75, "t": 1.1, "G": 26.6, "W": 1.2, "d": 0.8, "Z": 2.4},
    "26": {"D": 28.85, "t": 1.1, "G": 27.7, "W": 1.2, "d": 0.85, "Z": 2.6},
    "27": {"D": 29.95, "t": 1.3, "G": 28.8, "W": 1.4, "d": 0.9, "Z": 2.7},
    "28": {"D": 31.1, "t": 1.3, "G": 29.8, "W": 1.4, "d": 0.9, "Z": 2.7},
    "30": {"D": 33.4, "t": 1.3, "G": 31.9, "W": 1.4, "d": 0.95, "Z": 2.9},
    "32": {"D": 35.35, "t": 1.3, "G": 33.9, "W": 1.4, "d": 0.95, "Z": 2.9},
    "34": {"D": 37.75, "t": 1.3, "G": 36.1, "W": 1.4, "d": 1.05, "Z": 3.2},
    "35": {"D": 38.75, "t": 1.3, "G": 37.2, "W": 1.4, "d": 1.1, "Z": 3.3},
    "36": {"D": 40, "t": 1.3, "G": 38.3, "W": 1.4, "d": 1.15, "Z": 3.5},
    "37": {"D": 41.05, "t": 1.3, "G": 39.3, "W": 1.4, "d": 1.15, "Z": 3.5},
    "38": {"D": 42.15, "t": 1.3, "G": 40.4, "W": 1.4, "d": 1.2, "Z": 3.6},
    "40": {"D": 44.25, "t": 1.6, "G": 42.4, "W": 1.75, "d": 1.2, "Z": 3.6},
    "42": {"D": 46.6, "t": 1.6, "G": 44.5, "W": 1.75, "d": 1.25, "Z": 3.7},
    "45": {"D": 49.95, "t": 1.6, "G": 47.6, "W": 1.75, "d": 1.3, "Z": 3.9},
    "46": {"D": 51.05, "t": 1.6, "G": 48.7, "W": 1.75, "d": 1.35, "Z": 4},
    "47": {"D": 52.15, "t": 1.6, "G": 49.8, "W": 1.75, "d": 1.4, "Z": 4.2},
    "48": {"D": 53.3, "t": 1.6, "G": 50.9, "W": 1.75, "d": 1.45, "Z": 4.3},
    "50": {"D": 55.35, "t": 1.6, "G": 53.1, "W": 1.75, "d": 1.55, "Z": 4.6},
    "52": {"D": 57.9, "t": 2, "G": 55.3, "W": 2.15, "d": 1.65, "Z": 5},
    "55": {"D": 61.1, "t": 2, "G": 58.4, "W": 2.15, "d": 1.7, "Z": 5.1},
    "57": {"D": 63.25, "t": 2, "G": 60.5, "W": 2.15, "d": 1.75, "Z": 5.3},
    "58": {"D": 64.4, "t": 2, "G": 61.6, "W": 2.15, "d": 1.8, "Z": 5.4},
    "60": {"D": 66.8, "t": 2, "G": 63.8, "W": 2.15, "d": 1.9, "Z": 5.7},
    "62": {"D": 68.6, "t": 2, "G": 65.8, "W": 2.15, "d": 1.9, "Z": 5.7},
    "63": {"D": 69.9, "t": 2, "G": 66.9, "W": 2.15, "d": 1.95, "Z": 5.9},
    "65": {"D": 72.2, "t": 2.4, "G": 69, "W": 2.55, "d": 2, "Z": 6},
    "68": {"D": 75.7, "t": 2.4, "G": 72.2, "W": 2.55, "d": 2.1, "Z": 6.3},
    "70": {"D": 77.5, "t": 2.4, "G": 74.4, "W": 2.55, "d": 2.2, "Z": 6.6},
    "72": {"D": 79.6, "t": 2.4, "G": 76.5, "W": 2.55, "d": 2.25, "Z": 6.7},
    "75": {"D": 83.3, "t": 2.4, "G": 79.7, "W": 2.55, "d": 2.35, "Z": 7.1},
    "78": {"D": 86.8, "t": 2.8, "G": 82.8, "W": 2.95, "d": 2.4, "Z": 7.2},
    "80": {"D": 89.1, "t": 2.8, "G": 85, "W": 2.95, "d": 2.5, "Z": 7.5},
    "82": {"D": 91.1, "t": 2.8, "G": 87.2, "W": 2.95, "d": 2.6, "Z": 7.8},
    "85": {"D": 94.4, "t": 2.8, "G": 90.4, "W": 2.95, "d": 2.7, "Z": 8.1},
    "88": {"D": 97.9, "t": 2.8, "G": 93.6, "W": 2.95, "d": 2.8, "Z": 8.4},
    "90": {"D": 100, "t": 2.8, "G": 95.7, "W": 2.95, "d": 2.85, "Z": 8.6},
    "92": {"D": 102.2, "t": 2.8, "G": 97.8, "W": 2.95, "d": 2.9, "Z": 8.7},
    "95": {"D": 105.6, "t": 2.8, "G": 101, "W": 2.95, "d": 3, "Z": 9},
    "98": {"D": 109, "t": 2.8, "G": 104.2, "W": 2.95, "d": 3.1, "Z": 9.3},
    "100": {"D": 110.7, "t": 2.8, "G": 106.3, "W": 2.95, "d": 3.15, "Z": 9.5},
    "102": {"D": 112.4, "t": 2.8, "G": 108.4, "W": 2.95, "d": 3.2, "Z": 9.6},
    "105": {"D": 115.8, "t": 2.8, "G": 111.5, "W": 2.95, "d": 3.25, "Z": 9.8},
    "108": {"D": 119.2, "t": 2.8, "G": 114.6, "W": 2.95, "d": 3.3, "Z": 9.9},
    "110": {"D": 120.8, "t": 2.8, "G": 116.7, "W": 2.95, "d": 3.35, "Z": 10.1},
    "115": {"D": 126, "t": 2.8, "G": 121.9, "W": 2.95, "d": 3.45, "Z": 10.4},
    "120": {"D": 132.4, "t": 2.8, "G": 127, "W": 2.95, "d": 3.5, "Z": 10.5},
    "125": {"D": 137.1, "t": 2.8, "G": 132.1, "W": 2.95, "d": 3.55, "Z": 10.7},
    "130": {"D": 142.5, "t": 2.8, "G": 137.2, "W": 2.95, "d": 3.6, "Z": 10.8},
    "135": {"D": 148.5, "t": 3.2, "G": 142.3, "W": 3.4, "d": 3.65, "Z": 11},
    "140": {"D": 154.1, "t": 3.2, "G": 147.4, "W": 3.4, "d": 3.7, "Z": 11.1},
    "145": {"D": 159.5, "t": 3.2, "G": 152.5, "W": 3.4, "d": 3.75, "Z": 11.3},
    "150": {"D": 164.5, "t": 3.2, "G": 157.6, "W": 3.4, "d": 3.8, "Z": 11.4},
    "155": {"D": 168.8, "t": 3.2, "G": 162.7, "W": 3.4, "d": 3.85, "Z": 11.6},
    "160": {"D": 175.1, "t": 4, "G": 167.8, "W": 4.25, "d": 3.9, "Z": 11.7},
    "165": {"D": 180.3, "t": 4, "G": 172.9, "W": 4.25, "d": 3.95, "Z": 11.9},
    "170": {"D": 185.6, "t": 4, "G": 178, "W": 4.25, "d": 4, "Z": 12},
    "175": {"D": 191.3, "t": 4, "G": 183.2, "W": 4.25, "d": 4.1, "Z": 12.3},
    "180": {"D": 196.6, "t": 4, "G": 188.4, "W": 4.25, "d": 4.2, "Z": 12.6},
    "185": {"D": 202.7, "t": 4.8, "G": 193.6, "W": 5.1, "d": 4.3, "Z": 12.9},
    "190": {"D": 207.7, "t": 4.8, "G": 198.8, "W": 5.1, "d": 4.4, "Z": 13.2},
    "200": {"D": 217.8, "t": 4.8, "G": 209, "W": 5.1, "d": 4.5, "Z": 13.5},
    "210": {"D": 230.3, "t": 4.8, "G": 219.4, "W": 5.1, "d": 4.7, "Z": 14.1},
    "220": {"D": 240.5, "t": 4.8, "G": 230, "W": 5.1, "d": 5, "Z": 15},
    "230": {"D": 251.4, "t": 4.8, "G": 240.6, "W": 5.1, "d": 5.3, "Z": 15.9},
    "240": {"D": 262.3, "t": 4.8, "G": 251, "W": 5.1, "d": 5.5, "Z": 16.5},
    "250": {"D": 273.3, "t": 4.8, "G": 261.4, "W": 5.1, "d": 5.7, "Z": 17.1},
}

RING_TABLES = {"3am1": RETAINING_RINGS_3AM1, "3bm1": RETAINING_RINGS_3BM1}

# Ranuras para o-ring (Machinery's Handbook 27, «O-Rings», tablas 1 y 2, pp. 2503-2505), en pulgadas y
# por grueso de la sección AS568. w: grueso; static y moving: profundidad del alojamiento (fondo de la
# ranura hasta la superficie contra la que sella), como (mín, máx); width: ancho de la ranura sin
# anillos de apoyo. La clave es el grueso en mm con que se venden.
ORING_GROOVES_INCH = {
    "1.78": {"w": 0.070, "static": (0.050, 0.052), "moving": (0.055, 0.057), "width": 0.094},
    "2.62": {"w": 0.103, "static": (0.081, 0.083), "moving": (0.088, 0.090), "width": 0.141},
    "3.53": {"w": 0.139, "static": (0.111, 0.113), "moving": (0.121, 0.123), "width": 0.188},
    "5.33": {"w": 0.210, "static": (0.170, 0.173), "moving": (0.185, 0.188), "width": 0.281},
    "6.99": {"w": 0.275, "static": (0.226, 0.229), "moving": (0.237, 0.240), "width": 0.375},
}

GROOVE_FN = 96     # las máscaras llevan su resolución: un Ø de ranura no puede depender del ajuste global

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
    if category == "ring_groove":
        return list(RING_TABLES[standard])
    if category == "oring_groove":
        return list(ORING_GROOVES_INCH)
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


def _ring_mask(name: str, outer_d: float, inner_d: float, h: float, z: float, u_fn) -> Node:
    """Máscara de resta en forma de corona, de Ø outer_d a Ø inner_d, entre z y z + h."""
    outer = _cylinder(tr("Exterior"), h, outer_d / 2.0, u_fn)
    inner = _cylinder(tr("Paso interior"), h + 0.2, inner_d / 2.0, u_fn)
    outer.params["$fn"] = inner.params["$fn"] = GROOVE_FN
    mask = make_node("difference", u_fn(name))
    mask.children += [outer, _at(-0.1, inner)]
    return _at(z, mask) if z else mask


def create_ring_groove_node(
    standard: str = "3am1",
    size: str = "20",
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Máscara de la ranura de un anillo de retención: se resta del eje o del agujero. Empieza en z = 0
    y sobresale 1 mm de la superficie para que la resta quede limpia."""
    u_fn = unique_fn or (lambda s: s)
    spec = _lookup(RING_TABLES[standard], size, tr("Diámetro"))
    s, g, w = float(size), spec["G"], spec["W"]
    name = tr("Ranura anillo {ref}-{size}").format(ref=standard.upper(), size=size)
    if standard == "3am1":
        return _ring_mask(name, s + 2.0, g, w, 0.0, u_fn)
    return _ring_mask(name, g, s - 2.0, w, 0.0, u_fn)


def oring_groove(size: str, seal: str = "static") -> dict:
    """Medidas de la ranura en mm: grueso del anillo, profundidad del alojamiento (la mitad de su
    intervalo en la tabla), ancho de la ranura y cuánto se aplasta el anillo, en %."""
    spec = _lookup(ORING_GROOVES_INCH, size, tr("Sección"))
    low, high = spec[seal]
    gland = (low + high) / 2
    return {"w": round(spec["w"] * 25.4, 3), "gland": round(gland * 25.4, 3),
            "width": round(spec["width"] * 25.4, 3), "squeeze": round((1 - gland / spec["w"]) * 100)}


def _oring_diameters(standard: str, size: str, diameter: float, seal: str) -> tuple[dict, float, float]:
    """(medidas, Ø exterior e interior de la ranura). shaft: ranura en un eje que entra en un agujero
    de ese Ø; bore: en un agujero por el que pasa un eje de ese Ø; face: en una cara plana, con ese Ø
    exterior y siempre como junta estática."""
    d = oring_groove(size, "static" if standard == "face" else seal)
    if standard == "shaft":
        outer, inner = diameter, diameter - 2 * d["gland"]
    elif standard == "bore":
        outer, inner = diameter + 2 * d["gland"], diameter
    else:
        outer, inner = diameter, diameter - 2 * d["width"]
    if inner <= 0:
        raise ValueError(tr("Ø {d} mm es demasiado pequeño para un o-ring de {size} mm").format(
            d=format_number(diameter), size=size))
    return d, round(outer, 3), round(inner, 3)


def create_oring_groove_node(
    standard: str = "shaft",
    size: str = "2.62",
    diameter: float = 20.0,
    seal: str = "static",
    unique_fn: Optional[Callable[[str], str]] = None,
) -> Node:
    """Máscara de la ranura de un o-ring. La de eje o agujero empieza en z = 0; la de cara plana tiene
    la cara en z = 0: baja la profundidad y sube 1 mm para que la resta quede limpia."""
    u_fn = unique_fn or (lambda s: s)
    d, outer, inner = _oring_diameters(standard, size, diameter, seal)
    name = tr("Ranura o-ring {size}").format(size=size)
    if standard == "shaft":
        return _ring_mask(name, outer + 2.0, inner, d["width"], 0.0, u_fn)
    if standard == "bore":
        return _ring_mask(name, outer, max(inner - 2.0, inner / 2), d["width"], 0.0, u_fn)
    return _ring_mask(name, outer, inner, d["gland"] + 1.0, -d["gland"], u_fn)


def describe(category: str, standard: str, size: str, length: float, fit: str,
             diameter: float = 20.0, seal: str = "static") -> list[str]:
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
    if category == "ring_groove":
        spec = _lookup(RING_TABLES[standard], size, tr("Diámetro"))
        title = (tr("Ranura de eje Ø{size} para anillo 3AM1-{size} (ANSI B27.7)") if standard == "3am1"
                 else tr("Ranura de agujero Ø{size} para anillo 3BM1-{size} (ANSI B27.7)"))
        return [title.format(size=size),
                tr("Ø de la ranura {g} mm · ancho {w} mm · profundidad {d} mm").format(
                    g=fmt(spec["G"]), w=fmt(spec["W"]), d=fmt(spec["d"])),
                tr("Anillo de {t} mm de grueso · deja al menos {z} mm entre la ranura y el borde").format(
                    t=fmt(spec["t"]), z=fmt(spec["Z"]))]
    if category == "oring_groove":
        d, outer, inner = _oring_diameters(standard, size, diameter, seal)
        title = tr("Ranura para o-ring de {size} mm (sección AS568)").format(size=size)
        tail = tr("Profundidad del alojamiento {f} mm · el anillo se aplasta un {p} %").format(
            f=fmt(d["gland"]), p=d["squeeze"])
        if standard == "shaft":
            return [title, tr("En un eje, para un agujero de Ø{a}: Ø de fondo {r} mm · ancho {w} mm").format(
                a=fmt(diameter), r=fmt(inner), w=fmt(d["width"])), tail]
        if standard == "bore":
            return [title, tr("En un agujero, para un eje de Ø{a}: Ø de fondo {r} mm · ancho {w} mm").format(
                a=fmt(diameter), r=fmt(outer), w=fmt(d["width"])), tail]
        return [title, tr("En una cara plana, junta estática: Ø {o} a Ø {i} mm · ancho {w} mm").format(
            o=fmt(outer), i=fmt(inner), w=fmt(d["width"])), tail]
    raise ValueError(f"Categoría desconocida: {category}")
