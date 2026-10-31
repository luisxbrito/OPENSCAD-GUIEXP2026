# Contexto del proyecto para continuar el desarrollo

Este documento es para el asistente que siga con el desarrollo: Gemini, otra IA o una persona.
Léelo entero antes de tocar código.

## 1. Qué es

**OpenSCAD GUI Mejorada**: aplicación de escritorio, al estilo FreeCAD, para crear sólidos
con botones. Cada acción se traduce a código OpenSCAD, como un ORM traduce objetos a SQL.
El archivo `.scad` que se guarda es OpenSCAD estándar y se abre en el OpenSCAD normal.

- Lenguaje: **Python 3.10+**. No se compila nada.
- Interfaz: **PySide6** (Qt 6). Visor 3D: **pyqtgraph + PyOpenGL + numpy**.
- OpenSCAD **no se modifica ni se compila**: se usa el programa instalado, por línea de
  comandos (`openscad.com` en Windows, porque `openscad.exe` no devuelve mensajes).
- El usuario trabaja en **Windows**. Los textos de la interfaz se escriben en **español** en el código y
  se traducen con `tr()` a otros 5 idiomas. Los comentarios del código están en español.
- La carpeta `openscad-master/` que contiene a esta es el código fuente de OpenSCAD. Solo
  sirvió de referencia para el catálogo de comandos; la app no la usa.

Arranque: `run.bat` (instala dependencias la primera vez) o `python main.py [archivo.scad]`.

## 2. Mapa de archivos

```
main.py                    punto de entrada
scadgui/                   lógica SIN Qt (se prueba sin PySide6)
  catalog.py               los 30 módulos de OpenSCAD y las 3 matrices (Spec/Param), iconos SVG
  model.py                 el "ORM": Node, RawCode, Expr, Document (operaciones), generate()
  parser.py                .scad → Document (tolerante; lo desconocido → RawCode)
  geometry.py              numpy: mallas aproximadas, STL/OFF, aristas, rayos, colores,
                           iluminación y vista explosionada
  hardware.py              tablas de tornillería/rodamientos/perfiles, constructores y describe()
  sketches.py              perfiles 2D paramétricos
  drawing.py               lámina técnica 2D (vistas en sistema europeo)
  operations.py            textos y ajustes rápidos de la guía de cada operación
  code_assist.py           plantillas, fragmentos y ayuda de parámetros del editor
  runner.py                QProcess que llama a openscad (única pieza de Qt fuera de ui/)
  i18n.py, locales/*.py    tr() y un diccionario por idioma (español → idioma)
scadgui/ui/                solo ventanas y diálogos (PySide6)
  mainwindow.py            ventana: cinta, árbol, propiedades, código, consola, deshacer, gizmo
  viewer3d.py / viewer.py  visor OpenGL (pyqtgraph) y visor de imágenes de respaldo
  codeview.py              editor de código
  properties.py, editors.py, boolean_dialog.py, hardware_dialog.py, sketch.py,
  drawing_dialog.py, module_dialog.py, operation_helper.py, preferences_dialog.py,
  variables.py, style.py, icons.py
examples/                  rueda_con_eje_giratorio.scad (se abre al arrancar), placa_agujeros.scad
tests/test_core.py         modelo, parser, generador, tornillería, plano técnico, módulos…
tests/test_geometry.py     geometría, colores, OFF/STL, selección, explosión
tests/test_i18n.py         cobertura de traducciones
tests/simulacion/          Qt/pyqtgraph simulados + 2 scripts que recorren la ventana
build_portable.py, OpenSCAD_GUI_Mejorada.spec   ejecutable portable con PyInstaller
```

## 3. Arquitectura y reglas que NO se deben romper

1. **El modelo es la fuente de verdad.** La interfaz nunca edita texto: modifica
   `Document`/`Node` y llama a `generate()`. Todo cambio pasa por
   `MainWindow.mutate(change, select, key)`, que guarda el estado para deshacer, regenera
   el código, actualiza el árbol y pide la vista.
