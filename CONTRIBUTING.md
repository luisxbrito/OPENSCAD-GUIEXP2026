# Contributing

Thanks for wanting to improve OpenSCAD GUI Mejorada. Issues and pull requests are welcome in English
or Spanish. This page tells you how the code is organised, the rules that keep it working, and how
to check a change before you send it.

> **Language note.** The interface is translated into six languages, and the OpenSCAD code the program
> writes is commented in English. The Python source code comments and the architecture notes in
> [CONTEXTO_PARA_IA.md](CONTEXTO_PARA_IA.md) are still in Spanish; translating them is planned. The
> interface texts in the code stay in Spanish on purpose: Spanish is the base language that the
> translation files use as keys.

## Setting up

- Python 3.10 or newer.
- `python -m pip install -r requirements.txt` (PySide6, pyqtgraph, PyOpenGL, numpy).
- [OpenSCAD](https://openscad.org/downloads.html) 2021.01 or newer, to see the real result and run the
  tests that render with it. Without it the program shows an approximate preview, and those tests
  are skipped.
- Run the program with `python main.py`, or `run.bat` on Windows.

## How the code is organised

```
main.py                    entry point
scadgui/                   all the logic, with no Qt (tested without a window)
  catalog.py               every command the interface can create: a Spec with its Params, plus icons
  model.py                 the document: Node, RawCode, Expr, Document and generate() (model -> code)
  parser.py                code -> model; anything it does not understand is kept as RawCode
  geometry.py              approximate meshes (numpy) for the preview, picking and the exploded view
  library.py               our own OpenSCAD modules, written at the end of the .scad when used
  gears.py, flanges.py,    mechanical parts: formulas, standard tables and design warnings
  hardware.py, camshaft.py
  i18n.py, locales/*.py    tr() and one dictionary per language (Spanish text -> translation)
  runner.py                runs OpenSCAD (the only Qt class outside ui/)
scadgui/ui/                windows and dialogs only (PySide6)
tests/                     test_core, test_geometry, test_i18n, test_tema, test_openscad,
                           test_ventana_qt, and simulacion/ (window walk-throughs with a fake Qt)
```

## Rules that must not be broken

1. **The model is the source of truth.** The interface never edits code text. It changes the
   `Document` and its `Node`s through `MainWindow.mutate(...)`, which stores the undo step and
   regenerates the code.
2. **Opening and saving never loses code.** Whatever the parser does not understand (variables,
   loops, `if`, user modules, `include`, loose comments) is kept as `RawCode`. A change to
   `generate()` or `parse()` needs a round-trip test: `generate(parse(text)).text == text`.
3. **Part names are trailing comments** (`cube([10, 10, 10]); // Base`), and containers always have
   braces. The parser relies on both.
4. **A new command is a `Spec` in `catalog.py`**, with an icon, and with an approximate mesh in
   `geometry.solid()` if it has geometry. If it is our own module, its OpenSCAD code goes in
   `library.py` (see rule 9).
5. **Every visible text goes through `tr()`**, with data passed by `.format()`, never inside an
   f-string: `tr("Exported: {path}").format(path=p)`. Every new text needs its translation in the five
   files of `scadgui/locales/`; `tests/test_i18n.py` fails if one is missing or left in Spanish.
6. **Logic stays out of `ui/`.** Data, formulas and checks live in `scadgui/*.py` without importing
   Qt, and their tests must not need PySide6. `ui/` only builds widgets and calls that logic.
7. **Do not silence errors.** No `except Exception: pass`; catch only the exception you expect.
8. **Standard parts never swap a dimension.** If a size is not in the table of its standard, the
   builder raises `ValueError` and the dialog only offers the sizes that exist. Every table names its
   source (standard, edition, table and page) in the code. Do not commit the standards or books
   themselves (they are copyrighted, and `*.pdf` is ignored): only the values, with their citation.
9. **Our OpenSCAD modules** (`library.py`) are commented in English. If you change one that already
   shipped, add the previous text to `PREVIOUS_VERSIONS`, so files saved with it are still
   recognised and updated when opened.
10. **Check with the real OpenSCAD** when you touch `library.py` or the shape of the generated code:
    `tests/test_openscad.py` renders it and compares volumes with the preview mesh.
11. **One commit per finished change, with the tests passing.**

## Adding a mechanical part

A checklist, following the parts already in the program (the camshaft lobe `cam_lobe` is a short
example to copy):

1. Formulas or table lookups in a logic module (`gears.py`, `flanges.py`…), with the source cited.
2. The OpenSCAD module in `library.py`, registered in `LIBRARY`, with English comments.
3. A `Spec` in `catalog.py` (category `"mech"`), its icon in `ICONS`, and its button in
   `Ribbon.GROUPS` in `ui/mainwindow.py`.
4. The approximate mesh in `geometry.py`, built from the same points as the module, and its entry
   in `solid()`.
5. Measurements and warnings in the properties panel (`ui/properties.py`), calling the logic module.
6. Translations of the new texts in the five locale files.
7. Tests: values against the table, round trip, the mesh, and the volume against real OpenSCAD.

## Adding a language

Add a `scadgui/locales/<code>.py` with a `STRINGS` dictionary (Spanish text -> translation), list
it in `LANGUAGES` and `TRANSLATIONS` in `scadgui/i18n.py`, and run `tests/test_i18n.py`, which lists
every missing text. Keep the `{placeholders}`, line breaks and `&` shortcuts of the original.

## Running the tests

```bash
python tests/test_core.py        # model, generator, parser round trip, standard parts, tables
python tests/test_geometry.py    # meshes, volumes, picking, exploded view
python tests/test_i18n.py        # every interface text translated
python tests/test_tema.py        # dark theme contrast
python tests/test_openscad.py    # renders with the real OpenSCAD and checks volumes (skipped without it)
python tests/test_ventana_qt.py  # real mouse events and dialogs on the real Qt window
python tests/simulacion/sim_ventana_visor_opengl.py
python tests/simulacion/sim_ventana_visor_imagen.py
```

On Windows, `run_tests.bat` runs them all. The first three need neither Qt nor OpenSCAD and run on
every push. A new test should check the result (dimensions, orientation, generated text), not just
that a node exists, and it should fail without the change it protects.

## Licence

The project is GPL-3.0-or-later. By sending a contribution you agree that it is distributed under
that licence.
