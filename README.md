# OpenSCAD GUI Mejorada (OPENSCAD-GUIEXP2026)

> **El poder del diseño paramétrico por código, elevado a una experiencia visual, accesible y moderna.**
> *The power of code-based parametric design, elevated into a visual, accessible, and modern experience.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt-green.svg)](https://www.qt.io/)
[![3D Engine](https://img.shields.io/badge/3D-OpenGL%20%2F%20PyQtGraph-orange.svg)](https://pyqtgraph.readthedocs.io/)
[![OpenSCAD](https://img.shields.io/badge/OpenSCAD-Compatible-yellow.svg)](https://openscad.org/)
[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

---

## 📖 Descripción del Proyecto / Project Overview

**OpenSCAD GUI Mejorada** es un entorno de escritorio moderno que elimina la brecha entre el modelado algorítmico por código y la ergonomía de los entornos CAD visuales modernos.

Mantiene el principio de **cero dependencia propietaria** (genera y edita archivos `.scad` estándar en tiempo real sin perder comentarios ni variables personalizadas), pero transforma por completo el flujo de trabajo: reemplaza la pantalla en blanco por un entorno asistido, con manipulación 3D interactiva, sugerencias inteligentes y validaciones didácticas.

---

## 🌟 Características Principales / Key Features

### 1. 🎯 Manipulación Directa y Visor 3D Interactivo
* **Gizmos 3D de Traslación:** Arrastra los ejes espaciales directamente en la ventana 3D para reposicionar sólidos en tiempo real sin adivinar coordenadas a ciegas.
* **Selección por Raycasting:** Haz clic sobre cualquier cara o cuerpo en el visor 3D para localizarlo y seleccionarlo automáticamente en el árbol de operaciones.
* **Vista Explosionada (Exploded View):** Desliza un control para desensamblar suavemente mecanismos complejos hacia afuera desde su centro de masa; ideal para revisar ajustes internos y ensamblajes de múltiples piezas.
* **Herramienta de Medición Espacial:** Mide distancias reales con un clic, obteniendo el valor absoluto y sus deltas ($\Delta X, \Delta Y, \Delta Z$) al instante.

### 2. 🧩 Asistente Didáctico de Operaciones Booleanas (`difference`, `union`, `intersection`)
* Resuelve la duda más común: *¿a qué pieza se le resta qué?*
* El árbol de operaciones identifica automáticamente el rol de cada sólido con etiquetas semánticas y tooltips visuales:
  - `[Base (+)] ⭐ Sólido BASE (al que se le resta)`
  - `[- Resta] ✂️ Sólido que se RESTA a 'Pieza'`
* **Autocompletado de sólidos:** Elige fácilmente qué componentes restan o se intersectan seleccionándolos desde el árbol o mediante sugerencias guiadas.

### 3. ✍️ Editor de Código Moderno con Experiencia "Estilo VS Code"
* **Parameter Hints y Ayuda de Firma Flotante (Signature Help):** Al escribir cualquier primitiva (`cylinder(`, `cube(`, `linear_extrude(`), función matemática (`sin(`, `atan2(`) o módulo de usuario, aparece una tarjeta flotante contextual indicando cada parámetro, su tipo y valor por defecto, resaltando el argumento activo.
* **Aceptación de sugerencias sin ratón:** Presiona `Tab` o `Enter` para insertar autocompletados al vuelo.
* **Herramientas de productividad y accesibilidad integradas:**
  - Numeración de líneas y resaltado sutil de línea activa.
  - Cierre y emparejamiento automático de llaves, corchetes y comillas `{ }`, `[ ]`, `( )`.
  - Verificación en tiempo real de balance de llaves con advertencias de sintaxis.
  - Sangrado y desangrado por bloques (`Tab` / `Shift+Tab`).
  - Alternancia rápida de comentarios con `Ctrl + /`.
  - Barra de búsqueda flotante interactiva con coincidencia instantánea (`Ctrl + F`).
  - Zoom dinámico de tipografía con `Ctrl + Rueda del ratón`.
  - Snippets de componentes industriales normalizados (tornillería Allen ISO 4762, tuercas hexagonales, etc.).

### 4. 📐 Asistente de Bocetos 2D (Sketching)
* Crea perfiles 2D complejos en un lienzo interactivo milimétrico con imantación a cuadrícula (*snap-to-grid*), y extruye tus formas automáticamente al espacio 3D con un solo clic.

### 5. 🔩 Ensamblaje Industrial por Defecto (Figura 5.31 — Rueda con Eje Giratorio)
* La aplicación arranca con un **ensamblaje mecánico de ingeniería completo de 6 piezas** parametrizadas y diferenciadas por materiales:
  - **Pza 1 — Rueda:** Hule duro $\varnothing 100\text{ mm}$ con rebaje lateral y alojamiento central.
  - **Pza 2 — Poste giratorio:** Acero maquinado torneado con brida $\varnothing 18\text{ mm}$, vástago $\varnothing 14\text{ mm}$ y chaflanes.
  - **Pza 3 — Perno de eje:** Acero maquinado con cabeza embutida $\varnothing 16\text{ mm}$ y extremo roscado M6.
  - **Pza 4 — Soporte en U:** Horquilla estampada de chapa $2.36\text{ mm}$ con patas ahusadas y avance giratorio (*caster trail*).
  - **Pza 5 — Buje:** Latón autolubricado $\varnothing 14 \times \varnothing 8\text{ mm}$.
  - **Pza 6 — Tuerca Hexagonal M6:** Acero normalizado entrecaras $10\text{ mm}$.

### 6. 🌍 Soporte Multi-idioma Dinámico (i18n)
* Interfaz con traducción en tiempo real a **6 idiomas** (*Español, Inglés, Francés, Alemán, Italiano y Portugués*).

### 7. 📦 Ejecutable Portable y Sin Instalador
* Compilable en un único archivo ejecutable: `OpenSCAD_GUI_Mejorada.exe` sin instaladores ni configuración.
* Detección automática de OpenSCAD local/portable o instalado en el sistema.

---

## 🚀 Instrucciones de Implementación / Installation & Usage

### Requisitos Previos
* **Python 3.10 o superior** (probado en Python 3.10, 3.11, 3.12, 3.13 y 3.14).
* **OpenSCAD** (opcional pero recomendado para el renderizado CSG exacto en STL; descárgalo gratis desde [openscad.org](https://openscad.org/downloads.html)).

---

### Opción 1: Ejecución Directa con Python (Recomendada para Desarrollo)

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/luisxbrito/OPENSCAD-GUIEXP2026.git
   cd OPENSCAD-GUIEXP2026
   ```

2. **Instalar dependencias:**
   ```bash
   python -m pip install -r requirements.txt
   ```
   *(Dependencias: `PySide6>=6.5`, `pyqtgraph>=0.13.3`, `PyOpenGL>=3.1.7`, `numpy>=1.24`)*

3. **Iniciar la aplicación:**
   ```bash
   python main.py
   ```
   *Para abrir un archivo específico directamente:*
   ```bash
   python main.py ruta/a/tu_archivo.scad
   ```

---

### Opción 2: Compilar el Ejecutable Portable (.exe para Windows)

Si deseas generar el ejecutable autónomo para distribuirlo sin requerir que otros usuarios tengan Python instalado:

1. **Instalar PyInstaller:**
   ```bash
   pip install pyinstaller
   ```

2. **Compilar con el script automatizado:**
   * En Windows (doble clic o terminal):
     ```cmd
     build_portable.bat
     ```
   * O mediante Python:
     ```bash
     python build_portable.py
     ```

3. **Resultado:**
   El script generará en la carpeta `dist/`:
   * `dist/OpenSCAD_GUI_Mejorada.exe` *(Ejecutable portable independiente de ~64 MB)*.
   * `dist/OpenSCAD_GUI_Mejorada_Portable.zip` *(Paquete comprimido con el ejecutable y ejemplos)*.

---

## 📂 Estructura del Proyecto / Project Structure

```text
OPENSCAD-GUIEXP2026/
├── main.py                      # Punto de entrada de la aplicación
├── requirements.txt             # Dependencias del proyecto
├── build_portable.py            # Script automatizado de compilación portable
├── build_portable.bat           # Acceso rápido en 1 clic para compilar en Windows
├── OpenSCAD_GUI_Mejorada.spec   # Configuración de empaquetado PyInstaller
├── README.md                    # Documentación e instrucciones
├── LICENSE                      # Licencia GPLv3
│
├── scadgui/                     # Paquete principal de la aplicación
│   ├── catalog.py               # Catálogo de 30 módulos de OpenSCAD, parámetros e iconos
│   ├── geometry.py              # Motor geométrico 3D, mallas aproximadas, sombras y raycasting
│   ├── i18n.py                  # Sistema internacionalización dinámico (es, en, fr, de, it, pt)
│   ├── model.py                 # Modelo AST bidireccional (Document, Node, RawCode)
│   ├── parser.py                # Analizador sintáctico tolerante de scripts .scad
│   ├── runner.py                # Lanzador asíncrono y detección de OpenSCAD
│   └── ui/                      # Módulos de interfaz gráfica (PySide6)
│       ├── boolean_picker.py    # Asistente y selector didáctico de operaciones booleanas
│       ├── canvas2d.py          # Lienzo 2D con imantación milimétrica para bocetos
│       ├── codeview.py          # Editor de código con Signature Help y autocompletado Tab
│       ├── icons.py             # Generador dinámico de iconos vectoriales SVG
│       ├── mainwindow.py        # Ventana principal, cinta de comandos y árbol
│       ├── properties.py        # Panel inspector y editor interactivo de propiedades
│       ├── style.py             # Hoja de estilos moderna y temas
│       └── viewer3d.py          # Visor 3D OpenGL con gizmos y vista explosionada
│
├── examples/                    # Modelos de ejemplo
│   ├── rueda_con_eje_giratorio.scad  # Ensamblaje mecánico industrial (Figura 5.31)
│   └── placa_agujeros.scad           # Modelo clásico de placa con perforaciones
│
├── resources/                   # Recursos visuales e iconos
│   └── icon.ico                 # Icono de la aplicación
│
└── tests/                       # Suite completa de pruebas automatizadas
    ├── test_core.py             # Pruebas unitarias de AST, catálogo, i18n y snippets
    ├── test_geometry.py         # Pruebas de geometría, mallas, raycasting y exportación
    └── simulacion/              # Pruebas de integración de interfaz
        ├── sim_ventana_visor_opengl.py
        └── sim_ventana_visor_imagen.py
```

---

## 🧪 Ejecución de Pruebas / Running Tests

El proyecto cuenta con una cobertura completa de pruebas automatizadas:

```bash
# 1. Pruebas del núcleo (AST, parser, generador, i18n, snippets, ayuda de firma)
python tests/test_core.py

# 2. Pruebas de geometría 3D (mallas fantasma, ray hits, normales, transformaciones)
python tests/test_geometry.py

# 3. Pruebas de simulación de interfaz de usuario
python tests/simulacion/sim_ventana_visor_opengl.py
python tests/simulacion/sim_ventana_visor_imagen.py
```

---

## ⌨️ Atajos de Teclado Útiles / Useful Shortcuts

| Atajo | Acción |
| :--- | :--- |
| <kbd>Tab</kbd> / <kbd>Enter</kbd> | Aceptar autocompletado en el editor de código |
| <kbd>Esc</kbd> | Cerrar autocompletado o sugerencias flotantes |
| <kbd>Ctrl</kbd> + <kbd>F</kbd> | Abrir barra de búsqueda interactiva |
| <kbd>Ctrl</kbd> + <kbd>/</kbd> | Alternar comentario de línea o bloque |
| <kbd>Tab</kbd> / <kbd>Shift+Tab</kbd> | Aumentar / reducir sangría de bloque de código |
| <kbd>Ctrl</kbd> + <kbd>Rueda del ratón</kbd> | Aumentar o reducir tamaño de fuente del editor |
| <kbd>Ctrl</kbd> + <kbd>Clic en 3D</kbd> | Selección múltiple de piezas en el visor 3D |
| <kbd>Ctrl</kbd> + <kbd>Z</kbd> / <kbd>Ctrl</kbd> + <kbd>Y</kbd> | Deshacer / Rehacer cambios |

---

## 📄 Licencia / License

Distribuido bajo la Licencia **GNU General Public License v3.0**. Consulta el archivo `LICENSE` para más detalles.\n