2. **Ida y vuelta sin pérdidas.** Abrir y guardar un `.scad` no puede perder código. Lo que
   el parser no entiende (variables, `for` que no son matrices, `if`, `let`, `module`, `function`,
   `include`/`use`, módulos propios, comentarios sueltos) se guarda literal en un `RawCode`
   (candado en el árbol, se edita en el código). Los argumentos no literales son `Expr`.
3. **Los nombres de las piezas son comentarios al final de la línea**
   (`cube([40, 30, 10]); // Base`). Los contenedores siempre llevan llaves; el parser
   depende de ello. Una pieza nueva se llama como su palabra de OpenSCAD (`cube`,
   `cube001`...), nunca con un nombre traducido; si el nombre es igual a la palabra no se
   escribe comentario. Los botones de la cinta muestran solo esa palabra.
4. **Añadir un comando = añadir un `Spec` en `catalog.py`** (y su malla aproximada en
   `geometry.solid()`/`flat()` si tiene geometría). Un test exige 33 specs con icono.
   Las matrices (`linear_array`, `polar_array`, `grid_array`) son specs con
   `keyword="for"`: no son módulos de OpenSCAD. `model.array_head` escribe la cabecera del
   for y `parser.array_head` la reconoce; si se cambia una, hay que cambiar la otra (los
   tests de ida y vuelta lo comprueban). `catalog.openscad_modules()` excluye las matrices
   del resaltado y del autocompletado del editor.
5. **Visor OpenGL.** OpenSCAD calcula la malla final (OFF, con colores si la versión los
   exporta) solo cuando cambia el modelo. Seleccionar, resaltar, girar, medir, el gizmo y
   la explosión usan las mallas aproximadas (`build_ghosts`) y `assign_faces` (cara real →
   pieza). La iluminación se calcula en la CPU (`geometry.shade`, `shader=None`): no volver
   al shader `"shaded"` de pyqtgraph, que dejaba el modelo casi negro.
6. **El runner ejecuta un proceso a la vez**; una exportación en curso nunca se cancela.
7. **Temporales** junto al `.scad` guardado (`.scadgui_preview_*.scad`) para que
   `import()`/`include` encuentren las rutas relativas.
8. **Todo texto visible pasa por `tr()`.** Si lleva datos: `tr("Exportado: {path}").format(path=p)`,
   nunca un f-string con el texto dentro. Cada texto nuevo necesita su traducción en los 5
   archivos de `scadgui/locales/`; `tests/test_i18n.py` falla si falta alguna, si hay claves
   duplicadas o si una traducción se quedó en español. Esto incluye los nombres que ponen
   los asistentes (tornillería, bocetos) y los rótulos de la lámina técnica: salen en el
   idioma activo al crear la pieza. Los archivos de `locales/` se ordenan por
   `clave.lower()`.
9. **La lógica va fuera de `ui/`.** Datos y cálculos (presets, perfiles, firmas, piezas
   normalizadas, láminas) viven en `scadgui/*.py` sin importar Qt, y sus pruebas no pueden
   necesitar PySide6. `ui/` solo construye widgets y llama a esa lógica.
10. **El código de la aplicación no sabe que existen las pruebas.** Nada de detectar el Qt
    simulado ni de cambiar el comportamiento en las pruebas: si la simulación no soporta algo,
    se amplía `tests/simulacion/qtstub`.
11. **No silenciar errores.** Prohibido `except Exception: pass` y comprobar con `hasattr` métodos
    de Qt o atributos que crea el propio `__init__`. Capturar solo la excepción que se espera.
12. **Piezas normalizadas: nunca sustituir una medida.** Si una métrica no está en la tabla de
    su norma, los constructores lanzan `ValueError`; el diálogo solo ofrece
    `available_sizes(...)`, y el texto informativo sale de `describe()`, que usa las mismas
    constantes que la pieza.
13. **Plano técnico en sistema europeo** (ISO E): alzado arriba a la izquierda, planta debajo,
    perfil izquierdo a la derecha. Las rotaciones están en `drawing.VIEW_TRANSFORMS` y un test
    comprueba la orientación de cada vista.

## 4. Lecciones aprendidas (problemas que ya se resolvieron)

