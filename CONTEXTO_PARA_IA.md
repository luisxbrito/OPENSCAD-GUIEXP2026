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
  library.py               módulos propios (cube_edges, cylinder_edges) que se escriben en el .scad
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
  variables.py, style.py, icons.py
examples/                  rueda_con_eje_giratorio.scad, placa_agujeros.scad (menú Archivo; se arranca en blanco)
tests/test_core.py         modelo, parser, generador, tornillería, plano técnico, módulos…
tests/test_geometry.py     geometría, colores, OFF/STL, selección, explosión
tests/test_i18n.py         cobertura de traducciones
tests/test_openscad.py     pasa el código generado por el OpenSCAD real (se omite si no está)
tests/test_ventana_qt.py   eventos de ratón reales en la vista 3D con el Qt real (sin ventana)
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
- Dentados (Sólidos 3D › Mecánica): `spur_gear`, `helical_gear` y `rack`. Cada uno es un módulo
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
- Contraste del tema oscuro: `tests/test_tema.py` mide letra/fondo en cada regla. Un color que en
  claro es letra (DARK lo aclara) y alguna regla usa de fondo va en `DARK_BACKGROUND`.
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

## 7. Limitaciones conocidas y siguientes pasos posibles

- Sin selección con clic en texto, `import`, `surface`, resultados de `hull`/`minkowski` ni
  piezas con valores no literales (no tienen malla aproximada).
- Sin colores en la exportación OFF de OpenSCAD, las caras de `hull`/`minkowski` salen grises.
- Los comentarios entre los argumentos de una llamada se pierden al regenerar.
- El asistente 2D es un formulario de perfiles; no hay croquis con restricciones.
- Falta elegir licencia y añadir `LICENSE`.
- Posibles mejoras: malla aproximada para `import` (STL/OFF), croquis 2D con restricciones.
