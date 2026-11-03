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
  se traducen con `tr()` a otros 5 idiomas. Los comentarios del código están en español, salvo
  los de los módulos de `library.py`, que se escriben en el `.scad` del usuario: esos, en inglés.
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
  gears.py                 engranajes, poleas, estriado, chaveteros, leva de disco y perfiles de lóbulo
  flanges.py               bridas ASME B16.5 / EN 1092-1: tablas, medidas, avisos y constructor
  camshaft.py              árbol de levas: reparto de lóbulos por cilindros y avisos del conjunto
  sketches.py              perfiles 2D paramétricos
  drawing.py               lámina técnica 2D (vistas en sistema europeo)
  operations.py            textos y ajustes rápidos de la guía de cada operación
  library.py               módulos propios (cube_edges, cylinder_edges) que se escriben en el .scad
  library_old.py           los mismos con los comentarios en español, para reconocer archivos viejos
  edges.py                 redondear/achaflanar: cube ↔ cube_edges, cylinder ↔ cylinder_edges
  radii.py                 r/d/r1/d1/r2/d2 sin choques (las reglas de prioridad de OpenSCAD)
  code_assist.py           plantillas, fragmentos y ayuda de parámetros del editor
  runner.py                QProcess que llama a openscad (única pieza de Qt fuera de ui/)
  i18n.py, locales/*.py    tr() y un diccionario por idioma (español → idioma)
scadgui/ui/                solo ventanas y diálogos (PySide6)
  mainwindow.py            ventana: cinta, árbol, propiedades, código, consola, deshacer, gizmo
  viewer3d.py / viewer.py  visor OpenGL (pyqtgraph) y visor de imágenes de respaldo
  codeview.py              editor de código
  properties.py, editors.py, boolean_dialog.py, hardware_dialog.py, sketch.py,
  drawing_dialog.py, module_dialog.py, operation_helper.py, preferences_dialog.py,
  flange_dialog.py, camshaft_dialog.py (asistentes de bridas y de árbol de levas),
  variables.py, style.py, icons.py
examples/                  rueda_con_eje_giratorio.scad, placa_agujeros.scad (menú Archivo; se arranca en blanco)
tests/test_core.py         modelo, parser, generador, tornillería, plano técnico, módulos…
tests/test_geometry.py     geometría, colores, OFF/STL, selección, explosión
tests/test_i18n.py         cobertura de traducciones
tests/test_openscad.py     pasa el código generado por el OpenSCAD real (se omite si no está)
tests/test_ventana_qt.py   eventos de ratón reales en la vista 3D con el Qt real (sin ventana)
tests/simulacion/          Qt/pyqtgraph simulados + 2 scripts que recorren la ventana
build_portable.py, OpenSCAD_GUI_Mejorada.spec   ejecutable portable con PyInstaller
CONTRIBUTING.md            guía en inglés para quien quiera modificar la aplicación (resumen de este archivo)
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
   `geometry.solid()`/`flat()` si tiene geometría). Un test exige 46 specs con icono (`test_catalogo_completo`).
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
   idioma activo al crear la pieza. También los comentarios de la lámina (`drawing.py`) y de las
   plantillas del editor (`code_assist.localized_code`, que traduce además los nombres de ejemplo
   de `SNIPPET_NAMES`). Los archivos de `locales/` se ordenan por `clave.lower()`.
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
14. **Módulos propios (`library.py`).** Si el modelo usa `cube_edges` o `cylinder_edges`,
    `generate()` añade su definición al final del archivo (también si la llamada quedó dentro
    de un `module` del usuario); `parse()` la quita si no se modificó, y si se modificó la
    conserva como `RawCode` y no la duplica. Una arista se nombra por la primitiva, no por la
    malla: "x1y1" es la vertical en X e Y máximos; "top"/"bottom" en el cilindro.
    Redondeo: `hull()` de una nube de puntos (un `polyhedron` con una sola cara que los usa
    todos): octante de esfera en las esquinas con tres aristas redondeadas, y en las demás la
    superficie de cada cilindro recortada por el otro. Chaflán: intersección de tres prismas.
    Lo que falló con CGAL ("assertion violation") y no hay que repetir: `difference` con
    máscaras curvas que se tocan tangentes, `hull` de hijos hechos con booleanas, un `for`
    dentro de `hull` (une los hijos antes), y una nube con puntos repetidos o alineados
    (por eso `unique()`, solo los extremos de cada tramo de cilindro y el radio a 0,9999 de la
    mitad del lado). La intersección de prismas da esquinas "pellizcadas" (cruce de tres
    cilindros), que fue lo que se vio en la primera versión.
    `geometry.cube_edges` es una aproximación por planos (las esferas con pocos planos).
15. **Comprobar el `.scad` con OpenSCAD real** (`tests/test_openscad.py`) cuando se toque
    `library.py` o la forma del código generado; hay que probar CGAL y Manifold.
16. **Cada cambio se guarda en git** (repositorio en esta carpeta). Un commit por cambio
    terminado y con las pruebas pasando.

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
- **CGAL:** ver la regla 14; probar siempre con muchas combinaciones de aristas al azar en
  los dos motores (`--backend=manifold` y el de por defecto), no solo con los casos bonitos.
- **Radios:** `r` de sphere/circle/cylinder es opcional con `initial=True` (la pieza nueva lo
  trae, pero se puede cambiar por `d`). Al activar un radio en el panel, `Document.set_param`
  parte del radio actual y `radii.normalize` quita el que sobra sin cambiar la forma; si el
  archivo ya trae radios que chocan, el panel avisa y ofrece «Corregir». Antes se podía dejar
  `r` y `d2` a la vez y OpenSCAD avisaba "Cylinder parameters ambiguous".
- **Gizmo:** la tolerancia para agarrar un eje va en píxeles de pantalla. Con una tolerancia en
  mm (4 % de la distancia de la cámara) el gizmo se comía los clics alrededor de la pieza y no
  se podía deseleccionar con un clic en el vacío. Pulsar un eje sin arrastrar cuenta como clic.
- **Elegir aristas:** se gana la candidata más cercana a la cámara, no la más cercana al ratón
  en ángulo; si no, desde arriba junto a un borde se elegía la arista de abajo.
- **Cambio de idioma:** todo widget que escribe un texto con `tr()` en su `__init__` necesita
  volver a escribirlo en un `retranslate_ui()` que la ventana llame. La barra del visor no lo
  tenía y se quedaba en el idioma anterior hasta reiniciar (arreglado en Viewer3D y Viewport;
  `test_barra_del_visor_cambia_de_idioma`).
- **Fines de línea:** los `.py` están en el repositorio con LF; README.md, los `.bat` y
  library_old.py con CRLF. En Windows, Python en modo texto escribe CRLF: al tocar archivos con un
  script, leer y escribir con `io.open(..., newline="")`, y comprobar con `git ls-files --eol`
  antes de confirmar (un diff de miles de líneas es eso). Un script de Python pasado por la
  entrada estándar de bash se lee en cp1252 y no encuentra los textos con tildes: mejor escribir
  el script en un archivo UTF-8 y ejecutarlo.
- **Traducciones nuevas:** se insertan en los 5 archivos de locales en su sitio alfabético sin
  reordenar el resto (los archivos no están estrictamente ordenados). Una traducción idéntica al
  español solo la rechaza `test_i18n` si el texto «parece español»; «Escape», «Uno», «Volume» valen.

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
- Las `sim_*` usan un PySide6/pyqtgraph simulado y recorren la ventana completa (arranque en
  blanco, crear, envolver, propiedades, deshacer, código a mano, clic 3D, medir, gizmo,
  explosión, exportar, guardar). No ven la API real de Qt ni el dibujo: después, abrir la
  aplicación de verdad. No ejecutarlas con pytest junto con Qt real.
- Un test nuevo debe comprobar el resultado (medidas, orientación, texto generado), no solo
  que exista un nodo. Antes de darlo por bueno, comprobar que falla con el error que protege.

## 6. Estado actual

- Cinta con 8 pestañas y 33 comandos (incluidas las matrices); aristas redondeadas o
  achaflanadas eligiéndolas en el visor (`cube_edges`, `cylinder_edges`); árbol con multiselección, modificadores `# % ! *`,
  arrastrar y soltar, envolver, sacar, duplicar; propiedades generadas desde el catálogo.
- Código sincronizado con edición manual, ayuda de parámetros, autocompletado, búsqueda.
- Árbol sobre el visor (`MainWindow.set_tree_overlay`): se cambia de sitio el MISMO
  `QTreeWidget` (con su barra de herramientas) al panel flotante del visor, no se copia; las
  propiedades se quedan en el panel Modelo. Se recuerda en la configuración (`tree_overlay`).
  Con el árbol en el visor, el contenido del panel Modelo (propiedades y # % ! *) flota a la
  derecha del visor (`props_overlay`, `_move_props_to_viewer`) y solo se ve con algo
  seleccionado (`_sync_model_panel`); el visor no cambia de tamaño. Modelo y Variables se ocultan.
  Ahí el fondo es transparente: iconos y textos pasan a colores claros (`TREE_COLORS[True]`,
  `tree_on_viewer`) porque el fondo del visor es oscuro; al cambiar se reconstruye el árbol.
- Tema claro / oscuro (`ui/style.py`, Ver › Tema oscuro, se guarda en `theme`, por defecto
  oscuro; se aplica al reiniciar). Los colores se escriben SOLO una vez, los del tema claro:
  `themed(css)` y `c(color, text=...)` los traducen al oscuro (tabla `DARK` y, si no está,
  inversión del brillo conservando el tono). Todo `setStyleSheet(...)` va con `themed(...)`,
  todo `QColor("#...")` con `c(...)` e `icon()` traduce solo; el visor 3D es oscuro siempre
  (`VIEWER_STYLES`, `icon(..., fixed=True)`). En oscuro se usa el estilo Fusion con
  `dark_palette()` para los controles que no cubre la hoja de estilos.
- Regla de los ejes (botón «Regla», tecla R, se guarda en `ruler`): `geometry.ruler(span)` da las
  marcas para el ancho visible (paso 1-2-5, se rehace al hacer zoom). Los números son GLTextItem,
  que se pintan encima de todo: `_hide_covered_labels` oculta los que tapa la pieza (rayo desde
  la cámara), al parar de girar. `_AxisTriad`: indicador de ejes abajo a la izquierda.
- Rejilla: menú Ver › Rejilla o tecla G en el visor (sin botón), se guarda en `grid`. El menú Ver
  se rellena en `_fill_view_menu()`, también al cambiar de idioma (antes se quedaba vacío).
- Gizmo: puntas en cono (`geometry.arrow_cone`), dibujado siempre encima de las piezas
  (`SEE_THROUGH` / `ON_TOP_SOLID`: sin profundidad y sin caras traseras). Ver › Flechas de
  arrastre (gizmo) y Preferencias usan la misma opción `gizmo_enabled`.
- Preferencias: TODA opción que se guarda debe leerse en algún sitio (`apply_settings`,
  `_openscad_args`, `_new_document`). Se colaron cinco sin usar; la prueba
  `test_preferencias_que_antes_no_hacian_nada` las cubre.
- Regla: `geometry.RayIndex` (grupos de triángulos con su caja) para saber qué números tapa la
  pieza; se rehace solo al cambiar la malla. Recorrer todos los triángulos tardaba ~1 s con 200k.
- Cabecera: el archivo conserva la de su idioma (`Document.header_lang`); el editor la muestra en
  el de la interfaz. Caras sin color() en el OFF de OpenSCAD: `UNCOLORED`, se pintan con el color
  por defecto del momento (esquema).
- Tema oscuro: casillas y botones de opción con borde y marca propios (`indicator_stylesheet`,
  SVG en la carpeta temporal); en claro la cinta lleva recuadros (`LIGHT_ONLY_STYLES`). Cambiar
  tema o visor ofrece «Reiniciar ahora» (`MainWindow.restart`, vuelve a abrir el archivo).
- Simulaciones (qtstub): `layout.count()` devuelve un objeto «verdadero»; no usar
  `while layout.count()` (cuelga la simulación), sino `for _ in range(int(layout.count()))`.
  El stub también toma `self.x ==` por una asignación: escribir `valor == self.x`.
- Botones: `clicked` pasa un bool; no conectar `clicked` directamente a un método con parámetros
  opcionales (`fit(box=None)` lo tomaba por la caja): usar `lambda: self.fit()`.
- Para ver el OpenGL real en el contenedor de pruebas: Xvfb + QT_QPA_PLATFORM=xcb (hace falta
  libxcb-cursor o un sustituto) y `view.grabFramebuffer()`; `window.grab()` no saca los textos 3D.
- Esquema de color del visor (Preferencias): `scadgui/colorschemes.py` con los colores de los
  JSON de OpenSCAD (`color-schemes/render`) más el propio (`DEFAULT`). `MainWindow.apply_color_scheme`
  lo aplica al visor OpenGL (fondo, color de piezas sin color(), rejilla y textos oscuros si el fondo
  es claro: `VIEWER_ON_LIGHT_STYLES`) y al de imágenes (`--colorscheme`). Los colores de las
  piezas (muestra del panel) NO pasan por `themed()`.
- Dentados (pestaña Mecánica): `spur_gear`, `helical_gear` y `rack`. Cada uno es un módulo
  propio en library.py (como cube_edges) con las MISMAS fórmulas repetidas en `scadgui/gears.py`
  para la vista aproximada, los datos del panel y los avisos. Si se cambia una, cambiar la otra:
  `test_openscad` compara el volumen de OpenSCAD con el de Python para los tres.
  - Recto: evolvente, diámetros por módulo, mínimo de dientes 2/sin²α, distancia m·(z1+z2)/2,
    giro de fase `mesh_rotation`.
  - Helicoidal: el módulo y el ángulo de presión que se dan son los NORMALES; en el plano de giro
    valen mt = m/cos ψ y tan αt = tan α/cos ψ, pero la cabeza y el pie se siguen midiendo con el
    módulo normal. El perfil del plano de giro sale del mismo núcleo (`_involute_polygon`) y se
    retuerce con `linear_extrude(twist=)`, que da el helicoide exacto. OJO con el signo: OpenSCAD
    gira en sentido HORARIO con twist positivo, así que la hélice a derechas lleva twist negativo
    (comprobado contra OpenSCAD real). La pareja va de MANO CONTRARIA, a m·(z1+z2)/(2·cos ψ);
    con la misma mano chocan, y hay pruebas que lo verifican en los dos sentidos.
  - Cónico (`bevel_gear`): Handbook p. 2087, "milled bevel gears". El ángulo del cono depende de
    los dientes de LAS DOS ruedas (tan α = sen Σ/(NG/NP + cos Σ)), por eso la pieza pide los de
    la pareja. El diente sale del engranaje virtual de Tredgold (recto, N/cos α dientes): un
    punto que en el virtual está a ρ del centro se lleva al cono α + atan((ρ−rv)/C) y su ángulo
    alrededor del eje se divide por cos α. Luego el perfil se BARRE HACIA EL VÉRTICE
    (`linear_extrude(scale=)`), lo que da los conos de cabeza, primitivo y pie exactos.
    La cara trasera es PLANA, en el plano donde el cono de cabeza llega al Ø exterior (la "vertex
    distance" J del Handbook): así el Ø exterior de la pieza es el D + 2·m·cos α de las tablas.
    El vértice va en el ORIGEN, así que la pareja es la misma pieza girada el ángulo entre ejes,
    sin trasladar. OJO: una versión anterior cerraba la cara trasera en abanico sobre el cono
    posterior; eso alargaba la pieza en punta hasta C/cos α y, además, CGAL no sabía intersecar
    dos de esos poliedros. El barrido simple arregla las dos cosas.
  - Cremallera: el «dentado básico» del sistema, de flancos rectos. Línea primitiva en y = 0,
    dientes hacia +Y, cada diente centrado en su paso (los huecos caen en los múltiplos del paso).
    Con un ángulo de presión grande el hueco acaba en V y el diente en punta: los dos casos están
    contemplados en el perfil y avisados en el panel.
  - Cremallera helicoidal: los parámetros `helix_angle` y `left_hand` del mismo `rack` (opcionales,
    así la recta no se llena de datos inútiles). El diente es una recta que forma el ángulo de
    hélice con el eje del engranaje, o sea que el perfil del plano de giro se SESGA tan ψ por mm
    de grueso (`multmatrix` en OpenSCAD, `prism(shift=…)` en la vista; las caras laterales siguen
    siendo planas, así que la diagonal da igual y las dos coinciden exactas). El paso y los flancos
    son los aparentes y la cabeza y el pie, el módulo normal, igual que en el helicoidal. OJO: la
    cremallera y su engranaje llevan LA MISMA mano (al revés que dos engranajes), comprobado en
    Python y en OpenSCAD real. Los extremos quedan al sesgo del dentado; recortarlos a escuadra
    pediría una intersección, y entonces la vista aproximada ya no coincidiría con el modelo.
  - `geometry.twisted_prism` parte el retorcido en rebanadas como OpenSCAD y usa SU misma diagonal
    al triangular las caras laterales (`_quads(flip=…)`, que depende del signo del giro), así que
    la vista aproximada pesa exactamente lo mismo que el modelo de verdad.
  - `Document.add_meshing_gear` sirve para los tres (translate + rotate tras la pieza); sobre una
    cremallera crea un `spur_gear`. Holgura por defecto 0.1 mm (impresión 3D).
  - Fuentes: Machinery's Handbook 27 («Gears and Gearing», «Helical Gearing» p. 2099, «Basic Rack
    of the 20-Degree and 25-Degree Full-Depth Involute Systems») y AGMA 908-B89 ec. 2 y 4; Casillas.
  - Polea dentada (`pulley`): no engrana con nada, así que no hay pareja ni verificación de
    interferencia; solo hay que acertar el perfil del hueco contra la tabla. Secciones clásicas
    ANSI/RMA IP-24 MXL/XL/L/H/XH (Machinery's Handbook 27, tabla 40 «Nominal Tooth and Section
    Dimensions» y tabla 44 «Standard Pulley Diameters», comprobadas contra la 44 en los tests).
    El hueco es el NEGATIVO del diente de la correa: paso, ángulo de diente y grueso en la línea
    primitiva (bt) salen de la tabla 40; Ø primitivo = dientes·paso/π; Ø exterior = Ø primitivo −
    2·PLD (el «pitch line differential» de la tabla 44, cuánto la primitiva queda por encima del
    lomo entre huecos). De flancos rectos, sin los redondeos ra/rr de la tabla (igual que la
    cremallera tampoco los lleva). No hay botón «Añadir pareja»: el centro entre dos poleas lo
    pone la longitud de la correa, que esta pieza no calcula.
    Pestañas (`flange`/`flange_height`, opcionales): sin ellas la correa se puede salir por el
    eje. Son un collar cilíndrico simple (sin chaflán) que sobresale `flange_height` del Ø
    exterior, a un lado, al otro o a los dos; se tallan sumando esa altura al bloque extruido
    (abajo, arriba o los dos) y restando luego el agujero del eje por toda la pieza, incluidas
    las pestañas. Con pestañas, el centrado (`center`) centra el TOTAL (pestañas + dentado), no
    solo el dentado.
    El valor de `flange` es un `Param(translated=True)`: el modelo guarda siempre el valor en español
    (`ninguna`, `superior`…), `Node.call(lang)` lo escribe traducido, `canonical_choice` lo reconoce
    en cualquier idioma al leer y el módulo `pulley` lista todas las traducciones, porque el archivo
    tiene que funcionar en el OpenSCAD normal. Si cambia una traducción, cambiar también esas listas
    (`test_flange_de_la_polea_en_el_idioma_elegido` lo comprueba) y guardar el módulo anterior en
    `PREVIOUS_VERSIONS`. Sigue a `header_lang`: un archivo que ya tiene idioma lo conserva al guardar.
  - Polea trapecial (`v_pulley`), correa en V: secciones clásicas ANSI/RMA IP-20 A/B/C/D
    (Machinery's Handbook 27, tabla 9 «Classical V-Belt Sheave and Groove Dimensions ANSI/RMA
    IP-20, 1988»; leída de la imagen de la página, no del texto extraído, porque `pdftotext`
    desordena esta tabla). Las variantes de muesca moldeada AX/BX/CX/DX comparten exactamente la
    misma ranura que su letra base, así que NO se modelan aparte; tampoco se ofrece la letra "Z"
    del sistema ISO, que esta tabla no trae. El ángulo de la ranura (α) y su ancho en la boca
    (`bg`) cambian por tramos según el Ø primitivo/datum elegido; la profundidad (`hg`), la
    separación entre ranuras (`Sg`) y el margen al borde (`Se`) son fijos por sección. El ancho
    de cara NO es un parámetro propio (a diferencia de `pulley`): sale solo de
    `Sg·(ranuras−1) + 2·Se`, la fórmula que trae la propia tabla. No se modela el redondeo del
    fondo de la ranura (`RB` de la tabla): queda con fondo plano, igual que la cremallera y la
    polea dentada tampoco llevan los suyos. A diferencia de todas las demás piezas mecánicas de
    este archivo (que son prismas con un contorno por capa), esta es una pieza DE REVOLUCIÓN: el
    perfil (radio, altura) se gira una sola vez alrededor de Z, como `rotate_extrude()`, usando
    el `geometry.revolve(poly, ctx)` ya existente (pensado para `rotate_extrude`, reutilizado
    aquí). Por eso su mesh-builder recibe `ctx` (como `cube_edges`/`cylinder_edges`), a diferencia
    de `pulley`/`spur_gear`/etc.
  - Cuñeros (`keyway`, y `key_width`/`key_depth` opcionales; en `spur_gear`, `helical_gear`,
    `bevel_gear`, `pulley` y `v_pulley`): cuñas paralelas métricas BS 4235-1, con las medidas de ISO
    R773 (Machinery's Handbook 27, tabla 12, p. 2376; la tabla 1 de ANSI B17.1 es en pulgadas y no se
    usa). La tabla está en `gears.KEY_TABLE` y en el módulo `shaft_bore`; un test exige que coincidan.
    Cada fila es «más de, hasta e incluido», así que Ø 6 no está en la tabla y Ø 8 es de la fila 6-8.
    El cuñero va hacia +X y su fondo queda a d/2 + t2 del eje (t2: profundidad en el cubo). Fuera de la
    tabla no se talla nada salvo que se den las dos medidas: nunca se toma la de otro Ø (regla 12).
    `shaft_bore` es el único módulo de `library.py` que usan otros, y por eso va el último en `LIBRARY`:
    `needed_definitions` busca también en lo que ya ha añadido. Los parámetros van al final de las
    firmas para no mover los argumentos posicionales de los archivos guardados. La vista aproximada
    no talla el agujero, así que tampoco el cuñero: solo se ve con la malla de OpenSCAD.
  - Estriado (`spline`): estrías métricas de evolvente de ajuste lateral, ANSI B92.2M-1980, derivada
    de ISO 4156 (Machinery's Handbook 27, tabla 13, p. 2179). En esa tabla `pdftotext -layout` mezcla
    las columnas; sin `-layout` salen en orden. Hay 4 columnas: 30° de fondo plano, 30° de fondo
    redondeado, 37,5° y 45°. Los coeficientes (por módulo) están en `gears.SPLINE_*` y en el módulo
    `spline`, y un test exige que coincidan. Módulos normales y rangos: 0,5-10, y 0,25-2,5 con 45°.
    Una sola pieza: `internal = true` es el cubo (`hub_d`; sin él, dos módulos de pared). El diente del
    eje y el hueco del cubo van centrados en +X, así que encajan en el mismo sitio y la pareja
    (`add_meshing_gear`) no lleva translate ni rotate. `clearance` es el es de la norma: solo adelgaza
    el eje y baja sus Ø mayor y menor es/tan α; el Ø menor del cubo siempre sale de la forma del
    ajuste H/h (nota b de la tabla). No se modelan los redondeos del fondo: «fondo redondeado» cambia
    los diámetros de la tabla, pero el fondo sale recto. Tampoco las clases de tolerancia 4-7 ni la tabla 14.
    El cubo se dibuja en la vista aproximada con `geometry.annular_prism`, la primera malla con hueco.
    Las estrías rectas SAE (tablas 18-21) están en pulgadas y no se ofrecen.
- Ranuras (diálogo de piezas normalizadas, `hardware.py`): solo existen como máscara de resta, sin
  módulo propio: una corona hecha con `difference` de dos `cylinder`, cada uno con su `$fn` (`GROOVE_FN`),
  porque un Ø de ranura no puede depender del `$fn` global. Las máscaras arrancan en z = 0 y hay que
  colocarlas a lo largo del eje; con una pieza seleccionada se restan de ella.
  - Anillos de retención: series métricas 3AM1 (eje) y 3BM1 (agujero) de ANSI B27.7-1977, Machinery's
    Handbook 27, tablas 1 y 2, pp. 1685-1686, extraídas con un script del texto del PDF. Manda G (Ø de
    la ranura); d es solo de referencia (la tabla lo dice), y un test comprueba S ∓ 2d ≈ G en cada fila.
    No están el anillo como sólido, las tolerancias, los radios de fondo ni la serie E (3CM1).
  - O-ring: «O-Rings», tablas 1 y 2 del Handbook (en pulgadas, fuente Auburn Manufacturing). La
    profundidad del alojamiento (gland depth F) va del fondo de la ranura a la superficie contra la
    que sella, así que el Ø de fondo sale del Ø de esa superficie (A − 2F o B + 2F) y no del de la pieza
    que lleva la ranura: la holgura no entra. Se usa la mitad del intervalo de la tabla. El ancho es
    el de sin anillos de apoyo. OJO: la ranura en cara plana NO está en el Handbook: usa los mismos
    ancho y profundidad estática, como aproximación.
- Asiento de rodamiento (`create_bearing_seat_node`, `bearing_seat`; mismo diálogo): es una ayuda para
  dimensionar: la ficha da el Ø del alojamiento, las clases del eje y los hombros, y la máscara corta
  el Ø medio, con la cara de la pieza en z = 0. Un cilindro de 96 lados no puede sostener una
  tolerancia de centésimas: lo que vale para mecanizar es la ficha. Fuentes:
  - Tolerancias: Machinery's Handbook 27, tablas 14, 15 y 17, pp. 2287-2290 (ABEC-1). El alojamiento
    empieza en más de Ø18 y el eje en más de Ø6: fuera de ahí, `ValueError` o aviso (regla 12). La tabla
    17 sale desordenada con `pdftotext`; solo se tomaron las clases cuyos valores coinciden con ISO 286.
    OJO: la elección j5/k5 del eje giratorio viene de la tabla 14, también desordenada; revisarla.
  - Serie 62xx y sus hombros: Shigley, 8.ª ed., tabla 11-2.
  - Series 60xx y 63xx: NO están en los manuales del proyecto (ISO 15, de memoria): comprobar en un catálogo.
  - Sin hombro en la tabla, el paso libre usa la media de d y D (aproximación propia). La holgura de
    impresión (+0.2, +0.35, +0.5) tampoco es de ninguna norma.
- Contraste del tema oscuro: `tests/test_tema.py` mide letra/fondo en cada regla. Un color que en
  claro es letra (DARK lo aclara) y alguna regla usa de fondo va en `DARK_BACKGROUND`.
- Pestaña **Mecánica** (categoría `"mech"` en catalog.CATEGORIES): grupos Engranajes, Transmisión,
  Levas (cam, camshaft_main_shaft, cam_lobe), Uniones (pipe_flange) y Asistentes (tornillería,
  bridas, árbol de levas). Sólidos 3D solo tiene las primitivas. La categoría solo decide la
  pestaña: no cambia el código guardado. Las piezas nuevas de la fase 4 van en Levas.
- Cinta: `Ribbon.GROUPS` reparte los botones de cada pestaña en grupos con título (marcados con
  `N_()` para que `test_i18n` exija su traducción); un comando nuevo sin grupo va al último.
- Atajos de vista como Blender (`viewer3d.VIEW_KEYS`), solo en el visor OpenGL: valen con el
  ratón encima salvo si el foco está en un campo de texto. La ortográfica se imita con fov 1°.
- Visor OpenGL: selección con clic, resaltado, medición, gizmo de traslación, colores de
  `color()`, vista explosionada por piezas del montaje (sobre la malla real, conserva los
  huecos), vista aproximada sin OpenSCAD. Visor de imágenes de respaldo.
- Asistente booleano, guía de operaciones con ajustes rápidos, variables globales,
  convertir selección en módulo, perfiles 2D paramétricos, lámina técnica A4/A3,
  piezas normalizadas (tornillos, tuercas, arandelas, insertos, rodamientos, perfiles 20xx).
- Interfaz en 6 idiomas con cobertura comprobada por `tests/test_i18n.py`.
- Ejecutable portable con PyInstaller (`build_portable.py`).
- **Bridas** (`flanges.py`, módulo `pipe_flange` de library.py, `ui/flange_dialog.py`, botón
  `pipe_flange` en Mecánica y asistente `flange_wizard` en Asistentes). Fuentes: ASME B16.5-2013
  (PDF del usuario, copia de IHS) y BS EN 1092-1:2018 (PDF del usuario); los PDF están en la carpeta
  del proyecto, fuera de git (`*.pdf` en `.gitignore`) y no se suben nunca: solo los valores, cada uno
  con su tabla. Lo decidido leyendo las normas:
  - ASME: tf e Y se miden desde la cara de la brida, sin el resalte (párr. 6.4.1 y 6.4.2.1, el
    prólogo de 2009 sobre tf y las figuras de las tablas 8 y 14); el resalte (2 mm en 150/300, 7 mm
    desde 400) va encima. Cara plana = tf sin resalte (párr. 6.3.2). Clase 400 de NPS ½ a 3½ usa
    la 600; clase 900 de ½ a 2½, la 1500 (notas de las tablas). El agujero de la brida de cuello lo
    fija el comprador salvo en 150/300 hasta NPS 12 (tubo de pared estándar): el asistente no deja
    insertar sin él. Los agujeros vienen en pulgadas (`inch_mm`).
  - EN: C incluye el resalte (fig. 4, nota 1); f1 por DN de la tabla 8 (2 hasta DN 32, 3 hasta 250,
    4 hasta 500, 5 desde 600), comprobado en la imagen porque son celdas unidas. Tipo 11: N1 en la
    cara trasera, A en la punta, H2 largo total, H3 tramo recto (fig. 8); agujero = A − 2·S. PN 6
    tiene una sola columna C2/C3 y PN 40 une C2 y C3 en una celda: el extractor lo trata.
  - Las tablas se extrajeron con PyMuPDF (posición de cada palabra, deshaciendo el giro de las
    páginas apaisadas de ASME y juntando las fracciones apiladas) y se compararon: el Ø exterior
    de la tabla de taladrado coincide con el de la de medidas en todas las filas, y
    `test_bridas_todas_las_medidas_son_coherentes_y_vuelven_igual` comprueba que ninguna de las
    más de 1000 bridas tenga agujeros que corten el cuello o el borde.
  - Sin MSS SP-44 (NPS 26 a 60, = B16.47 serie A): está gratis y legal en Public Resource
    (law.resource.org/pub/us/cfr/ibr/inc/ansi/mss.sp-44.2010.pdf), pero es un escaneo y las tablas
    de las clases altas salen ilegibles en texto; habría que leerlas de la imagen y comprobarlas.
  - Solo se probó con OpenSCAD 2021.01 (CGAL): `test_bridas_volumen_en_los_dos_motores` usa
    Manifold solo si la versión instalada tiene `--backend`.
- **Árbol de levas** (encargo del usuario en 6 fases; se entrega fase a fase y no se pasa a la
  siguiente sin su visto bueno). Decisión: no un archivo con variables globales arriba (perdería
  la selección en 3D, el panel y los avisos), sino piezas del modelo con los nombres de módulo del
  encargo: `camshaft_main_shaft` (eje a lo largo de Z, de 0 a length) y `cam_lobe` (lóbulo
  extruido en Z, centrado en `position`, punta hacia `angle`, reposo centrado en la punta, subida
  y bajada independientes, `step` grados por punto). Las leyes son las de la leva de disco
  (`gears.cam_motion`); `gears.lobe_polygon` es el mismo perfil que el módulo. Grupo propio en la
  cinta («Árbol de levas»). Ejemplo: `examples/arbol_de_levas.scad`.
  - Hecho: fase 1 (eje y lóbulo paramétrico), fase 2 (perfiles) y fase 3 (asistente). `profile` = "ley" (las leyes,
    con subida/reposo/bajada) o "circular", "excentrico", "eliptico" y "periforme" (`nose_r`):
    construcciones geométricas sin norma, todas con radio base y alzada exactos y hechas como
    envolvente convexa (`hull` de `circle`/`scale`, $fn = ceil(360/step)), así que no se cortan;
    `gears.lobe_polygon` repite los mismos vértices (envolvente propia, `_convex_hull`). Un perfil
    por ley es polar con r > 0 y tampoco se corta; `lobe_concave` avisa de tramos cóncavos.
    `lobe_opening` da la apertura real de cualquier perfil (>1 % de la alzada). El módulo de la
    fase 1 está en PREVIOUS_VERSIONS (tenía una variable interna llamada `profile`).
  - Fase 3: `camshaft.py` (sin Qt) reparte y comprueba; `ui/camshaft_dialog.py` es el asistente
    (botón `camshaft_wizard`, en Mecánica › Asistentes). Crea un `group()` con el eje y un
    `cam_lobe` por lóbulo, con nombres traducidos (Eje, Admisión n, Escape n, Leva n) y sus
    `position`/`angle` literales: no impone motor; el desfase entre cilindros se propone como
    360°/cilindros y el orden («1-3-4-2») solo decide qué cilindro recibe cada desfase. El panel
    del eje y de cada lóbulo avisa de solapes, lóbulos fuera del eje y radio base menor que el del
    eje, mirando las piezas del mismo contenedor (`camshaft.siblings`).
  - Pendiente: personalizado por funciones (las leyes ya cubren lo habitual; una función de
    OpenSCAD como parámetro sería un `Expr` sin vista aproximada); fase 4 (muñones, apoyos y
    extremos, reutilizando chavetero y estriado; esos parámetros entran como opcionales en
    `camshaft_main_shaft` para no romper archivos ya guardados); fase 5 (exportar por piezas y
    colocar para imprimir); fase 6 (casos al azar en los dos motores). Sin animación ni cinemática.

## 7. Limitaciones conocidas y siguientes pasos posibles

- Sin selección con clic en texto, `import`, `surface`, resultados de `hull`/`minkowski` ni
  piezas con valores no literales (no tienen malla aproximada).
- Sin colores en la exportación OFF de OpenSCAD, las caras de `hull`/`minkowski` salen grises.
- Los comentarios entre los argumentos de una llamada se pierden al regenerar.
- El asistente 2D es un formulario de perfiles; no hay croquis con restricciones.
- Licencia: GPL-3.0-or-later, la misma GPLv3 con que se publicó la primera versión (archivo `LICENSE`).
- Posibles mejoras: malla aproximada para `import` (STL/OFF), croquis 2D con restricciones.
- Árbol de levas, fase 4 (plan acordado): muñones como piezas propias (`camshaft_bearings`, una
  por muñón, con posición, Ø y longitud de apoyo) y extremos (`camshaft_ends`, uno por punta:
  liso, chavetero BS 4235-1 con la profundidad en el eje t1 de KEY_TABLE, estriado ANSI B92.2M
  reutilizando `spline`, o plato de arrastre geométrico sin norma). El asistente añade muñones
  (por defecto entre cilindros y en las puntas) y el tipo de cada extremo, y una opción de
  cojinetes enteros/partidos: con enteros, avisar si un muñón es menor que el lóbulo más alto
  (radio base + alzada), porque el árbol no pasaría. Avisos de solapes muñón-lóbulo y de muñones
  fuera del eje. Sin roscas, rodamientos (ya están en tornillería) ni cálculos.
- Traducir al inglés los comentarios y docstrings del código (~1 100 comentarios y ~1 000
  líneas de docstrings en 59 archivos) y este archivo: después de la fase 4, por zonas, un commit
  por zona, con una comprobación automática de que el árbol sintáctico de cada archivo, sin
  comentarios ni docstrings, no cambia. Se quedan en español a propósito los textos de `tr()` (son
  las claves de las traducciones) y los valores que ya se escriben en los `.scad` ("cicloidal",
  "periforme"…), salvo que el programa aprenda a aceptar las dos formas.
- Bridas pendientes: MSS SP-44 / ASME B16.47 serie A (NPS 26 a 60), B16.47 serie B (sin fuente),
  EN 1092-1 PN 2,5 y PN 160 a 400, tipos roscado, socket weld y lap joint, y los nombres DIN
  antiguos (DIN 2633, 2576…) como alias: la tabla de correspondencias está en el anexo nacional
  alemán, que no tenemos.