- **PySide6 ≥ 6.5**: enums con nombre completo (`Qt.AlignmentFlag.AlignCenter`). No combinar
  con `|` flags de tipos distintos: `int(x.value)`.
- `QTreeWidgetItemIterator += 1` no es fiable: recorrer con `childCount()`/`child(i)`.
- `QMenu.addAction(texto, función)` no es fiable: `menu.addAction(texto).triggered.connect(f)`.
- `QAction.triggered` pasa un `bool`: si el slot tiene parámetros con valor por defecto, usar
  `lambda: self.metodo(...)` (pasó con `open_example`, que recibía `False` como ruta).
- `QByteArray` → `.data()`, no `bytes(...)`.
- **Modo oscuro de Windows:** todo widget sin fondo y color de texto en `style.py` sale negro.
- **Gizmo:** el desplazamiento se mide desde el punto donde empezó el arrastre
  (`_drag_origin`), no desde el gizmo, que se mueve con la pieza; si no, la pieza oscila.
  Un clic sin arrastre no debe dejar un `translate` ni un paso de deshacer.
- **Plano técnico:** `rotate([90,0,0])` deja el alzado boca abajo; el correcto es
  `rotate([-90,0,0])`. `use <...>` no puede ir dentro de un módulo.
- **Variables:** un `Expr` se escribe con `.text`; `str(Expr)` producía `Expr('...')` en el archivo.

## 5. Cómo comprobar que no se rompe nada

Después de cada cambio:

```
python tests/test_core.py
python tests/test_geometry.py
python tests/test_i18n.py
python tests/simulacion/sim_ventana_visor_opengl.py
python tests/simulacion/sim_ventana_visor_imagen.py
```

- Las tres primeras no necesitan Qt ni OpenSCAD.
- Las `sim_*` usan un PySide6/pyqtgraph simulado y recorren la ventana completa (arranque con
  la rueda, crear, envolver, propiedades, deshacer, código a mano, clic 3D, medir, gizmo,
  explosión, exportar, guardar). No ven la API real de Qt ni el dibujo: después, abrir la
  aplicación de verdad. No ejecutarlas con pytest junto con Qt real.
- Un test nuevo debe comprobar el resultado (medidas, orientación, texto generado), no solo
  que exista un nodo. Antes de darlo por bueno, comprobar que falla con el error que protege.

## 6. Estado actual

- Cinta con 8 pestañas y 33 comandos (incluidas las matrices); árbol con multiselección, modificadores `# % ! *`,
  arrastrar y soltar, envolver, sacar, duplicar; propiedades generadas desde el catálogo.
- Código sincronizado con edición manual, ayuda de parámetros, autocompletado, búsqueda.
- Visor OpenGL: selección con clic, resaltado, medición, gizmo de traslación, colores de
  `color()`, vista explosionada por piezas del montaje (sobre la malla real, conserva los
  huecos), vista aproximada sin OpenSCAD. Visor de imágenes de respaldo.
- Asistente booleano, guía de operaciones con ajustes rápidos, variables globales,
  convertir selección en módulo, perfiles 2D paramétricos, lámina técnica A4/A3,
  piezas normalizadas (tornillos, tuercas, arandelas, insertos, rodamientos, perfiles 20xx).
- Interfaz en 6 idiomas con cobertura comprobada por `tests/test_i18n.py`.
- Ejecutable portable con PyInstaller (`build_portable.py`).

## 7. Limitaciones conocidas y siguientes pasos posibles

- Sin selección con clic en texto, `import`, `surface`, resultados de `hull`/`minkowski` ni
  piezas con valores no literales (no tienen malla aproximada).
- Sin colores en la exportación OFF de OpenSCAD, las caras de `hull`/`minkowski` salen grises.
- Los comentarios entre los argumentos de una llamada se pierden al regenerar.
- El asistente 2D es un formulario de perfiles; no hay croquis con restricciones.
- Falta elegir licencia y añadir `LICENSE`.
- Posibles mejoras: malla aproximada para `import` (STL/OFF), croquis 2D con restricciones.
