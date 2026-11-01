"""Esquemas de color del visor, los mismos de OpenSCAD (Archivo › Preferencias).

Los colores salen de los archivos ``color-schemes/render/*.json`` de OpenSCAD (Cornfield, el
predeterminado de OpenSCAD, está escrito en su código): el fondo y el color de las piezas sin
``color()`` en la vista previa. ``DEFAULT`` es el aspecto propio de esta interfaz.

El visor de imágenes pasa el nombre a OpenSCAD (``--colorscheme``); el visor OpenGL usa los
colores de aquí. Este módulo no necesita Qt.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT = "default"   # aspecto propio de la interfaz (el de siempre)


@dataclass(frozen=True)
class ColorScheme:
    name: str           # nombre en OpenSCAD (o DEFAULT)
    background: str     # fondo del visor
    face: str           # piezas sin color()

    @property
    def openscad_name(self) -> str:
        """Nombre para ``--colorscheme`` (el propio se parece a Tomorrow Night)."""
        return "Tomorrow Night" if DEFAULT == self.name else self.name

    def rgba(self, which: str = "face") -> tuple:
        h = getattr(self, which).lstrip("#")
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1.0,)

    @property
    def light(self) -> bool:
        """Fondo claro: los textos del visor se leen mejor oscuros que blancos."""
        return _contrast(self.background, "#1B2230") > _contrast(self.background, "#FFFFFF")


def _luminance(color: str) -> float:
    h = color.lstrip("#")
    lin = [(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
           for c in (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


SCHEMES: dict[str, ColorScheme] = {
    DEFAULT: ColorScheme(DEFAULT, "#262B33", "#CCD1DB"),
    "Cornfield": ColorScheme("Cornfield", "#FFFFE5", "#F9D72C"),
    "Metallic": ColorScheme("Metallic", "#AAAAFF", "#DDDDFF"),
    "Sunset": ColorScheme("Sunset", "#AA4444", "#FFAAAA"),
    "Starnight": ColorScheme("Starnight", "#000000", "#FFFFE0"),
    "BeforeDawn": ColorScheme("BeforeDawn", "#333333", "#CCCCCC"),
    "Nature": ColorScheme("Nature", "#FAFAFA", "#16A085"),
    "Daylight Gem": ColorScheme("Daylight Gem", "#F0F0F0", "#02DAF7"),
    "Nocturnal Gem": ColorScheme("Nocturnal Gem", "#0C0C0C", "#02DAF7"),
    "DeepOcean": ColorScheme("DeepOcean", "#333333", "#EEEEEE"),
    "Solarized": ColorScheme("Solarized", "#FDF6E3", "#B58800"),
    "Tomorrow": ColorScheme("Tomorrow", "#F8F8F8", "#4271AE"),
    "Tomorrow Night": ColorScheme("Tomorrow Night", "#1D1F21", "#81A2BE"),
    "ClearSky": ColorScheme("ClearSky", "#87CEEB", "#F9D72C"),
    "Nord Dark": ColorScheme("Nord Dark", "#2E3440", "#88C0D0"),
    "Nord Light": ColorScheme("Nord Light", "#E5E9F0", "#88C0D0"),
}


def get(name: str) -> ColorScheme:
    """El esquema con ese nombre; uno desconocido (o un nombre antiguo) da el propio."""
    return SCHEMES.get(name, SCHEMES[DEFAULT])
