# Enhanced OpenSCAD GUI (`OPENSCAD-GUIEXP2026`)

> **The power of code-based parametric design, elevated into a visual, accessible, and modern CAD experience.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt-green.svg)](https://www.qt.io/)
[![3D Engine](https://img.shields.io/badge/3D-OpenGL%20%2F%20PyQtGraph-orange.svg)](https://pyqtgraph.readthedocs.io/)
[![OpenSCAD](https://img.shields.io/badge/OpenSCAD-Compatible-yellow.svg)](https://openscad.org/)
[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/luisxbrito/OPENSCAD-GUIEXP2026)

---

## 📖 Project Overview

**Enhanced OpenSCAD GUI** is a modern desktop CAD environment that bridges the gap between code-driven parametric modeling and visual CAD software ergonomics.

It strictly upholds the principle of **zero proprietary vendor lock-in**: it reads, generates, and edits standard `.scad` scripts in real time while preserving comments, custom variables, loops, and user modules. At the same time, it transforms the user experience by replacing the blank text window with an assisted workflow featuring interactive 3D viewports, direct manipulation gizmos, intelligent code assistance, and educational validation tools.

---

## 🌟 Key Features & Highlights

### 1. 🎯 Direct 3D Manipulation & Interactive Viewport
* **Real-time 3D Translation Gizmos:** Move objects visually along spatial coordinate axes directly inside the 3D viewport without guessing coordinates.
* **Raycasting Selection:** Click directly on any face or body in the 3D viewport to locate and select it instantly within the operations tree and property inspector.
* **Interactive Exploded View:** Drag a smooth slider to expand complex assemblies outward from their center of mass—ideal for inspecting internal clearances, bushings, and fasteners.
* **Spatial Measurement Tool:** Inspect real 3D distances between mesh points with a single click, providing the absolute measurement along with coordinate deltas ($\Delta X, \Delta Y, \Delta Z$).

### 2. 🧩 Educational Boolean Assistant (`difference`, `union`, `intersection`)
* **Eliminates OpenSCAD's biggest beginner pain point:** *Which solid is subtracted from which?*
* The operations tree automatically identifies the role of each solid using semantic badges and clear visual tooltips:
  - `[Base (+)] ⭐ BASE solid (the main body)`
  - `[- Subtraction] ✂️ Cutting solid being SUBTRACTED from the base`
* **Guided Solid Autocompletion:** Easily select cutting or intersecting solids directly from the model tree or via guided suggestions.

### 3. ✍️ Modern Code Editor with "VS Code-Style" Ergonomics
* **Parameter Hints & Floating Signature Help:** When typing any primitive (`cylinder()`, `cube()`, `linear_extrude()`), built-in math function (`sin()`, `atan2()`), or user-defined module, a floating card displays required parameters, data types, and default values while highlighting the active argument.
* **Keyboard-Driven Suggestion Acceptance:** Press <kbd>Tab</kbd> or <kbd>Enter</kbd> to accept completions and snippets on the fly without reaching for the mouse.
* **Integrated Accessibility & Productivity Tools:**
  - Line numbering and subtle highlighting of the active line.
  - Automatic closing and matching of braces, brackets, and quotes `{ }`, `[ ]`, `( )`.
  - Real-time syntax warning for unbalanced braces.
  - Block indentation and outdentation (<kbd>Tab</kbd> / <kbd>Shift+Tab</kbd>).
  - Quick comment toggle (<kbd>Ctrl</kbd> + <kbd>/</kbd>).
  - Floating interactive search bar with instant matching (<kbd>Ctrl</kbd> + <kbd>F</kbd>).
  - Dynamic font zoom (<kbd>Ctrl</kbd> + <kbd>Mouse Wheel</kbd>).
  - Engineering snippets library (Allen ISO 4762 bolts, hex nuts, bearings, etc.).

### 4. 📐 2D Sketching Canvas (Sketch-to-3D)
* Draw complex 2D profiles on an interactive millimeter canvas with magnetic snap-to-grid, and extrude them into 3D space with a single click.

### 5. 🔩 Default Industrial Assembly (Figure 5.31 — Caster Wheel with Swivel Axis)
* The application greets users with a complete **6-part mechanical engineering assembly** showcasing realistic material colors, hierarchy, and parametric design:
  - **Part 1 — Wheel:** Hard rubber $\varnothing 100\text{ mm}$ with side recess and central bushing bore.
  - **Part 2 — Swivel Post:** Turned machined steel with $\varnothing 18\text{ mm}$ flange, $\varnothing 14\text{ mm}$ shank, and assembly chamfers.
  - **Part 3 — Axle Bolt:** Machined steel with $\varnothing 16\text{ mm}$ countersunk head and M6 threaded end.
  - **Part 4 — U-Bracket:** Stamped sheet metal ($2.36\text{ mm}$ thick) with tapered legs and swivel caster trail.
  - **Part 5 — Bushing:** Self-lubricating brass $\varnothing 14 \times \varnothing 8\text{ mm}$.
  - **Part 6 — Hex Nut M6:** Standardized steel nut ($10\text{ mm}$ across flats).
* Serves as an immediate educational example of assembly hierarchy, exploded views, and material rendering.

### 6. 🌍 Dynamic Multi-language Support (i18n)
* Live interface translation across **6 languages** (*English, Spanish, French, German, Italian, and Portuguese*), covering menus, ribbons, parameter hints, boolean assistants, and error prompts.

### 7. 📦 Zero-Install Portable Windows Executable
* Distributable as a single standalone executable: `OpenSCAD_GUI_Mejorada.exe` (~64 MB).
* **No installation required:** Runs directly from a USB stick or local folder without needing Python or administrator rights.
* **Portable OpenSCAD integration:** Automatically detects local portable copies of OpenSCAD (`openscad.com` / `openscad.exe`) placed in the same folder or in an `openscad/` subfolder.

---

## 🛠️ Implementation & Setup Instructions

### Prerequisites
* **Python 3.10+** (Tested on Python 3.10, 3.11, 3.12, 3.13, and 3.14).
* **OpenSCAD** (Optional but recommended for exact CSG STL rendering; free download from [openscad.org](https://openscad.org/downloads.html)).

---

### Option 1: Running from Source (Development Mode)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/luisxbrito/OPENSCAD-GUIEXP2026.git
   cd OPENSCAD-GUIEXP2026
   ```

2. **Install dependencies:**
   ```bash
   python -m pip install -r requirements.txt
   ```
   *(Dependencies: `PySide6>=6.5`, `pyqtgraph>=0.13.3`, `PyOpenGL>=3.1.7`, `numpy>=1.24`)*

3. **Launch the application:**
   ```bash
   python main.py
   ```
   *To open a specific `.scad` file directly:*
   ```bash
   python main.py path/to/your_file.scad
   ```

---

### Option 2: Building the Portable Windows Executable (`.exe`)

To build the standalone `.exe` file that runs without Python:

1. **Install PyInstaller:**
   ```bash
   pip install pyinstaller
   ```

2. **Compile using the automated build script:**
   * On Windows terminal or double-click:
     ```cmd
     build_portable.bat
     ```
   * Or via Python:
     ```bash
     python build_portable.py
     ```

3. **Output:**
   The compiled binaries will be generated in `dist/`:
   * `dist/OpenSCAD_GUI_Mejorada.exe` *(Standalone single-file portable executable, ~64 MB)*.
   * `dist/OpenSCAD_GUI_Mejorada_Portable.zip` *(Portable ZIP package containing the executable and sample files)*.

---

## 📂 Project Structure

```text
OPENSCAD-GUIEXP2026/
├── main.py                      # Application entry point
├── requirements.txt             # Python dependencies
├── build_portable.py            # Automated portable build script
├── build_portable.bat           # 1-click Windows compilation script
├── OpenSCAD_GUI_Mejorada.spec   # PyInstaller packaging configuration
├── README.md                    # Project documentation and guide
├── LICENSE                      # GNU GPLv3 license
│
├── scadgui/                     # Core application package
│   ├── catalog.py               # 30 OpenSCAD module specifications, parameters & icons
│   ├── geometry.py              # 3D geometry engine, ghost meshes, lighting & ray hits
│   ├── i18n.py                  # Dynamic multi-language translation (en, es, fr, de, it, pt)
│   ├── model.py                 # Bidirectional AST model (Document, Node, RawCode)
│   ├── parser.py                # Tolerant .scad script parser
│   ├── runner.py                # Asynchronous OpenSCAD process runner and auto-detection
│   └── ui/                      # Graphical user interface modules (PySide6)
│       ├── boolean_picker.py    # Educational boolean operation dialog and selector
│       ├── canvas2d.py          # Interactive 2D sketch canvas with grid snapping
│       ├── codeview.py          # Modern code editor with Signature Help and Tab completion
│       ├── icons.py             # Dynamic SVG vector icon renderer
│       ├── mainwindow.py        # Main application window, command ribbon, and model tree
│       ├── properties.py        # Interactive property inspector and editor
│       ├── style.py             # Modern stylesheet and themes
│       └── viewer3d.py          # OpenGL 3D viewport with gizmos and exploded view
│
├── examples/                    # Sample models
│   ├── rueda_con_eje_giratorio.scad  # Mechanical engineering assembly (Figure 5.31)
│   └── placa_agujeros.scad           # Perforated mounting plate example
│
├── resources/                   # Visual assets and application icons
│   └── icon.ico                 # Application desktop icon
│
└── tests/                       # Comprehensive automated test suite
    ├── test_core.py             # AST, parser, code generator, i18n, and signature tests
    ├── test_geometry.py         # 3D geometry, meshes, raycasting, and export tests
    └── simulacion/              # Headless UI simulation tests
        ├── sim_ventana_visor_opengl.py
        └── sim_ventana_visor_imagen.py
```

---

## 🧪 Running the Test Suite

The project includes an extensive automated test suite covering unit, geometry, and headless UI tests:

```bash
# 1. Core unit tests (AST, parser, code generator, i18n, parameter hints, snippets)
python tests/test_core.py

# 2. 3D geometry engine tests (ghost meshes, raycasting, face normals, STL export)
python tests/test_geometry.py

# 3. Headless UI simulation tests
python tests/simulacion/sim_ventana_visor_opengl.py
python tests/simulacion/sim_ventana_visor_imagen.py
```

---

## ⌨️ Useful Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| <kbd>Tab</kbd> / <kbd>Enter</kbd> | Accept autocompletion / snippet in the code editor |
| <kbd>Esc</kbd> | Dismiss completion popup or parameter hint |
| <kbd>Ctrl</kbd> + <kbd>F</kbd> | Open floating interactive search bar |
| <kbd>Ctrl</kbd> + <kbd>/</kbd> | Toggle line / block comment |
| <kbd>Tab</kbd> / <kbd>Shift+Tab</kbd> | Indent / outdent selected block |
| <kbd>Ctrl</kbd> + <kbd>Mouse Wheel</kbd> | Zoom editor font size in or out |
| <kbd>Ctrl</kbd> + <kbd>3D Click</kbd> | Multi-select objects in the 3D viewport |
| <kbd>Ctrl</kbd> + <kbd>Z</kbd> / <kbd>Ctrl</kbd> + <kbd>Y</kbd> | Undo / Redo changes |

---

## 📄 License

Distributed under the **GNU General Public License v3.0**. See `LICENSE` for details.
