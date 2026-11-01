# OpenSCAD GUI Mejorada

A desktop front end for [OpenSCAD](https://openscad.org) that lets you build models with
buttons, a model tree and a 3D view, FreeCAD style, while every action is written as plain
OpenSCAD code. The `.scad` file it saves opens in regular OpenSCAD, and code you write by
hand (variables, loops, your own modules) is kept as is.

The interface is in Spanish by default and also available in English, French, German,
Italian and Portuguese (*Edit › Preferences*).

## What it does

- **Model tree and properties.** Ribbon with the 30 OpenSCAD primitives, transformations,
  booleans and extrusions. The property panel is generated from each module's parameters.
  Each part's name is stored as a trailing comment: `cube([40, 30, 10]); // Base`.
- **Rounded and chamfered edges.** With *Pick edges* in the 3D view you click the edges of a
  `cube` or the top/bottom rim of a `cylinder` and round or chamfer them. The part becomes
  `cube_edges(...)` or `cylinder_edges(...)`; the definition of those two modules is written
  at the end of the file, so it opens in plain OpenSCAD without any library.
- **Arrays.** Linear, polar and grid arrays of the selected parts. Each one is written as a
  plain `for` loop, for example `for (i = [0 : 3]) translate(i * [20, 0, 0]) { ... }`, and is
  recognised again when the file is reopened. Other `for` loops are kept as code.
- **Code kept in sync.** Clicking a line selects the part. You can edit the code by hand and
  apply it back (Ctrl+Enter). Anything the tree cannot represent (other loops, `if`, user modules,
  `include`) shows up with a lock icon and is never lost when saving.
- **3D view (OpenGL).** OpenSCAD computes the final mesh only when the model changes;
  rotating, selecting and highlighting do not re-run it. Click a part in the 3D view to
  select it (clicking the wall of a hole selects the cylinder that was subtracted). Also:
  a translation gizmo, a measuring tool, colours from `color()`, and an exploded view that
  separates the parts of an assembly while keeping their holes.
- **Boolean helper.** Shows which solid is the base of a `difference` and which ones are
  subtracted, and lets you change the base.
- **Standard parts.** ISO 4762, DIN 933, DIN 7991 and ISO 7380 screws, DIN 934/985 nuts,
  DIN 125 washers, heat-set inserts, 6xx ball bearings and 2020/2040 aluminium profiles, each
  as a solid or as the matching clearance hole (ISO 273). Only the sizes listed in each
  standard are offered. The parts have no thread and the profile slots are straight (no
  T shape): they are meant for fit-checking and drawings.
- **2D profiles.** A dialog that creates rounded rectangles, slots, regular polygons, stars,
  rings and L profiles from normal OpenSCAD nodes, optionally extruded.
- **Technical drawing.** An A4/A3 sheet with front, top, left-side and isometric projections
  in first-angle (ISO E) layout, border and title block, exportable to SVG, DXF or PDF.
- **Global variables and modules.** A panel for top-level variables, and a command that
  turns the selected parts into a parametric `module`.
- **Export** to STL, 3MF, OBJ, OFF, AMF, SVG, DXF, PDF and PNG through OpenSCAD.

## Requirements

- Python 3.10 or newer.
- OpenSCAD, installed or as a portable copy next to the program (it is found automatically
  in `C:\Program Files\OpenSCAD\`, next to the `.exe`, or in an `openscad/` subfolder).
  Without OpenSCAD the 3D view shows an approximate model without the boolean operations.
- Python packages: `PySide6`, `pyqtgraph`, `PyOpenGL`, `numpy` (see `requirements.txt`).

## Running

On Windows, double-click `run.bat`: it installs the packages the first time and starts the
program. Elsewhere:

```bash
python -m pip install -r requirements.txt
python main.py                 # starts with an empty model (examples are in the File menu)
python main.py part.scad       # opens a file
```

If the OpenGL view does not work on a machine, untick *View › OpenGL Viewport* and restart:
the program falls back to static images rendered by OpenSCAD.

## Portable Windows executable

```bash
python -m pip install pyinstaller
python build_portable.py        # or double-click build_portable.bat
```

This produces `dist/OpenSCAD_GUI_Mejorada.exe` (a single file, no Python needed) and
`dist/OpenSCAD_GUI_Mejorada_Portable.zip` with the examples. OpenSCAD is not bundled: put a
portable OpenSCAD in the same folder or in `openscad/`, or install it.

## Project layout

```text
main.py                  entry point
scadgui/
  catalog.py             the 30 OpenSCAD modules and the 3 arrays: parameters, icons
  model.py               Document / Node / RawCode and the code generator
  parser.py              .scad -> Document (unknown code is kept as RawCode)
  geometry.py            per-part approximate meshes, STL/OFF reading, lighting, picking,
                         exploded view (numpy only)
  runner.py              runs openscad in the background
  hardware.py            standard parts tables and builders
  sketches.py            2D profile builders
  drawing.py             technical drawing sheet generator
  operations.py          help texts and quick presets for each operation
  library.py, edges.py   cube_edges / cylinder_edges modules and the edge rounding logic
  code_assist.py         code templates and parameter hints for the editor
  i18n.py, locales/      translations (one file per language)
  ui/                    PySide6 windows and dialogs
examples/                swivel caster assembly and a plate with holes
tests/                   see below
```

Adding an OpenSCAD module only needs a new `Spec` in `catalog.py`: the ribbon button, the
property form, the generator and the parser all read from it.

## Tests

None of these need OpenSCAD except the last one; the first three do not need Qt either.

```bash
python tests/test_core.py        # model, generator, parser round-trip, standard parts, drawing
python tests/test_geometry.py    # meshes, volumes, STL/OFF, picking, colours, exploded view
python tests/test_i18n.py        # every interface text translated, no duplicate keys
python tests/simulacion/sim_ventana_visor_opengl.py   # whole window against a stub of Qt
python tests/simulacion/sim_ventana_visor_imagen.py
python tests/test_openscad.py    # renders generated code with the real OpenSCAD (skipped if not found)
```

The two `sim_*` scripts drive the main window with a fake PySide6/pyqtgraph, so they catch
logic errors but not drawing problems; after changes, also open the real program.

## Known limitations

- Picking in the 3D view works for parts with literal values (cube, sphere, cylinder,
  polyhedron, 2D shapes and extrusions). Text, imports, the result of `hull`/`minkowski`
  and parts driven by variables are visible but must be selected in the tree or the code.
- When OpenSCAD does not export face colours, colours are worked out by matching faces to
  parts, so faces produced by `hull`/`minkowski` come out grey.
- Comments placed between the arguments of a call are lost when the code is regenerated.
- Only edges of `cube` and straight `cylinder` parts can be rounded, and not inside an
  extrusion, `hull`, `minkowski` or `resize`. Each part has a single radius for all its rounded
  edges. Where three rounded edges meet, the corner is the intersection of their cylinders
  rather than a sphere (that construction never fails with CGAL or Manifold).
- The 2D profile dialog is form based; there is no constraint-driven sketcher.
- No license has been chosen yet: add a `LICENSE` file before publishing the code.
