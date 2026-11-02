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
- **Gears and racks.** *3D Solids › Mechanical* has three involute parts, all by module:
  `spur_gear`, `helical_gear` and `rack`. The panel works out their measurements, warns about
  design problems, and a button places the part that meshes with the selected one, already in
  position and in phase.
  - **Spur gear** (module, teeth, pressure angle, backlash, bore): the panel shows the pitch,
    outside and root diameters, and warns about undercut teeth. The mating gear goes at
    m·(z1 + z2)/2.
  - **Helical gear** (plus helix angle and hand): the module and pressure angle given are the
    *normal* ones, so the pitch Ø is m·z/cos ψ. The panel also shows the transverse module and
    pressure angle, the lead of the helix, the twist over the face width and the axial overlap —
    it warns when that overlap drops below 1, because then the tooth does not wrap a whole pitch
    and the gear runs like a spur one. The mating gear is made with the **opposite hand** (two
    gears of the same hand do not mesh) and placed at m·(z1 + z2)/(2·cos ψ).
  - **Bevel gear** (module, teeth, teeth of the mate, shaft angle, face width): a straight bevel
    gear for shafts that cross, from the Handbook's milled-bevel formulas. Its cone angle depends
    on both tooth counts, so the mate's has to be given. The tooth comes from Tredgold's virtual
    spur gear (N/cos α teeth) and the profile is swept from the cone apex, which puts the face,
    pitch and root cones exactly where the tables say and gives the standard outside diameter
    D + 2·m·cos α. The apex sits at the origin and the gear faces +Z, so **the mate is the same
    part turned by the shaft angle** — nothing to move. The panel shows the cone angles, the cone
    distance, the virtual teeth and the maximum face width (C/3 or 8·m).
  - **Rack** (module, teeth, thickness, base, pressure angle, backlash): the basic tooth form of
    the module system, with straight flanks. Its pitch line sits at y = 0 and the teeth point
    towards +Y, so the gear put on it has its centre one pitch radius above. Tick **helix angle**
    and the teeth slant: the profile is sheared tan ψ per mm of thickness, the pitch becomes the
    transverse one, and the gear button then makes a **helical gear of the same hand** (a rack and
    a gear mesh with the same hand, unlike two gears). The ends of a helical rack come out at the
    slant of the teeth; square them off with a `difference()` if you need a flat end.

  Like the edge modules, the three are written at the end of the file, so the `.scad` opens in
  plain OpenSCAD without any library.
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
  The model tree can float over the 3D view (button *Tree* or *View › Tree over the 3D view*),
  like the browser in Fusion, so the view can use the whole window width.
  View shortcuts work as in Blender, on the numeric keypad or the number row, with the mouse
  over the 3D view: 1 front, 3 right, 7 top (Ctrl+key: the opposite view), 0 isometric,
  9 flip, 2/4/6/8 orbit 15°, 5 perspective/orthographic, `.` frame selection, Home frame all.
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
  library.py, edges.py   cube_edges / cylinder_edges / spur_gear / helical_gear / bevel_gear /
                         rack / pulley / v_pulley modules and the edge rounding logic
  gears.py               involute gear, bevel, rack, timing-pulley and V-belt pulley maths (same formulas as those modules)
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
python tests/test_tema.py        # dark theme: text/background contrast, tooltips, colour schemes
python tests/simulacion/sim_ventana_visor_opengl.py   # whole window against a stub of Qt
python tests/simulacion/sim_ventana_visor_imagen.py
python tests/test_openscad.py    # renders generated code with the real OpenSCAD (skipped if not found)
python tests/test_ventana_qt.py  # real mouse events on the 3D view with real Qt (skipped without PySide6)
```

On Windows, `run_tests.bat` runs all of them in order and says at the end whether any failed.
Install `pyqtgraph` in the same Python you start the program with, or the window tests are skipped;
those are the ones that catch Windows-only drawing problems.

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
  edges. Where three rounded edges meet the corner is a sphere; where only two meet, the two
  fillets simply cross (no vertex blend), as in most CAD programs without a corner setback.
- The 2D profile dialog is form based; there is no constraint-driven sketcher.
- No license has been chosen yet: add a `LICENSE` file before publishing the code.
