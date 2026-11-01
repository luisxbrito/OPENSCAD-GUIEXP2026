"""Contraste del tema oscuro (no necesita Qt).

Recorre la hoja de estilos y los estilos de cada widget (los ``themed("...")`` del código) y
comprueba que ninguna regla deje la letra casi del mismo color que su fondo, también en
``:hover``. Con el tema claro no se mira: es el original y las reglas heredan colores que esta
prueba no puede seguir.

Ejecutar:  python tests/test_tema.py
"""

import ast
import glob
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from scadgui.ui import style  # noqa: E402

HEX = r"(#[0-9A-Fa-f]{6}|#[0-9A-Fa-f]{3})\b"


def _luminance(color: str) -> float:
    h = color.lstrip("#")
    h = "".join(ch * 2 for ch in h) if len(h) == 3 else h
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _sheets():
    yield "style.py", style.stylesheet()
    for path in glob.glob(os.path.join(ROOT, "scadgui", "ui", "*.py")):
        for node in ast.walk(ast.parse(open(path, encoding="utf-8").read())):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "themed" and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                yield f"{os.path.basename(path)}:{node.lineno}", style.themed(node.args[0].value)


def test_letra_y_fondo_se_distinguen_en_oscuro():
    style.set_theme("dark")
    try:
        text_default = style.c("#1B2230", True)
        bad = []
        for where, css in _sheets():
            for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css) or [("", css)]:
                bg = re.search(r"background(?:-color)?\s*:\s*" + HEX, body)
                fg = re.search(r"(?<![-\w])color\s*:\s*" + HEX, body)
                if bg:
                    ratio = contrast(bg.group(1), fg.group(1) if fg else text_default)
                    if ratio < 3.0:
                        bad.append(f"{where} {selector.strip()} ({ratio:.2f})")
        assert not bad, bad
    finally:
        style.set_theme("light")


def test_boton_principal_al_pasar_el_raton():
    """Antes, en oscuro, el fondo del botón principal pasaba a azul claro bajo la letra blanca."""
    style.set_theme("dark")
    try:
        css = style.stylesheet()
        hover = re.search(r"QPushButton#primary:hover\s*\{[^}]*background:\s*" + HEX, css).group(1)
        assert contrast(hover, "#FFFFFF") > 4.5, hover
        assert style.c("#174A96", True) != "#174A96"      # como letra, sigue aclarándose
    finally:
        style.set_theme("light")



def test_ayudas_emergentes_con_fondo_y_letra_propios():
    """Windows pinta el fondo de los tooltips claro aunque la paleta sea oscura: el estilo debe
    fijar fondo y letra, y que se distingan, en los dos temas."""
    for theme in ("dark", "light"):
        style.set_theme(theme)
        try:
            css = style.tooltip_stylesheet()
            bg = re.search(r"background:\s*" + HEX, css).group(1)
            fg = re.search(r"(?<![-\w])color:\s*" + HEX, css).group(1)
            assert contrast(bg, fg) > 7, (theme, bg, fg)
        finally:
            style.set_theme("light")
    style.set_theme("dark")
    try:
        assert style.tooltip_stylesheet().count("#20252D") == 1     # fondo oscuro en el tema oscuro
    finally:
        style.set_theme("light")


def test_esquemas_de_color_como_los_de_openscad():
    """Los esquemas del visor llevan los colores de OpenSCAD (si sus archivos están al lado)."""
    import json
    from scadgui import colorschemes
    assert colorschemes.get("no existe") is colorschemes.SCHEMES[colorschemes.DEFAULT]
    assert colorschemes.get("Cornfield").light and not colorschemes.get("Tomorrow Night").light
    folder = os.path.join(ROOT, "..", "color-schemes", "render")
    if not os.path.isdir(folder):
        return                                  # fuera del árbol de OpenSCAD: solo lo anterior
    for path in glob.glob(os.path.join(folder, "*.json")):
        data = json.load(open(path, encoding="utf-8"))
        if not data.get("show-in-gui", True):
            continue
        scheme = colorschemes.SCHEMES[data["name"]]
        assert scheme.background == data["colors"]["background"].upper(), data["name"]
        assert scheme.face == data["colors"]["opencsg-face-front"].upper(), data["name"]

if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print("FALLA", name, "->", str(exc)[:600])
    sys.exit(1 if failures else 0)
