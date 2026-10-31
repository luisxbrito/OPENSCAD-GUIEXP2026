"""Pruebas de las traducciones (no necesitan Qt).

Reúne todos los textos de la interfaz que pasan por tr() y comprueba que cada idioma
los tenga, sin claves duplicadas y sin entradas que se quedaron en español.

Ejecutar:  python tests/test_i18n.py
"""

import ast
import glob
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from scadgui.i18n import LANGUAGES, TRANSLATIONS, tr, set_language  # noqa: E402

# Textos que se escriben igual en todos los idiomas (nombres propios, unidades, símbolos).
SAME_EVERYWHERE = {
    "Color", "Minkowski", "Manifold (rápido)", "OpenSCAD", "X +10", "X -10", "Y +10", "Y -10",
    "Z +10", "Z -10", "Z = 0", "X +90°", "Y +90°", "Z +90°", "Z +45°", "Z +180°", "5 mm", "10 mm",
    "20 mm", "SteelBlue", "Tomato", "Gold", "SeaGreen", "DimGray", "Purple", "Radio R=2",
    "Radio R=5", "Delta +1", "Delta -1", "Twist 90°", "Alta suave ($fn=64)",
}

# Palabras que en ese idioma se escriben igual que en español (revisadas una a una).
SAME_AS_SPANISH = {
    "pt": {"Automático", "Automático (recomendado)", "CÓDIGO", "CÓDIGO OPENSCAD", "Círculo", "Código",
           "Código ASCII / Unicode", "Mapas de altura (*.png *.dat);;Todos (*)", "Módulo", "Módulo OpenSCAD",
           "Número de lados:", "Polígono", "Polígono regular", "Rápido (300 ms)", "Sólidos 3D",
           "Tipo de componente normalizado", "Tipo de perfil 2D", "código", "de",
           "Círculo 1", "Círculo 2", "Hexágono", "Polígono de {n} lados"},
}


def _string_args(call: ast.Call, positions, keywords):
    for i in positions:
        if i < len(call.args) and isinstance(call.args[i], ast.Constant) and isinstance(call.args[i].value, str):
            yield call.args[i].value
    for kw in call.keywords:
        if kw.arg in keywords and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            yield kw.value.value


def interface_strings() -> set:
    """Todos los textos que la interfaz traduce."""
    out = set()
    for path in glob.glob(os.path.join(ROOT, "scadgui", "**", "*.py"), recursive=True):
        if path.endswith("i18n.py"):
            continue
        for node in ast.walk(ast.parse(open(path, encoding="utf-8").read())):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name == "tr":
                out.update(_string_args(node, [0], ()))
            elif name == "_act":  # MainWindow._act(texto, función, atajo, icono, ayuda)
                out.update(_string_args(node, [0, 4], ("tip",)))

    from scadgui.catalog import CATEGORIES, SPECS
    from scadgui.operations import OPERATION_HELPERS
    from scadgui.sketches import PROFILES
    out.update(s.label for s in SPECS.values())
    out.update(s.hint for s in SPECS.values() if s.hint)
    out.update(p.title for s in SPECS.values() for p in s.params)
    out.update(t for _, t, _ in CATEGORIES)
    out.update(h for _, _, h in CATEGORIES)
    for info in OPERATION_HELPERS.values():
        out.update(info[k] for k in ("title", "summary", "how_it_works", "pro_tip", "category") if k in info)
        out.update(p[0] for p in info.get("presets", []))
    out.update(label for _, label in PROFILES)
    from scadgui.code_assist import OPENSCAD_BUILTINS, SNIPPETS_CATALOG
    out.update(info["doc"] for info in OPENSCAD_BUILTINS.values())
    out.update(param[2] for info in OPENSCAD_BUILTINS.values() for param in info["params"])
    out.update(label for label, _code in SNIPPETS_CATALOG)

    # Datos de módulos con Qt: se leen del código sin importarlos.
    for rel, var, index in (("scadgui/ui/hardware_dialog.py", "CATEGORIES", 1),
                            ("scadgui/ui/viewer3d.py", "VIEWS", None),
                            ("scadgui/ui/mainwindow.py", "EXTRA_BUTTONS", (3, 4))):
        tree = ast.parse(open(os.path.join(ROOT, rel), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                target = node.targets[0] if isinstance(node, ast.Assign) else node.target
                if getattr(target, "id", None) != var:
                    continue
                value = ast.literal_eval(node.value)
                if index is None:
                    out.update(value)          # claves de un dict
                elif isinstance(index, tuple):
                    out.update(row[i] for row in value for i in index)
                else:
                    out.update(row[index] for row in value)
    return {s for s in out if s.strip()}


def duplicate_keys() -> dict:
    """Claves repetidas en cada archivo de idioma (Python se queda con la última sin avisar)."""
    dups = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "scadgui", "locales", "*.py"))):
        for node in ast.walk(ast.parse(open(path, encoding="utf-8").read())):
            if isinstance(node, ast.Dict):
                seen, repeated = set(), []
                for k in node.keys:
                    (repeated.append(k.value) if k.value in seen else seen.add(k.value))
                if repeated:
                    dups[os.path.basename(path)] = repeated
    return dups


def test_sin_claves_duplicadas():
    files = glob.glob(os.path.join(ROOT, "scadgui", "locales", "*.py"))
    assert len(files) == 6  # __init__ + 5 idiomas: la prueba no puede pasar por no encontrar nada
    assert duplicate_keys() == {}, duplicate_keys()


def test_todos_los_textos_traducidos():
    needed = interface_strings()
    for lang, table in TRANSLATIONS.items():
        missing = sorted(s for s in needed if s not in table)
        assert not missing, f"{lang}: faltan {len(missing)}: {missing[:5]}"


def _looks_spanish(text: str) -> bool:
    low = f" {text.lower()} "
    return any(c in low for c in "ñ¿¡") or any(w in low for w in (
        " de ", " la ", " el ", " que ", " para ", " con ", " los ", " las ", " sin ", " una ", " del ",
        "ción", "ó", "í", "á"))


def test_nada_quedo_en_espanol():
    """Una traducción idéntica al original solo vale si no es texto en español (p. ej. "Error", "Delta")."""
    for lang, table in TRANSLATIONS.items():
        allowed = SAME_EVERYWHERE | SAME_AS_SPANISH.get(lang, set())
        same = sorted(k for k, v in table.items() if k == v and k not in allowed and _looks_spanish(k))
        assert not same, f"{lang}: {len(same)} textos sin traducir: {same[:5]}"


def test_marcadores_y_atajos_se_conservan():
    """Las traducciones mantienen los {marcadores}, saltos de línea y atajos (Ctrl+F) del original."""
    import re
    for lang, table in TRANSLATIONS.items():
        for src, dst in table.items():
            for pattern in (r"\{[a-z_]*\}", r"\n", r"\$fn", r"%[sd]"):
                assert sorted(re.findall(pattern, src)) == sorted(re.findall(pattern, dst)), (lang, src, dst)


def test_tr_y_cambio_de_idioma():
    assert len(LANGUAGES) == 6
    set_language("en")
    assert tr("Cubo") == "Cube"
    assert tr("texto que no existe") == "texto que no existe"
    set_language("es")
    assert tr("Cubo") == "Cubo"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print("FALLA", name, "->", str(exc)[:300])
    sys.exit(1 if failures else 0)
