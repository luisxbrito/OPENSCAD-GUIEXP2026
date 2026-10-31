"""Traducción de la interfaz.

Los textos se escriben en español en el código y se pasan por ``tr()``. Cada idioma
es un diccionario en ``scadgui/locales/<idioma>.py``; si falta una traducción se
muestra el texto en español. ``tests/test_i18n.py`` comprueba que no falte ninguna.
"""

from __future__ import annotations

from typing import Optional

from .locales import de, en, fr, it, pt

LANGUAGES = {
    "es": "Español",
    "en": "English",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "pt": "Português",
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": en.STRINGS,
    "fr": fr.STRINGS,
    "de": de.STRINGS,
    "it": it.STRINGS,
    "pt": pt.STRINGS,
}

_current_lang = "es"


def set_language(lang: str) -> None:
    """Cambia el idioma activo. Los códigos desconocidos se ignoran."""
    global _current_lang
    if lang in LANGUAGES:
        _current_lang = lang


def get_language() -> str:
    return _current_lang


def tr(text: str, lang: Optional[str] = None) -> str:
    """Texto traducido al idioma activo (o a ``lang``); el original si no hay traducción."""
    target = lang or _current_lang
    if target == "es":
        return text
    return TRANSLATIONS.get(target, {}).get(text, text)
