"""Pruebas del núcleo (no necesitan PySide6 ni OpenSCAD).

Ejecutar:  python -m pytest tests   (o)   python tests/test_core.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scadgui.catalog import SPECS, CATEGORIES, ICONS, specs_in  # noqa: E402
from scadgui.model import Document, Expr, Node, RawCode, format_value, generate, make_node  # noqa: E402
from scadgui.parser import ParseError, literal, parse  # noqa: E402

EJEMPLO = """\
$fn = 64;

difference() { // Placa con agujeros
  cube([40, 30, 10], center = true); // Base
  translate([0, 0, 0]) { // Mover agujero
    cylinder(h = 12, r = 6, center = true); // Agujero central
  }
  // Agujeros laterales
  for (x = [-14, 14])
    translate([x, 10, 0]) cylinder(h = 12, r = 2, center = true);
}
"""


def roundtrip(text):
    return generate(parse(text), header=False).text


def test_catalogo_completo():
    assert len(SPECS) == 43  # 30 módulos de OpenSCAD + 3 matrices + 2 de aristas + 8 de mecánica
    for key, _, _ in CATEGORIES:
        assert specs_in(key), key
    for name in SPECS:
        assert name in ICONS, name


def test_formato_valores():
    assert format_value(10.0) == "10"
    assert format_value(0.1 + 0.2) == "0.3"
    assert format_value([1, 2.5, -3]) == "[1, 2.5, -3]"
    assert format_value(True) == "true"
    assert format_value('di "hola"') == '"di \\"hola\\""'
    assert format_value(Expr("x * 2")) == "x * 2"


def test_literales():
    assert literal("[1, -2, 3.5]") == [1, -2, 3.5]
    assert literal("true") is True
    assert literal('"a\\"b"') == 'a"b'
    assert literal("1e3") == 1000.0
    assert literal("x + 1") == Expr("x + 1")
    assert literal("1-2") == Expr("1-2")
    assert literal("[for (i=[0:3]) i]") == Expr("[for (i=[0:3]) i]")


def test_documento_y_generador():
    doc = Document(fn=64)
    base = doc.add("cube")
    base.params["size"] = [40, 30, 10]
    base.params["center"] = True
    hole = doc.add("cylinder")
    hole.params.update(h=12, r=6, center=True)
    diff = doc.wrap([hole.id, base.id], "difference")
    assert [c.id for c in diff.children] == [base.id, hole.id]  # orden del documento
    tr = doc.wrap([hole.id], "translate")
    gen = generate(doc)
    # el nombre por defecto es la palabra de OpenSCAD y no se repite como comentario
    assert "difference() {\n" in gen.text
    assert "cube([40, 30, 10], center = true);\n" in gen.text
    assert "translate([0, 0, 0]) {\n" in gen.text
    assert "cylinder(h = 12, r = 6, center = true);\n" in gen.text
    lines = gen.text.splitlines()
    a, b = gen.lines[hole.id]
    assert a == b and "cylinder" in lines[a]
    assert gen.node_at(a) == hole.id
    ta, tb = gen.lines[tr.id]
    assert ta < a <= tb


def test_nombres_unicos():
    doc = Document()
    assert doc.add("cube").name == "cube"
    assert doc.add("cube").name == "cube001"
    assert doc.add("cube").name == "cube002"
    assert "// cube001" in generate(doc).text


def test_nombres_tras_reabrir():
    """Al reabrir, un cube sin comentario se llama "cube" y la siguiente pieza no repite el nombre."""
    doc = Document()
    doc.add("cube")
    again = parse(generate(doc).text)
    assert again.children[0].label == "cube"
    assert again.add("cube").name == "cube001"
    assert again.duplicate(again.children[0].id).name == "cube002"


def test_operaciones_arbol():
    doc = Document()
    a, b, c = doc.add("cube"), doc.add("sphere"), doc.add("cylinder")
    assert doc.move(c.id, -1) and [n.id for n in doc.children] == [a.id, c.id, b.id]
    g = doc.wrap([a.id], "union")
    assert doc.indent(c.id) and c in g.children
    assert doc.outdent(c.id) and doc.children.index(c) == 1
    dup = doc.duplicate(b.id)
    assert dup.id != b.id and dup.name == "sphere001"
    assert doc.unwrap(g.id) and doc.children[0] is a
    doc.delete([a.id, b.id])
    assert [n.kind for n in doc.children] == ["cylinder", "sphere"]
    # añadir dentro de un contenedor seleccionado
    d = doc.wrap([doc.children[0].id], "difference")
    s = doc.add("sphere", target_id=d.id)
    assert s in d.children
    # arrastrar y soltar (reparent)
    c_node = d.children[0]
    # mover s antes de c_node
    assert doc.reparent([s.id], c_node.id, position="before")
    assert d.children == [s, c_node]
    # mover s después de c_node
    assert doc.reparent([s.id], c_node.id, position="after")
    assert d.children == [c_node, s]
    # sacar s a la raíz (into con target_id=None)
    assert doc.reparent([s.id], None, position="into")
    assert s in doc.children and s not in d.children
    # meter s de vuelta en d (into con target contenedor)
    assert doc.reparent([s.id], d.id, position="into")
    assert s in d.children
    # rechazar mover un contenedor dentro de su propio hijo
    assert not doc.reparent([d.id], s.id, position="into")
    assert not doc.reparent([d.id], s.id, position="before")
    # rechazar mover "into" una pieza no contenedora
    assert not doc.reparent([s.id], c_node.id, position="into")


def test_wrap_ignora_descendientes():
    doc = Document()
    a = doc.add("cube")
    t = doc.wrap([a.id], "translate")
    u = doc.wrap([t.id, a.id], "union")
    assert u.children == [t] and t.children == [a]


def test_resaltado_y_modificadores():
    doc = Document()
    a = doc.add("cube")
    b = doc.add("sphere")
    b.modifier = "%"
    text = generate(doc, highlight=[a.id, b.id]).text
    assert "#cube(" in text and "%sphere(" in text and "#%" not in text


def test_ida_y_vuelta_ejemplo():
    doc = parse(EJEMPLO)
    assert doc.fn == 64
    diff = doc.children[0]
    assert diff.kind == "difference" and diff.name == "Placa con agujeros"
    kinds = [type(c).__name__ + ":" + c.kind for c in diff.children]
    assert kinds == ["Node:cube", "Node:translate", "RawCode:__raw__", "RawCode:__raw__"]
    assert diff.children[0].params == {"size": [40, 30, 10], "center": True}
    assert diff.children[0].name == "Base"
    assert diff.children[1].children[0].name == "Agujero central"
    assert diff.children[2].is_comment
    loop = diff.children[3]
    assert loop.text.startswith("for (x = [-14, 14])\n  translate")
    once = roundtrip(EJEMPLO)
    assert roundtrip(once) == once  # estable
    assert "$fn = 64;" in once and "for (x = [-14, 14])" in once


def test_conserva_codigo_desconocido():
    src = """include <MCAD/boxes.scad>
use <otro.scad>
lado = 20; // variable
module pata(h) {
  cylinder(h = h, r = 2);
}
function doble(x) = x * 2;
if (lado > 10) cube(lado); else sphere(5);
pata(10);
/* bloque
   de comentario */
cube(size = doble(lado));
"""
    doc = parse(src)
    raws = [c for c in doc.children if isinstance(c, RawCode)]
    assert [r.text.split("\n")[0] for r in raws] == [
        "include <MCAD/boxes.scad>", "use <otro.scad>", "lado = 20; // variable",
        "module pata(h) {", "function doble(x) = x * 2;",
        "if (lado > 10) cube(lado); else sphere(5);", "pata(10);", "/* bloque"]
    last = doc.children[-1]
    assert last.kind == "cube" and last.params["size"] == Expr("doble(lado)")
    out = roundtrip(src)
    for fragment in ("include <MCAD/boxes.scad>", "module pata(h) {\n  cylinder(h = h, r = 2);\n}",
                     "else sphere(5);", "cube(doble(lado));", "   de comentario */"):
        assert fragment in out, fragment
    assert roundtrip(out) == out


def test_formas_encadenadas_y_posicionales():
    doc = parse("translate([1,2,3]) rotate([0,0,45]) cube(5, true);\nrotate(45) square(2);\n")
    t = doc.children[0]
    assert t.kind == "translate" and t.children[0].kind == "rotate"
    cube = t.children[0].children[0]
    assert cube.params == {"size": 5, "center": True}
    assert doc.children[1].params["a"] == 45
    assert roundtrip(roundtrip("translate([1,2,3]) cube(5);")) == "translate([1, 2, 3]) {\n  cube(5);\n}\n"


def test_modificadores_y_args_extra():
    doc = parse("#cube(1);\n%sphere(r = 3, $fn = 12);\n*cylinder(h = 1, r = 1, $fa = 5);\n")
    assert [c.modifier for c in doc.children] == ["#", "%", "*"]
    assert doc.children[1].params == {"r": 3, "$fn": 12}
    assert doc.children[2].params["$fa"] == 5
    assert "*cylinder(h = 1, r = 1, $fa = 5);" in roundtrip("*cylinder(h = 1, r = 1, $fa = 5);")


def test_llamadas_raras_quedan_como_codigo():
    doc = parse("cube(1, 2, 3, 4);\ncube(size = 1, size = 2);\ntranslate([1,0,0]);\n")
    assert isinstance(doc.children[0], RawCode)
    assert isinstance(doc.children[1], RawCode)
    assert doc.children[2].kind == "translate" and doc.children[2].children == []


def test_errores():
    for bad in ("difference() { cube(1);", "/* sin cerrar", 'text("abc);'):
        try:
            parse(bad)
        except ParseError:
            pass
        else:
            raise AssertionError(bad)
    # una llave de más no rompe: queda como código
    doc = parse("cube(1);\n}\n")
    assert isinstance(doc.children[1], RawCode)


def test_valores_por_defecto_generan_codigo_valido():
    doc = Document()
    for name, spec in SPECS.items():
        node = make_node(name)
        if spec.container:
            node.children.append(make_node("square" if spec.category in ("extrude", "shape2d") or name in ("fill", "roof") else "cube"))
        doc.children.append(node)
    text = generate(doc).text
    again = parse(text)
    assert all(not isinstance(c, RawCode) for c in again.children)
    assert generate(again).text == text


def test_asistente_bocetos_2d():
    from scadgui.sketches import create_sketch_node, PROFILES
    assert len(PROFILES) >= 6
    doc = Document()

    # 1. Rectángulo redondeado (offset + square)
    rr = create_sketch_node("rounded_rect", {"w": 40, "h": 25, "r": 3, "center": True}, doc.unique_name)
    assert rr.kind == "offset" and rr.params["r"] == 3
    assert rr.children[0].kind == "square" and rr.children[0].params["size"] == [34, 19]

    # 2. Ranura / chavetero (hull de 2 círculos trasladados)
    slot = create_sketch_node("slot", {"l": 30, "r": 5}, doc.unique_name)
    assert slot.kind == "hull" and len(slot.children) == 2
    assert slot.children[0].kind == "translate" and slot.children[0].children[0].kind == "circle"

    # 3. Polígono regular (círculo con $fn)
    poly = create_sketch_node("regular_polygon", {"n": 6, "r": 15}, doc.unique_name)
    assert poly.kind == "circle" and poly.params["$fn"] == 6

    # 4. Estrella paramétrica (polygon con 2*p vértices)
    star = create_sketch_node("star", {"p": 5, "r1": 20, "r2": 9}, doc.unique_name)
    assert star.kind == "polygon" and len(star.params["points"]) == 10

    # 5. Corona / anillo (difference de 2 círculos)
    ring = create_sketch_node("ring", {"r_ext": 20, "r_int": 12}, doc.unique_name)
    assert ring.kind == "difference" and len(ring.children) == 2

    # 6. Perfil en L (polygon de 6 vértices)
    lp = create_sketch_node("l_profile", {"w": 30, "h": 30, "t": 4}, doc.unique_name)
    assert lp.kind == "polygon" and len(lp.params["points"]) == 6

    # 7. Con extrusión 3D directa
    ext = create_sketch_node("rounded_rect", {"w": 30, "h": 20, "r": 2}, doc.unique_name, extrude_3d=True, extrude_h=12.5)
    assert ext.kind == "linear_extrude" and ext.params["height"] == 12.5
    assert ext.children[0].kind == "offset"

    # Ida y vuelta completa de todos los perfiles a código OpenSCAD
    doc.children.extend([rr, slot, poly, star, ring, lp, ext])
    code = generate(doc).text
    parsed = parse(code)
    assert len(parsed.children) == 7
    assert all(not isinstance(c, RawCode) for c in parsed.children)
    assert generate(parsed).text == code


def test_convertir_en_modulo():
    doc = Document()
    base = doc.add("cube")
    base.name = "Base"
    base.params["size"] = [40, 30, 10]
    tr = doc.add("translate")
    tr.name = "PosAgujero"
    tr.params["v"] = [0, 0, 5]
    cyl = doc.add("cylinder", target_id=tr.id)
    cyl.name = "Pivote"
    cyl.params["h"] = 12
    cyl.params["r"] = 6

    # 1. Recopilar parámetros candidatos
    params = doc.collect_module_parameters([base.id, tr.id])
    assert len(params) >= 3
    var_names = [p["suggested_name"] for p in params]
    assert any("size" in v for v in var_names)
    assert any("h" in v for v in var_names)

    # 2. Desactivar un parámetro para comprobar que se conserva literal
    for p in params:
        if p["param_key"] == "center":
            p["enabled"] = False

    # 3. Convertir en módulo
    mod_node, call_node = doc.make_module([base.id, tr.id], "soporte_pivote", params)
    assert isinstance(mod_node, RawCode)
    assert isinstance(call_node, RawCode)
    assert doc.children[0] is mod_node
    assert call_node in doc.children

    # 4. Código generado y roundtrip
    code = generate(doc).text
    assert "module soporte_pivote(" in code
    assert "soporte_pivote(" in code and "// Soporte Pivote" in code
    parsed = parse(code)
    assert len(parsed.children) == 2
    assert generate(parsed).text == code


def test_variables_globales():
    doc = Document()
    c = doc.add("cube")
    c.name = "Caja"

    # 1. Definir variables
    doc.set_variable("ancho", 50, "Ancho de la caja")
    doc.set_variable("alto", 25.5)
    assert len(doc.get_variables()) == 2
    assert doc.get_variables()[0]["name"] == "ancho"
    assert doc.get_variables()[0]["value"] == "50"
    assert doc.get_variables()[0]["comment"] == "Ancho de la caja"

    # 2. Asignar variable a un parámetro mediante Expr
    c.params["size"] = [Expr("ancho"), 30, Expr("alto")]

    # 3. Código generado y roundtrip
    code = generate(doc).text
    assert "ancho = 50; // Ancho de la caja" in code
    assert "alto = 25.5;" in code
    assert "cube([ancho, 30, alto]" in code
    parsed = parse(code)
    assert len(parsed.children) == 3
    assert generate(parsed).text == code

    # 4. Actualizar variable existente y eliminar
    doc.set_variable("ancho", 60, "Nuevo ancho")
    assert doc.get_variables()[0]["value"] == "60"
    assert doc.delete_variable("alto")
    assert len(doc.get_variables()) == 1


def test_generador_plano_tecnico():
    from scadgui.drawing import generate_technical_drawing_code

    modelo_ejemplo = "cube([20, 20, 10], center = true);"

    # 1. Lámina A4 estándar con todas las vistas y cajetín
    code_a4 = generate_technical_drawing_code(
        target_code=modelo_ejemplo,
        title="Pieza Mecánica",
        author="Ingeniero",
        sheet_size="A4",
        scale=1.0,
    )
    assert "module __modelo_base__()" in code_a4
    assert "cube([20, 20, 10]" in code_a4
    assert "Pieza Mecánica" in code_a4
    assert "Ingeniero" in code_a4
    assert "Escala: 1:1  ·  A4" in code_a4
    assert "square([297.0, 210.0])" in code_a4
    assert "ALZADO" in code_a4 and "PLANTA" in code_a4 and "PERFIL" in code_a4 and "ISOMÉTRICA" in code_a4
    assert "projection(cut = false)" in code_a4

    # 2. Lámina A3 con escala 1:2 y solo vistas frontal y superior sin marco
    code_a3 = generate_technical_drawing_code(
        target_code=modelo_ejemplo,
        title="Subensamblaje",
        sheet_size="A3",
        scale=0.5,
        views={"front": True, "top": True, "side": False, "isometric": False},
        include_border=False,
    )
    assert "square([420.0, 297.0])" not in code_a3
    assert "ALZADO" in code_a3 and "PLANTA" in code_a3
    assert "PERFIL" not in code_a3 and "ISOMÉTRICA" not in code_a3
    assert "scale([0.5, 0.5, 1])" in code_a3

    # 3. Comprobar que el código generado se parsea correctamente
    parsed = parse(code_a4)
    assert len(parsed.children) > 0


def test_componentes_estandar_industriales():
    from scadgui.hardware import (
        create_screw_node, create_nut_node, create_heat_set_node,
        create_washer_node, create_bearing_node, create_profile_node,
    )

    doc = Document()

    # 1. Tornillo Allen ISO 4762 M3x16 sólido y modo taladro
    screw_solid = create_screw_node("iso4762", "M3", 16.0, mode="solid", unique_fn=doc.unique_name)
    assert screw_solid.kind == "color"
    grp = screw_solid.children[0]
    assert grp.kind == "group"
    shank = grp.children[0]
    assert shank.kind == "cylinder" and shank.params["r"] == 1.5 and shank.params["h"] == 16.0

    screw_hole = create_screw_node("iso4762", "M3", 16.0, mode="hole", fit="medium", unique_fn=doc.unique_name)
    assert screw_hole.kind == "group"

    # 2. Tornillo hexagonal DIN 933 M4x20
    screw_hex = create_screw_node("din933", "M4", 20.0, mode="solid", unique_fn=doc.unique_name)
    assert screw_hex.kind == "color"

    # 3. Tornillo avellanado 90° ISO 10642 M3x12
    screw_csk = create_screw_node("iso10642", "M3", 12.0, mode="solid", unique_fn=doc.unique_name)
    assert screw_csk.kind == "color"

    # 4. Tuerca DIN 934 M3 sólida y modo cajeado
    nut_solid = create_nut_node("din934", "M3", mode="solid", unique_fn=doc.unique_name)
    assert nut_solid.kind == "color"
    nut_hole = create_nut_node("din934", "M3", mode="hole", unique_fn=doc.unique_name)
    assert nut_hole.kind == "group"

    # 5. Inserto térmico M3 para impresión 3D
    insert_solid = create_heat_set_node("M3", mode="solid", unique_fn=doc.unique_name)
    assert insert_solid.kind == "color" and insert_solid.params["c"] == "Gold"

    # 6. Arandela plana DIN 125 M3
    washer = create_washer_node("M3", unique_fn=doc.unique_name)
    assert washer.kind == "color"

    # 7. Rodamiento 608 (patinete / 3D)
    bearing_solid = create_bearing_node("608", mode="solid", unique_fn=doc.unique_name)
    assert bearing_solid.kind == "color"
    bearing_hole = create_bearing_node("608", mode="hole", unique_fn=doc.unique_name)
    assert bearing_hole.kind == "group"

    # 8. Perfil aluminio 2020
    prof = create_profile_node("2020", length=120.0, unique_fn=doc.unique_name)
    assert prof.kind == "color"

    # 9. Agregar todos al documento y comprobar generación y roundtrip
    doc.children.extend([screw_solid, screw_hole, screw_hex, screw_csk, nut_solid,
                         nut_hole, insert_solid, washer, bearing_solid, bearing_hole, prof])
    code = generate(doc).text
    assert "ISO4762" in code or "Tornillo" in code
    assert "Rodamiento" in code
    assert "Perfil 2020" in code

    parsed = parse(code)
    assert len(parsed.children) == len(doc.children)
    assert generate(parsed).text == code


def test_sistema_internacionalizacion_i18n():
    from scadgui.i18n import LANGUAGES, get_language, set_language, tr

    assert len(LANGUAGES) >= 6
    assert "es" in LANGUAGES and "en" in LANGUAGES and "de" in LANGUAGES

    # 1. Idioma por defecto es español
    set_language("es")
    assert get_language() == "es"
    assert tr("Nuevo") == "Nuevo"
    assert tr("Guardar") == "Guardar"

    # 2. Inglés
    set_language("en")
    assert get_language() == "en"
    assert tr("Nuevo") == "New"
    assert tr("Guardar") == "Save"
    assert tr("&Archivo") == "&File"
    assert tr("Preferencias…") == "Preferences…"
    assert tr("Configuración y Preferencias") == "Settings and Preferences"
    assert tr("Motor OpenSCAD") == "OpenSCAD Engine"
    assert tr("Visor 3D y Gizmo") == "3D Viewport and Gizmo"
    assert tr("Componentes y Planos") == "Components and Drawings"
    assert tr("Editor y Proyecto") == "Editor and Project"
    assert tr("Guardar preferencias") == "Save Preferences"
    assert tr("Automático (recomendado)") == "Automatic (recommended)"
    assert tr("Visor 3D OpenGL interactivo (recomendado)") == "Interactive OpenGL 3D Viewport (recommended)"

    # 3. Francés
    set_language("fr")
    assert tr("Nuevo") == "Nouveau"
    assert tr("Deshacer") == "Annuler"
    assert tr("Configuración y Preferencias") == "Paramètres et Préférences" or "Configuration" in tr("Configuración y Preferencias")
    assert tr("Guardar preferencias") == "Enregistrer les préférences"

    # 4. Alemán
    set_language("de")
    assert tr("Nuevo") == "Neu"
    assert tr("Deshacer") == "Rückgängig"
    assert tr("Guardar preferencias") == "Einstellungen speichern"

    # 5. Italiano
    set_language("it")
    assert tr("Nuevo") == "Nuovo"
    assert tr("Salir") == "Esci"
    assert tr("Guardar preferencias") == "Salva preferenze"

    # 6. Portugués
    set_language("pt")
    assert tr("Nuevo") == "Novo"
    assert tr("Guardar") == "Salvar"

    # 7. Fallback para textos desconocidos
    assert tr("Texto Desconocido Sin Traducir") == "Texto Desconocido Sin Traducir"

    # 8. Comprobar traducciones del editor de código, hints y parámetros
    set_language("en")
    assert tr("CÓDIGO OPENSCAD") == "OPENSCAD CODE"
    assert tr("+ Insertar bloque") == "+ Insert block"
    assert tr("Módulo OpenSCAD") == "OpenSCAD Module"
    assert tr("Altura (h)") == "Height (h)"
    assert tr("Cilindro") == "Cylinder"
    assert tr("Cubo") == "Cube"
    assert tr("Opcional") == "Optional"
    assert tr("Obligatorio") == "Required"

    # 9. Restaurar a español
    set_language("es")
    assert get_language() == "es"


def test_operaciones_booleanas_y_asistente():
    """Comprueba wrap_ordered, set_difference_base, get_solids y la lógica de operaciones booleanas."""
    doc = Document()
    c1 = doc.add("cube")
    c1.name = "CajaPrincipal"
    cyl1 = doc.add("cylinder")
    cyl1.name = "TaladroPaso"
    cyl2 = doc.add("cylinder")
    cyl2.name = "Avellanado"

    # 1. get_solids detecta todos los sólidos con sus etiquetas
    solids = doc.get_solids()
    assert len(solids) == 3
    ids = [s[0] for s in solids]
    labels = [s[1] for s in solids]
    assert c1.id in ids and cyl1.id in ids and cyl2.id in ids
    assert "CajaPrincipal" in labels and "TaladroPaso" in labels

    # 2. wrap_ordered respeta estrictamente el orden de los IDs pasados (Base al principio)
    # Ponemos cyl1 como base y c1 como lo que se resta a cyl1
    diff = doc.wrap_ordered([cyl1.id, c1.id, cyl2.id], "difference")
    assert diff.kind == "difference"
    assert len(diff.children) == 3
    assert diff.children[0].id == cyl1.id  # cyl1 es la base
    assert diff.children[1].id == c1.id    # c1 se resta
    assert diff.children[2].id == cyl2.id  # cyl2 se resta

    # 3. set_difference_base permite cambiar interactivamente quién es la base
    # Ahora queremos que CajaPrincipal (c1) sea la Base (+), y los dos cilindros sean las restas
    ok = doc.set_difference_base(diff.id, c1.id)
    assert ok is True
    assert diff.children[0].id == c1.id    # c1 ahora es la base en índice 0
    assert diff.children[1].id == cyl1.id  # cyl1 pasa a ser resta
    assert diff.children[2].id == cyl2.id  # cyl2 es resta

    # 4. Código generado
    gen = generate(doc, header=False)
    assert "difference() {" in gen.text
    assert "cube" in gen.text
    assert "cylinder" in gen.text


def test_operation_helpers():
    """Comprueba el catálogo de helpers y presets para las operaciones."""
    from scadgui.operations import OPERATION_HELPERS

    required_kinds = [
        "translate", "rotate", "scale", "mirror", "color",
        "difference", "union", "intersection",
        "linear_extrude", "rotate_extrude", "offset", "hull", "minkowski",
    ]
    for k in required_kinds:
        assert k in OPERATION_HELPERS, f"Falta helper para {k}"
        info = OPERATION_HELPERS[k]
        assert "title" in info and "summary" in info and "how_it_works" in info
        assert "example_code" in info and len(info["example_code"]) > 0

    # Comprobar presets de translate
    tr_presets = OPERATION_HELPERS["translate"]["presets"]
    assert len(tr_presets) >= 6
    x_plus_10 = next(fn for name, fn, _key in tr_presets if name == "X +10")
    res = x_plus_10({"v": [5.0, 0.0, 0.0]})
    assert res == [15.0, 0.0, 0.0]

    # Comprobar presets de rotate
    rot_presets = OPERATION_HELPERS["rotate"]["presets"]
    z_plus_90 = next(fn for name, fn, _key in rot_presets if "Z +90" in name)
    res_rot = z_plus_90({"a": [0.0, 0.0, 0.0]})
    assert res_rot[2] == 90.0


def test_codeview_snippets_y_plantillas():
    """Comprueba que los snippets y plantillas de código para el editor accesible estén completos."""
    from scadgui.code_assist import BOOLEAN_TEMPLATES, SNIPPETS_CATALOG

    # Plantillas booleanas
    assert "difference" in BOOLEAN_TEMPLATES
    assert "union" in BOOLEAN_TEMPLATES
    assert "intersection" in BOOLEAN_TEMPLATES
    for templ in BOOLEAN_TEMPLATES.values():
        assert templ.count("{") == templ.count("}")
        assert templ.count("(") == templ.count(")")

    # Catálogo de snippets
    assert len(SNIPPETS_CATALOG) >= 10
    for title, code in SNIPPETS_CATALOG:
        assert len(title) > 0
        assert len(code) > 0
        assert code.count("{") == code.count("}"), f"Snippet desbalanceado: {title}"
        assert code.count("(") == code.count(")"), f"Snippet desbalanceado: {title}"
        assert code.count("[") == code.count("]"), f"Snippet desbalanceado: {title}"


def test_codeview_signature_help_and_parameter_hints():
    """Comprueba el analizador y asistente de firmas/parámetros (Signature Help / Parameter Hints)."""
    from scadgui.code_assist import (
        OPENSCAD_BUILTINS,
        find_active_call,
        get_signature_info,
        format_signature_html,
    )

    # 1. Catálogo de built-ins
    assert len(OPENSCAD_BUILTINS) >= 25
    for fn in ("sin", "cos", "tan", "sqrt", "pow", "abs", "min", "max", "norm", "cross", "concat", "len", "str"):
        assert fn in OPENSCAD_BUILTINS, f"Falta built-in {fn}"

    # 2. Detección de llamada activa (find_active_call)
    code = "translate([sin(45), 0, 0]) cylinder(h = 10, r = 5, center = true);"

    # Cursor dentro de 'sin(45)'
    pos_sin = code.find("45") + 1
    call_sin = find_active_call(code, pos_sin)
    assert call_sin is not None
    assert call_sin[0] == "sin"
    assert call_sin[1] == 0

    # Cursor dentro de 'cylinder(h = 10, r = 5, center = true)' en 'r = 5'
    pos_r = code.find("r = 5") + 2
    call_cyl_r = find_active_call(code, pos_r)
    assert call_cyl_r is not None
    assert call_cyl_r[0] == "cylinder"
    assert call_cyl_r[1] == 1
    assert call_cyl_r[2] == "r"

    # Cursor dentro de 'center = true'
    pos_center = code.find("center") + 2
    call_center = find_active_call(code, pos_center)
    assert call_center is not None
    assert call_center[0] == "cylinder"
    assert call_center[1] == 2
    assert call_center[2] == "center"

    # Cursor fuera de cualquier llamada
    call_outside = find_active_call(code, len(code))
    assert call_outside is None

    # 3. Metadatos de firma (get_signature_info)
    # 3a. Para Spec nativo de OpenSCAD (cylinder)
    sig_cyl = get_signature_info("cylinder", 0, "r")
    assert sig_cyl is not None
    assert sig_cyl["name"] == "cylinder"
    assert sig_cyl["active_param"]["name"] == "r"
    assert sig_cyl["active_param"]["kind"] == "num"

    # 3b. Para función matemática nativa (sin)
    sig_sin = get_signature_info("sin", 0, None)
    assert sig_sin is not None
    assert sig_sin["name"] == "sin"
    assert sig_sin["active_param"]["name"] == "a"
    assert "grados" in sig_sin["active_param"]["label"].lower()

    # 3c. Para módulo de usuario definido en el script
    user_script = "module soporte(diametro = 25, alto = 15, tornillo = 3) {}"
    sig_user = get_signature_info("soporte", 1, None, user_script)
    assert sig_user is not None
    assert sig_user["name"] == "soporte"
    assert sig_user["active_param"]["name"] == "alto"
    assert sig_user["active_param"]["default"] == " = 15"

    # 4. Formato HTML
    sig_html, detail_html = format_signature_html(sig_cyl)
    assert "<b>cylinder</b>" in sig_html
    assert "r: num" in sig_html
    assert "background-color: #DBEAFE" in sig_html  # Resaltado del parámetro activo
    assert "Radio (r)" in detail_html


def test_rueda_con_eje_giratorio_ejemplo():
    """El modelo de inicio (rueda con eje giratorio) carga con sus 6 piezas y sin código suelto."""
    path = os.path.join(os.path.dirname(__file__), "..", "examples", "rueda_con_eje_giratorio.scad")
    assert os.path.isfile(path), "No se encuentra rueda_con_eje_giratorio.scad"
    with open(path, encoding="utf-8") as f:
        code = f.read()
    doc = parse(code)
    assert doc.fn == 64
    piezas = [n for n in doc.children if isinstance(n, Node)]
    assert len(piezas) == 6, f"Esperadas 6 piezas principales, se encontraron {len(piezas)}"
    nombres = [p.name for p in piezas]
    assert nombres == ["Rueda", "Buje", "Soporte", "Perno del eje", "Tuerca M6", "Poste giratorio"]
    # sin comentarios sueltos: todo el archivo se representa en el árbol
    assert not any(isinstance(n, RawCode) for n, _, _ in doc.walk())
    # un nombre por pieza como mucho, y ninguno repetido
    named = [n.name for n, _, _ in doc.walk() if n.name]
    assert len(named) == len(set(named))
    # al guardar, solo se añade la cabecera del programa
    assert generate(doc).text.strip().splitlines()[1:] == code.strip().splitlines()

    # Generación de código de vuelta sin pérdida
    code_gen = generate(doc).text
    doc2 = parse(code_gen)
    piezas2 = [n for n in doc2.children if isinstance(n, Node)]
    assert len(piezas2) == 6

    # Geometría y mallas fantasma
    from scadgui import geometry as geo
    ghosts = geo.build_ghosts(doc)
    assert len(ghosts) > 0, "No se generaron mallas fantasma para la rueda giratoria"


def test_variable_con_expresion_se_escribe_como_codigo():
    doc = Document()
    doc.set_variable("ancho", Expr("base * 2"), "doble de la base")
    doc.set_variable("alto", "")
    text = generate(doc, header=False).text
    assert "ancho = base * 2; // doble de la base" in text
    assert "Expr(" not in text
    assert "alto = undef;" in text  # "alto = ;" no sería OpenSCAD válido
    assert generate(parse(text), header=False).text == text


def _view_blocks(code):
    """Bloques translate([x, y]) { ... } de la lámina, con su rótulo y la matriz de sus rotate()."""
    import numpy as np
    from scadgui.geometry import node_matrix
    doc = parse(code)
    out = {}
    for n in doc.children:
        if not isinstance(n, Node) or n.kind != "translate" or len(n.children) != 2:
            continue
        label = n.children[1].children[0].params.get("text") if n.children[1].children else None
        m = np.eye(4)
        node = n.children[0]          # scale -> projection -> rotate -> rotate -> modelo
        while isinstance(node, Node) and node.children:
            if node.kind == "rotate":
                m = m @ node_matrix(node)
            node = node.children[0]
        out[label] = (n.params["v"], m[:3, :3])
    return out


def test_plano_tecnico_vistas_bien_orientadas_y_sistema_europeo():
    import numpy as np
    from scadgui.drawing import generate_technical_drawing_code
    views = _view_blocks(generate_technical_drawing_code("cube([30, 20, 10]);"))
    X, Y, Z = np.eye(3)

    def axes(label):
        """Qué dirección del mundo queda a la derecha y arriba en la hoja."""
        m = views[label][1]
        return m.T @ X, m.T @ Y

    right, up = axes("ALZADO")
    assert np.allclose(right, X) and np.allclose(up, Z)          # antes salía boca abajo
    right, up = axes("PLANTA")
    assert np.allclose(right, X) and np.allclose(up, Y)
    right, up = axes("PERFIL IZQUIERDO")
    assert np.allclose(right, -Y) and np.allclose(up, Z)         # antes salía tumbado
    right, up = axes("ISOMÉTRICA")
    assert up[2] > 0.8 and abs(right[2]) < 1e-6                  # Z hacia arriba, horizontal a nivel
    # sistema europeo: planta debajo del alzado, perfil izquierdo a su derecha
    (fx, fy), (tx, ty), (sx, sy) = (views[k][0][:2] for k in ("ALZADO", "PLANTA", "PERFIL IZQUIERDO"))
    assert fx == tx and ty < fy and sy == fy and sx > fx


def test_plano_tecnico_saca_use_del_modulo_y_escapa_textos():
    from scadgui.drawing import generate_technical_drawing_code
    code = generate_technical_drawing_code("use <lib.scad>\ncube(1);", title='Pieza "A" \\ 2')
    assert code.index("use <lib.scad>") < code.index("module __modelo_base__")
    assert 'text("Pieza \\"A\\" \\\\ 2", size = 4.5);' in code


def test_tornilleria_medidas_y_metricas_validas():
    from scadgui import hardware as hw
    # solo se ofrecen las métricas que existen en cada norma, y una inexistente es un error
    assert hw.available_sizes("screw", "iso7380")[0] == "M3"
    assert "M10" not in hw.available_sizes("screw", "iso10642")
    for bad in (lambda: hw.create_screw_node("iso10642", "M10"), lambda: hw.create_nut_node("din985", "M10")):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("una métrica fuera de la norma no debe cambiarse por M3")

    def nodes(root):
        stack = [root]
        while stack:
            n = stack.pop()
            yield n
            stack.extend(n.children)

    # ISO 7380 en modo taladro: paso de ISO 273 y cajeado, nunca el vástago macizo
    hole = hw.create_screw_node("iso7380", "M4", 20, mode="hole", fit="medium")
    radii = {n.params.get("r") for n in nodes(hole) if n.kind == "cylinder"}
    assert hw.CLEARANCE_HOLES_ISO_273["M4"]["medium"] / 2 in radii and 2.0 not in radii
    # el texto del diálogo da las mismas medidas que la pieza
    recess = next(n for n in nodes(hole) if n.name.startswith("Cajeado"))
    assert f"cajeado Ø{2 * recess.params['r']:g} mm" in hw.describe("screw", "iso7380", "M4", 20, "medium")[2]

    # perfil 2040: un taladro y dos ranuras por cada módulo de 20 mm, simétricos respecto al centro
    prof = hw.create_profile_node("2040", 50)
    bores = sorted(n.params["v"][1] for n in nodes(prof)
                   if n.kind == "translate" and n.children and n.children[0].kind == "cylinder")
    assert bores == [-10.0, 10.0]
    slots = [n for n in nodes(prof) if n.kind == "cube" and n.name.startswith("Ranura")]
    assert len(slots) == 6


def test_presets_admiten_rotate_con_angulo_escalar():
    from scadgui.operations import OPERATION_HELPERS
    presets = {name: fn for name, fn, _ in OPERATION_HELPERS["rotate"]["presets"]}
    assert presets["Z +90°"]({"a": 45}) == [0.0, 0.0, 135.0]   # rotate(45) gira en Z
    assert presets["X +90°"]({}) == [90.0, 0.0, 0.0]
    assert presets["Z +90°"]({"a": [0, 0, 300]}) == [0.0, 0.0, 30.0]


def test_nombres_de_asistentes_en_el_idioma_elegido():
    """Tornillería, bocetos y plano usan el idioma de la interfaz al crear la pieza."""
    from scadgui import hardware as hw
    from scadgui.drawing import generate_technical_drawing_code
    from scadgui.i18n import set_language
    from scadgui.sketches import create_sketch_node
    set_language("en")
    try:
        screw = hw.create_screw_node("iso4762", "M3", 16)
        assert screw.name == "Socket screw M3x16 ISO4762"
        names = [n.name for n, _, _ in Document(children=[screw]).walk() if n.name]
        assert "Shank M3" in names and "Hex socket" in names
        assert hw.describe("nut", "din985", "M4", 0, "medium")[0] == "Self-locking hex nut M4 DIN 985"
        slot = create_sketch_node("slot", {}, lambda s: s, extrude_3d=True)
        assert slot.name == "Slot extrusion"
        sheet = generate_technical_drawing_code("cube(10);")
        assert '"FRONT"' in sheet and '"LEFT SIDE VIEW"' in sheet and '"Technical drawing"' in sheet
        try:
            hw.create_nut_node("din934", "M99")
            raise AssertionError("debía fallar")
        except ValueError as exc:
            assert str(exc).startswith("Thread size M99 is not in the table")
    finally:
        set_language("es")
    assert hw.create_screw_node("iso4762", "M3", 16).name == "Tornillo M3x16 ISO4762"



def test_matrices_generan_for_y_se_reabren():
    doc = Document()
    base = doc.add("cube")
    arr = doc.wrap([base.id], "linear_array")
    pol = doc.add("polar_array")
    grid = doc.add("grid_array")
    text = generate(doc, header=False).text
    assert "for (i = [0 : 3]) translate(i * [20, 0, 0]) {\n  cube(" in text
    assert "for (i = [0 : 5]) rotate(a = i * 60, v = [0, 0, 1]) {}" in text
    assert "for (i = [0 : 2], j = [0 : 1]) translate(i * [20, 0, 0] + j * [0, 20, 0]) {}" in text
    again = parse(text)
    assert [n.kind for n in again.children] == ["linear_array", "polar_array", "grid_array"]
    assert again.children[0].params == {"n": 4, "step": [20, 0, 0]}
    assert again.children[0].children[0].kind == "cube"
    assert generate(again, header=False).text == text
    assert arr.call().startswith("for (") and pol.label == "polar_array" and grid.is_container


def test_matrices_con_variables_y_expresiones():
    """Una expresión compuesta va entre paréntesis para que i * (a + b) no sea i * a + b."""
    doc = Document()
    arr = doc.add("linear_array")
    arr.params.update(n=Expr("copias"), step=Expr("paso + [1, 0, 0]"))
    pol = doc.add("polar_array")
    pol.params.update(n=Expr("a ? 4 : 6"), angle=Expr("360 / copias"))
    text = generate(doc, header=False).text
    assert "for (i = [0 : copias - 1]) translate(i * (paso + [1, 0, 0]))" in text
    assert "for (i = [0 : (a ? 4 : 6) - 1]) rotate(a = i * (360 / copias), v = [0, 0, 1])" in text
    again = parse(text)
    assert again.children[0].params == {"n": Expr("copias"), "step": Expr("paso + [1, 0, 0]")}
    assert again.children[1].params["n"] == Expr("a ? 4 : 6")
    assert generate(again, header=False).text == text


def test_otros_for_se_conservan_como_codigo():
    src = ("for (i = [0 : 3]) cube(i);\n"
           "for (x = [0 : 2]) translate([x * 5, 0, 0]) cube(1);\n"
           "for (i = [0 : 2]) translate(i * [5, 0, 0]) rotate(i * 10) cube(1);\n")
    doc = parse(src)
    assert isinstance(doc.children[0], RawCode) and isinstance(doc.children[1], RawCode)
    # la cabecera encaja con una matriz; lo de dentro es un rotate normal
    assert doc.children[2].kind == "linear_array" and doc.children[2].children[0].kind == "rotate"
    assert generate(parse(roundtrip(src)), header=False).text == roundtrip(src)


def test_matrices_modificador_nombre_y_anidadas():
    src = ("#for (i = [0:2]) translate(i*[5,0,0]) { // Fila\n"
           "  for (i = [0 : 1]) translate(i * [0, 5, 0]) cube(1);\n"
           "}\n")
    doc = parse(src)
    outer = doc.children[0]
    assert outer.kind == "linear_array" and outer.modifier == "#" and outer.name == "Fila"
    assert outer.params["n"] == 3 and outer.children[0].kind == "linear_array"
    assert roundtrip(roundtrip(src)) == roundtrip(src)


def test_matrices_no_son_modulos_de_openscad():
    from scadgui.catalog import openscad_modules
    from scadgui.code_assist import get_signature_info
    assert "linear_array" not in openscad_modules() and "cube" in openscad_modules()
    assert get_signature_info("linear_array", 0, None) is None
    # "linear_array(...)" escrito a mano no es una matriz: se conserva como código
    assert isinstance(parse("linear_array(n = 3) cube(1);").children[0], RawCode)


def test_presets_matriz_polar():
    from scadgui.operations import OPERATION_HELPERS
    presets = {name: (fn, key) for name, fn, key in OPERATION_HELPERS["polar_array"]["presets"]}
    fn, key = presets["Repartir en 360°"]
    assert key == "angle" and fn({"n": 6}) == 60 and fn({"n": Expr("k")}) == 360
    assert presets["Repartir en 180°"][0]({"n": 5}) == 45  # extremos incluidos: 0, 45, ..., 180



def test_redondear_aristas_de_un_cubo():
    from scadgui.edges import finish_edges
    from scadgui.library import CUBE_EDGES
    doc = parse("cube([40, 30, 10], center = true); // Base\n")
    base = doc.children[0]
    assert finish_edges(doc, [(base.id, "x1y1"), (base.id, "x0y0")], "round", 3) == [base.id]
    assert base.kind == "cube_edges" and base.name == "Base"
    text = generate(doc, header=False).text
    assert text.startswith('cube_edges([40, 30, 10], center = true, edges = ["x0y0", "x1y1"], rounding = 3); // Base\n')
    assert text.count("module cube_edges(") == 1 and CUBE_EDGES in text   # la definición va al final
    again = parse(text)
    assert len(again.children) == 1 and again.children[0].params == base.params  # la definición no se ve
    assert generate(again, header=False).text == text
    # un solo valor por pieza; el chaflán sustituye al redondeo
    finish_edges(doc, [(base.id, "y1z1")], "chamfer", 1.5)
    assert base.params["edges"] == ["x0y0", "x1y1", "y1z1"] and base.params["chamfer"] == 1.5
    assert "rounding" not in base.params
    # quitar todas las aristas devuelve el cube original
    finish_edges(doc, [(base.id, k) for k in base.params["edges"]], "none", 0)
    assert base.kind == "cube" and base.params == {"size": [40, 30, 10], "center": True}
    assert "module" not in generate(doc).text


def test_redondear_bordes_de_un_cilindro():
    from scadgui.edges import finish_edges
    doc = parse("cylinder(h = 20, d = 16, $fn = 48);\ncylinder(h = 5, r1 = 4, r2 = 2);\n")
    cyl, cone = doc.children
    finish_edges(doc, [(cyl.id, "top")], "round", 2)
    assert cyl.kind == "cylinder_edges"
    assert cyl.call() == 'cylinder_edges(h = 20, r = 8, edges = ["top"], rounding = 2, $fn = 48)'
    try:
        finish_edges(doc, [(cyl.id, "bottom"), (cone.id, "top")], "round", 1)
        raise AssertionError("un cono no se puede redondear")
    except ValueError:
        pass
    assert cyl.params["edges"] == ["top"]            # el error no deja el modelo a medias
    try:
        finish_edges(doc, [(cyl.id, "top")], "round", 0)
        raise AssertionError("radio 0")
    except ValueError:
        pass
    v = parse("cylinder(h = 5, d = ancho + 2);").children[0]
    finish_edges(Document(children=[v]), [(v.id, "bottom")], "chamfer", 1)
    assert v.params["r"] == Expr("(ancho + 2) / 2")


def test_modulos_propios_y_modulo_de_usuario():
    from scadgui.edges import finish_edges
    doc = Document()
    c = doc.add("cube")
    finish_edges(doc, [(c.id, "x1y1")], "round", 1)
    # al convertir la pieza en módulo, la llamada queda dentro de un texto: la definición se añade igual
    doc.make_module([c.id], "pata", [])
    text = generate(doc).text
    assert text.count("module cube_edges(") == 1 and text.index("module pata(") < text.index("module cube_edges(")
    # una definición modificada a mano se conserva y no se duplica
    edited = text.replace("n = max(1, ", "n = max(2, ")
    assert edited != text
    again = parse(edited)
    assert any(isinstance(n, RawCode) and "module cube_edges(" in n.text for n in again.children)
    assert generate(again).text.count("module cube_edges(") == 1


def test_lista_de_textos_es_literal():
    assert literal('["x1y1", "top"]') == ["x1y1", "top"]
    assert literal('[]') == []
    assert isinstance(literal('["a", b]'), Expr)



def test_archivos_con_la_version_anterior_de_cube_edges_se_actualizan():
    """La primera versión dejaba las esquinas pellizcadas; al abrir un archivo guardado con ella
    se reconoce y se escribe la actual."""
    from scadgui.library import CUBE_EDGES, PREVIOUS_VERSIONS
    old = PREVIOUS_VERSIONS["cube_edges"][0]
    doc = parse('cube_edges([30, 30, 5], edges = ["x0y0"], rounding = 1);\n\n' + old + "\n")
    assert len(doc.children) == 1 and doc.children[0].kind == "cube_edges"
    text = generate(doc).text
    assert CUBE_EDGES in text and old not in text


def test_modulos_propios_con_comentarios_en_ingles():
    """Los comentarios de los módulos que se escriben en el archivo van en inglés, solo cambiaron
    los comentarios, y un archivo guardado con los de antes (en español) se actualiza al abrirlo."""
    import re
    from scadgui.library import LIBRARY
    from scadgui.library_old import SPANISH_COMMENTS

    def code_only(text):
        return " ".join(re.sub(r"//[^\n]*", "", text).split())

    assert set(SPANISH_COMMENTS) == set(LIBRARY) - {"shaft_bore", "spline", "pipe_flange"}   # nacieron en inglés
    for name, code in LIBRARY.items():
        assert all(c.isascii() for c in re.findall(r"//[^\n]*", code)), name
        assert "written by OpenSCAD GUI Mejorada" in code and "lo escribe" not in code, name
    for name, old in SPANISH_COMMENTS.items():
        code = LIBRARY[name]
        if name in ("cube_edges", "cylinder_edges", "rack"):  # los demás cambiaron también el código
            assert code_only(old) == code_only(code), name
        doc = parse(f"{name}();\n\n{old}\n")
        assert [n.kind for n in doc.children] == [name], name
        text = generate(doc).text
        assert code in text and "lo escribe" not in text, name


def test_asiento_de_rodamiento():
    """Series, tolerancias de las tablas 15 y 17 del Handbook, hombros de Shigley y máscara."""
    from scadgui import hardware as hw
    assert hw.BEARINGS_ISO["6204"] == {"d": 20.0, "D": 47.0, "B": 14.0}
    assert hw.BEARINGS_ISO["6219"] == {"d": 95.0, "D": 170.0, "B": 32.0}
    assert hw.BEARINGS_ISO["6005"]["D"] == 47 and hw.BEARINGS_ISO["6305"]["D"] == 62
    assert hw.BEARING_SHOULDERS["6204"] == {"r": 1, "ds": 25.0, "dH": 41.0}
    for model, s in hw.BEARING_SHOULDERS.items():       # cada hombro cae entre el eje y el exterior
        spec = hw.BEARINGS_ISO[model]
        assert spec["d"] < s["ds"] < s["dH"] < spec["D"], model
    d = hw.bearing_seat("6204", "H7")                    # Ø47: tramo 30-50
    assert (d["low"], d["high"], d["bore"]) == (47.0, 47.025, 47.0125) and d["through"] == 41
    assert hw.bearing_seat("6204", "M6")["high"] == 46.996
    assert hw.bearing_seat("608", "G7")["low"] == 22.007   # Ø22: tramo 18-30
    assert hw.bearing_seat("6010", "K6")["high"] == 80.004   # Ø80 todavía es del tramo 50-80
    p = hw.bearing_seat("608")                           # impreso, ajuste medio
    assert p["low"] == p["high"] == p["bore"] == 22.35 and p["through"] == 15   # media de 8 y 22
    try:
        hw.bearing_seat("624", "H7")                     # Ø13: la tabla empieza en 18
        raise AssertionError("una tolerancia fuera de la tabla no se sustituye")
    except ValueError as exc:
        assert "624" in str(exc)
    assert hw.bearing_seat("624")["bore"] == 13.35       # impreso, sí
    blind = hw.create_bearing_seat_node("6204", "H7")
    assert blind.kind == "group" and len(blind.children) == 1
    pocket = blind.children[0]
    assert pocket.params["v"] == [0.0, 0.0, -14.0] and pocket.children[0].params["h"] == 15
    assert pocket.children[0].params["$fn"] == hw.GROOVE_FN
    through = hw.create_bearing_seat_node("6204", "H7", 5)
    hole = through.children[1]
    assert hole.params["v"] == [0.0, 0.0, -20.0] and hole.children[0].params["r"] == 20.5
    assert hole.children[0].params["h"] == 7
    lines = hw.describe("bearing_seat", "seat", "6204", 0, "medium", seat="H7")
    assert "6204" in lines[0] and "47.025" in lines[1]
    assert "19.987" in lines[2] and "k5" in lines[2] and "20.011" in lines[2]
    assert "41" in lines[3]
    assert "j5" in hw.describe("bearing_seat", "seat", "608", 0, "medium")[2]      # Ø8 ≤ 18
    assert "6 mm" in hw.describe("bearing_seat", "seat", "624", 0, "medium")[2]    # Ø4: fuera de la tabla
    assert "15" in hw.describe("bearing_seat", "seat", "608", 0, "medium")[3]


def test_ranuras_de_anillo_de_retencion():
    """ANSI B27.7 (Handbook, tablas 1 y 2): medidas, coherencia de toda la tabla y máscara de resta."""
    from scadgui import hardware as hw
    a, b = hw.RETAINING_RINGS_3AM1, hw.RETAINING_RINGS_3BM1
    assert len(a) == 58 and len(b) == 83
    assert a["20"] == {"D": 18.35, "t": 1.1, "G": 18.85, "W": 1.2, "d": 0.58, "Z": 1.7}
    assert a["4"]["G"] == 3.8 and a["100"]["W"] == 2.95
    assert b["8"]["G"] == 8.4 and b["100"]["G"] == 106.3 and b["250"]["Z"] == 17.1
    for s, r in a.items():    # la ranura queda dentro del eje; el anillo libre, más estrecho que ella
        assert abs(float(s) - 2 * r["d"] - r["G"]) < 0.25 and r["D"] < r["G"] and r["t"] < r["W"], s
    for s, r in b.items():    # en el agujero, al revés
        assert abs(float(s) + 2 * r["d"] - r["G"]) < 0.25 and r["D"] > r["G"] and r["t"] < r["W"], s
    assert hw.available_sizes("ring_groove", "3bm1")[0] == "8"
    try:
        hw.create_ring_groove_node("3am1", "21.5")
        raise AssertionError("una medida fuera de la tabla no se sustituye")
    except ValueError as exc:
        assert "21.5" in str(exc)
    mask = hw.create_ring_groove_node("3am1", "20")
    outer, inner = mask.children[0], mask.children[1].children[0]
    assert mask.kind == "difference" and outer.params["r"] == 11 and inner.params["r"] == 9.425
    assert outer.params["h"] == 1.2 and outer.params["$fn"] == hw.GROOVE_FN
    mask = hw.create_ring_groove_node("3bm1", "20")
    assert mask.children[0].params["r"] == 10.575 and mask.children[1].children[0].params["r"] == 9
    lines = hw.describe("ring_groove", "3am1", "20", 0, "medium")
    assert "3AM1-20" in lines[0] and "18.85" in lines[1] and "1.7" in lines[2]


def test_ranuras_de_oring():
    """Handbook, «O-Rings», tablas 1 y 2: profundidad y ancho según la sección y el tipo de junta."""
    from scadgui import hardware as hw
    d = hw.oring_groove("2.62")
    assert d["w"] == 2.616 and d["gland"] == round(0.082 * 25.4, 3) and d["width"] == round(0.141 * 25.4, 3)
    assert d["squeeze"] == 20
    assert hw.oring_groove("2.62", "moving")["gland"] == round(0.089 * 25.4, 3)
    for size in hw.available_sizes("oring_groove"):
        for seal in ("static", "moving"):
            f = hw.oring_groove(size, seal)
            assert f["gland"] < f["w"] < f["width"], (size, seal)     # se aplasta y le sobra ancho
    try:
        hw.oring_groove("4")
        raise AssertionError("una sección fuera de la tabla no se sustituye")
    except ValueError:
        pass
    f = hw.oring_groove("2.62")["gland"]
    w = hw.oring_groove("2.62")["width"]
    mask = hw.create_oring_groove_node("shaft", "2.62", 30)        # eje que entra en un agujero de Ø30
    assert mask.children[0].params["r"] == 16 and mask.children[1].children[0].params["r"] == round(15 - f, 3)
    assert mask.children[0].params["h"] == w
    mask = hw.create_oring_groove_node("bore", "2.62", 30)         # agujero por el que pasa un eje de Ø30
    assert mask.children[0].params["r"] == round(15 + f, 3) and mask.children[1].children[0].params["r"] == 14
    mask = hw.create_oring_groove_node("face", "2.62", 30, "moving")   # en cara plana, siempre estática
    assert mask.kind == "translate" and mask.params["v"] == [0.0, 0.0, -f]
    ring = mask.children[0]
    assert ring.children[0].params["r"] == 15 and ring.children[1].children[0].params["r"] == round(15 - w, 3)
    assert ring.children[0].params["h"] == round(f + 1, 3)
    try:
        hw.create_oring_groove_node("shaft", "6.99", 5)
        raise AssertionError("un Ø que no da para la ranura es un error")
    except ValueError as exc:
        assert "6.99" in str(exc)
    lines = hw.describe("oring_groove", "shaft", "2.62", 0, "medium", 30)
    assert "Ø30" in lines[1] and "20 %" in lines[2]
    doc = Document()
    doc.children.append(hw.create_oring_groove_node("bore", "2.62", 30, unique_fn=doc.unique_name))
    again = parse(generate(doc).text)
    assert [n.kind for n in again.children] == ["difference"]      # se abre como piezas, no como código


def test_estriado_medidas_de_la_tabla_13():
    """ANSI B92.2M (Handbook, tabla 13): las cuatro columnas, la holgura y los coeficientes del módulo."""
    import math
    import re
    from scadgui import gears
    from scadgui.library import SPLINE
    d = gears.spline_dims(2, 20)                     # 30°, fondo plano
    assert d["pitch_d"] == 40 and abs(d["base_d"] - 34.641) < 1e-3 and abs(d["pitch"] - 6.2832) < 1e-3
    assert (d["major_e"], d["minor_e"], d["major_i"]) == (42, 37, 43)
    assert abs(d["form_e"] - 37.829) < 1e-3 and abs(d["minor_i"] - 38.229) < 1e-3 and abs(d["form_i"] - 42.4) < 1e-9
    assert d["hub_d"] == 51                          # sin Ø: dos módulos de pared a cada lado
    d = gears.spline_dims(2, 20, 30, True)           # 30°, fondo redondeado
    assert (d["major_e"], d["minor_e"], d["major_i"]) == (42, 36.4, 43.6)
    d = gears.spline_dims(2, 20, 37.5)
    assert abs(d["major_e"] - 41.8) < 1e-9 and abs(d["minor_e"] - 37.2) < 1e-9 and abs(d["major_i"] - 42.8) < 1e-9
    d = gears.spline_dims(2, 20, 45)
    assert abs(d["major_e"] - 41.6) < 1e-9 and abs(d["minor_e"] - 37.6) < 1e-9 and abs(d["major_i"] - 42.4) < 1e-9
    d = gears.spline_dims(2, 20, 30, False, 0.1)     # es: DEE y DIE bajan es/tan α; DII usa el H/h
    assert abs(d["major_e"] - (42 - 0.1 / math.tan(math.radians(30)))) < 1e-9
    assert abs(d["minor_i"] - gears.spline_dims(2, 20)["minor_i"]) < 1e-12
    k = re.search(r"k = (pressure_angle == 45.*?);\n", SPLINE, re.S).group(1)
    rows = [tuple(float(x) for x in r.split(",")) for r in re.findall(r"\[([\d., ]+)\]", k)]
    assert rows == [gears.SPLINE_45, gears.SPLINE_37_5, gears.SPLINE_FILLET_ROOT, gears.SPLINE_FLAT_ROOT]


def test_estriado_codigo_pareja_y_avisos():
    from scadgui import gears
    doc = Document()
    shaft = doc.add("spline")
    for key, value in (("mod", 2), ("clearance", 0.1)):
        doc.set_param(shaft.id, key, value)
    hub = doc.add_meshing_gear(shaft.id)
    assert [n.kind for n in doc.children] == ["spline", "spline"] and hub is doc.children[1]
    assert hub.params["internal"] is True and "clearance" not in hub.params   # la holgura es del eje
    assert hub.params["mod"] == 2
    doc.set_param(hub.id, "hub_d", 70)
    back = doc.add_meshing_gear(hub.id)
    assert "internal" not in back.params and "hub_d" not in back.params
    text = generate(doc).text
    assert "spline(mod = 2, teeth = 20, length = 20, pressure_angle = 30, internal = true, hub_d = 70" in text
    assert text.count("module spline(") == 1 and "shaft_bore" not in text
    again = parse(text)
    assert [n.kind for n in again.children] == ["spline"] * 3     # nada queda como código
    assert again.children[1].params["internal"] is True
    assert not gears.spline_warnings(2, 20)
    assert "serie" in gears.spline_warnings(2.2, 20)[0][0]
    assert "37,5" in gears.spline_warnings(2, 20, 35)[0][0]
    assert "módulo" in gears.spline_warnings(5, 20, 45)[0][0]     # 45° solo llega a módulo 2,5
    assert not gears.spline_warnings(5, 20, 30)
    assert "pared" in gears.spline_warnings(2, 20, 30, internal=True, hub_d=45)[0][0]
    assert not gears.spline_warnings(2, 20, 30, internal=True, hub_d=60)
    assert "holgura" in gears.spline_warnings(2, 20, clearance=3.2)[0][0]   # grueso básico: 3.14 mm
    assert not gears.spline_warnings(2, 20, clearance=0.1)


def test_cunero_medidas_de_la_tabla():
    """BS 4235 (Handbook, tabla 12): cada fila vale para «más de, hasta e incluido», las filas no
    dejan huecos, fuera de la tabla no se inventa una medida, y el módulo lleva los mismos datos."""
    import re
    from scadgui import gears
    from scadgui.library import SHAFT_BORE
    assert gears.keyway_size(8) == (2, 1)            # 8 todavía es de la fila 6-8
    assert gears.keyway_size(8.01) == (3, 1.4)
    assert gears.keyway_size(25) == (8, 3.3)
    assert gears.keyway_size(50) == (14, 3.8)
    assert gears.keyway_size(500) == (100, 19.5)
    assert gears.key_row(25)[3:5] == (7, 4)          # cuña 8 x 7, profundidad en el eje 4
    assert gears.keyway_size(6) is None and gears.keyway_size(501) is None   # 6 es «más de 6»
    assert gears.keyway_size(5, 2, 1) == (2, 1)      # a medida, fuera de la tabla
    assert gears.keyway_size(5, 2) is None           # falta la profundidad: no se saca de otra fila
    assert gears.keyway_size(25, 9) == (9, 3.3) and gears.keyway_size(25, 0, 4) == (8, 4)
    for low, high in zip(gears.KEY_TABLE, gears.KEY_TABLE[1:]):
        assert low[1] == high[0], (low, high)
    table = re.search(r"table = \[(.*?)\];", SHAFT_BORE, re.S).group(1)
    rows = [tuple(float(x) for x in r.split(",")) for r in re.findall(r"\[([^\[\]]+)\]", table)]
    assert rows == [(float(a), float(b), float(w), float(t2)) for a, b, w, _h, _t1, t2 in gears.KEY_TABLE]


def test_cunero_codigo_avisos_y_archivos_viejos():
    from scadgui import gears
    from scadgui.library import LIBRARY, PREVIOUS_VERSIONS
    for kind in ("spur_gear", "helical_gear", "bevel_gear", "pulley", "v_pulley"):
        doc = Document()
        first = doc.add(kind)
        doc.add(kind)
        doc.set_param(first.id, "bore", 20)
        doc.set_param(first.id, "keyway", True)
        text = generate(doc).text
        assert "bore = 20, keyway = true" in text, kind
        assert text.count(f"module {kind}(") == 1 and text.count("module shaft_bore(") == 1, kind
        again = parse(text)
        assert [n.kind for n in again.children] == [kind, kind], kind    # nada queda como código
        assert again.children[0].params["keyway"] is True, kind
        for old in PREVIOUS_VERSIONS[kind]:                  # un archivo de antes se actualiza
            updated = generate(parse(f"{kind}(bore = 8);\n\n{old}\n")).text
            assert LIBRARY[kind] in updated and old not in updated and "module shaft_bore(" in updated, kind
    assert "shaft_bore" not in generate(parse("rack();")).text       # la cremallera no tiene agujero
    assert gears.keyway_warnings(0, 0, 0, 40)                        # sin agujero
    assert "tabla" in gears.keyway_warnings(5, 0, 0, 40)[0][0]       # Ø fuera de la tabla
    assert not gears.keyway_warnings(5, 2, 1, 40)                    # a medida, sí vale
    assert not gears.keyway_warnings(20, 0, 0, 40)                   # sobran 40/2 - (10 + 2.8) mm
    assert "quedan" in gears.keyway_warnings(35, 0, 0, 40)[0][0]     # 20 - (17.5 + 3.3) < 0: se sale
    assert not gears.keyway_warnings(30, 0, 0, 40)                   # 20 - (15 + 3.3) = 1.7


def test_flange_de_la_polea_en_el_idioma_elegido():
    """El código lleva el valor en el idioma pedido, el modelo guarda siempre el mismo, y el módulo
    escrito en el archivo entiende todas las traducciones (si no, la pestaña desaparecería)."""
    from scadgui.catalog import SPECS
    from scadgui.geometry import pulley
    from scadgui.i18n import LANGUAGES, tr
    from scadgui.library import PREVIOUS_VERSIONS, PULLEY, library_name
    options = next(p for p in SPECS["pulley"].params if p.name == "flange").options
    for lang in LANGUAGES:
        names = [tr(o, lang) for o in options]
        assert len(set(names)) == len(options), (lang, names)   # dos valores no pueden confundirse
        for option in options:
            doc = Document()
            pu = doc.add("pulley")
            doc.set_param(pu.id, "flange", option)
            text = generate(doc, header_lang=lang).text
            assert f'flange = "{tr(option, lang)}"' in text, (lang, option)
            if option != "ninguna":
                assert f'"{tr(option, lang)}"' in PULLEY, (lang, option)
            again = parse(text)
            assert again.children[0].params["flange"] == option, (lang, option)
    en = parse('pulley(flange = "bottom", flange_height = 2);').children[0]
    es = parse('pulley(flange = "inferior", flange_height = 2);').children[0]
    assert en.params == es.params and pulley(en.params) is not None
    other = parse('pulley(flange = "otra");').children[0]
    assert other.params["flange"] == "otra"                     # lo desconocido no se pierde
    assert 'flange = "otra"' in generate(parse('pulley(flange = "otra");')).text
    assert library_name(PREVIOUS_VERSIONS["pulley"][0]) == "pulley"


def test_lamina_y_plantillas_en_el_idioma_elegido():
    """Los comentarios de la lámina y de las plantillas salen en el idioma de la interfaz."""
    from scadgui.code_assist import BOOLEAN_TEMPLATES, SNIPPETS_CATALOG, localized_code
    from scadgui.drawing import generate_technical_drawing_code
    from scadgui.i18n import set_language
    snippets = dict(SNIPPETS_CATALOG)
    assert localized_code(BOOLEAN_TEMPLATES["difference"]) == BOOLEAN_TEMPLATES["difference"]   # español
    assert "// BASE SOLID (the one subtracted from):" in localized_code(BOOLEAN_TEMPLATES["difference"], "en")
    assert "SÓLIDO" not in localized_code(BOOLEAN_TEMPLATES["difference"], "en")
    assert localized_code(snippets["Cubo (cube)"], "de").endswith("// Würfel")
    assert "// Hole" in localized_code(snippets["Restar (difference)"], "en")
    module = localized_code(snippets["Módulo de usuario"], "de")
    assert "module mein_teil(breite = 20, hoehe = 10)" in module and "cube([breite, breite, hoehe]" in module
    set_language("en")
    try:
        sheet = generate_technical_drawing_code("cube(10);")
    finally:
        set_language("es")
    assert sheet.startswith("// Technical drawing sheet generated with OpenSCAD GUI Mejorada")
    assert "// --- Outer frame and margin ---" in sheet and "// --- Title block ---" in sheet
    assert "// --- 2D projections (first-angle system) ---" in sheet
    assert "Lámina" not in sheet and "Cajetín" not in sheet and "Marco" not in sheet



def test_radios_sin_avisos_de_openscad():
    from scadgui import geometry as g
    from scadgui.radii import conflicts
    ctx = {"fn": 32, "fa": 12, "fs": 2}
    doc = Document()
    cyl = doc.add("cylinder")                                  # h = 10, r = 5
    doc.set_param(cyl.id, "d2", 4)                             # activar d2 en el panel (valor por defecto 4)
    assert cyl.params == {"h": 10, "r1": 5, "d2": 10, "center": False}   # misma forma: no cambia nada
    assert conflicts(cyl) == []
    doc.set_param(cyl.id, "d2", 4)                             # ahora sí la tapa
    doc.set_param(cyl.id, "r", 5)                              # volver a un cilindro recto
    assert cyl.params == {"h": 10, "r": 5, "center": False}
    sph = doc.add("sphere")
    doc.set_param(sph.id, "d", 20)
    assert sph.params == {"d": 20}
    # archivo con radios que chocan (como el de la prueba del usuario): se avisa y se corrige
    bad = parse("cylinder(h = 10, r = 1, d2 = 4, center = true);").children[0]
    doc2 = Document(children=[bad])
    before = g.signed_volume(g.solid(bad, ctx)[bad.id])
    assert len(conflicts(bad)) == 1
    assert doc2.fix_radii(bad.id)
    assert bad.call() == "cylinder(h = 10, r1 = 1, d2 = 4, center = true)" and conflicts(bad) == []
    assert abs(g.signed_volume(g.solid(bad, ctx)[bad.id]) - before) < 1e-9
    # editar un radio de una pieza que ya traía el choque también lo corrige
    cone = parse("cylinder(h = 5, r = 1, d2 = 6, center = true);").children[0]
    Document(children=[cone]).set_param(cone.id, "d2", 5)
    assert cone.call() == "cylinder(h = 5, r1 = 1, d2 = 5, center = true)"
    both = parse("sphere(r = 3, d = 10);").children[0]
    Document(children=[both]).set_param(both.id, "r", 4)     # se edita r: se queda r
    assert both.params == {"r": 4}
    c = parse("circle(r = 3, d = 10);").children[0]
    assert Document(children=[c]).fix_radii(c.id) and c.params == {"d": 10}



def test_cabecera_en_el_idioma_de_la_interfaz():
    """La línea "// Generado con…" sigue el idioma de la interfaz y se reconoce en cualquiera al abrir."""
    from scadgui.i18n import get_language, set_language
    from scadgui.model import header_line
    before = get_language()
    try:
        set_language("es")
        assert generate(parse("cube(5);")).text.startswith("// Generado con OpenSCAD GUI Mejorada\n")
        set_language("en")
        text = generate(parse("cube(5);")).text
        assert text.startswith("// Generated with OpenSCAD GUI Mejorada\n"), text
        for lang in ("es", "fr", "de"):   # un archivo guardado en otro idioma no acumula cabeceras
            doc = parse(header_line(lang) + "\ncube(5);\n")
            assert not any(isinstance(n, RawCode) for n in doc.children), doc.children
            assert generate(doc).text.count("OpenSCAD GUI Mejorada") == 1
    finally:
        set_language(before)


def test_cabecera_del_archivo_no_cambia_con_el_idioma():
    """Abrir un archivo con la cabecera en francés y guardarlo con la interfaz en inglés la deja en
    francés (el archivo no cambia); el editor la muestra en el idioma de la interfaz."""
    from scadgui.i18n import get_language, set_language
    from scadgui.model import header_line
    before = get_language()
    try:
        doc = parse(header_line("fr") + "\ncube(5);\n")
        assert doc.header_lang == "fr"
        set_language("en")
        assert generate(doc).text.startswith(header_line("en"))                         # editor
        assert generate(doc, header_lang=doc.header_lang).text.startswith(header_line("fr"))   # archivo
        assert doc.snapshot().header_lang == "fr"
        assert parse("cube(5);").header_lang is None
    finally:
        set_language(before)


def test_engranaje_y_su_pareja():
    """«Añadir engranaje que engrane»: misma pieza, otros dientes, a m·(z1+z2)/2 y en fase."""
    doc = Document()
    g = doc.add("spur_gear")
    doc.set_param(g.id, "mod", 2)
    doc.set_param(g.id, "bore", 6)
    new = doc.add_meshing_gear(g.id, 31)
    shift = doc.children[1]
    assert shift.kind == "translate" and shift.params["v"] == [51, 0, 0]
    assert shift.children[0].kind == "rotate" or shift.children[0] is new        # 31 dientes: impar, sin giro
    assert new.params["teeth"] == 31 and new.params["mod"] == 2 and new.params["bore"] == 6
    new2 = doc.add_meshing_gear(g.id, 20)                                         # par: girado 9°
    assert doc.children[1].children[0].params["a"] == [0, 0, 9]
    text = generate(doc).text
    assert text.count("module spur_gear(") == 1                                   # la definición, una vez
    again = parse(text)
    assert generate(again).text == text                                           # ida y vuelta
    assert [n.kind for n in again.children] == ["spur_gear", "translate", "translate"]
    try:
        doc.add_meshing_gear(doc.children[1].id)
        raise AssertionError("debería rechazar algo que no es un engranaje")
    except ValueError:
        pass
    assert new2.params["teeth"] == 20


def test_helicoidal_y_su_pareja_de_mano_contraria():
    """La pareja de un helicoidal va a m·(z1+z2)/(2·cos ψ) y con la hélice al revés."""
    import math
    doc = Document()
    g = doc.add("helical_gear")
    for key, value in (("mod", 2), ("helix_angle", 30), ("bore", 6)):
        doc.set_param(g.id, key, value)
    new = doc.add_meshing_gear(g.id, 40)
    shift = doc.children[1]
    assert shift.kind == "translate"
    assert abs(shift.params["v"][0] - 2 * 60 / (2 * math.cos(math.radians(30)))) < 1e-5
    assert shift.children[0].params["a"] == [0, 0, 4.5]              # 40 dientes: par, medio paso
    assert new.params["teeth"] == 40 and new.params["left_hand"] is True
    assert new.params["helix_angle"] == 30 and new.params["bore"] == 6
    assert doc.add_meshing_gear(new.id, 20).params["left_hand"] is False   # y la de esa, otra vez a derechas
    text = generate(doc).text
    assert text.count("module helical_gear(") == 1
    assert "left_hand = true" in text
    again = parse(text)
    assert generate(again).text == text                              # ida y vuelta


def test_conico_y_su_pareja_girada_el_angulo_entre_ejes():
    """La pareja de un cónico se crea girada, sin mover: los dos comparten el vértice del cono."""
    doc = Document()
    g = doc.add("bevel_gear")
    for key, value in (("mod", 2), ("teeth", 15), ("mate_teeth", 30), ("face_width", 8)):
        doc.set_param(g.id, key, value)
    new = doc.add_meshing_gear(g.id)                                 # sin decir dientes: los de la pareja
    assert new.params["teeth"] == 30 and new.params["mate_teeth"] == 15
    turn = doc.children[1]
    assert turn.kind == "rotate" and turn.params["a"] == [0, 90, 0]   # inclinada, no movida
    assert turn.children[0].params["a"] == [0, 0, 6]                  # 30 dientes: medio paso
    assert all(n.kind != "translate" for n in doc.children)
    text = generate(doc).text
    assert text.count("module bevel_gear(") == 1
    again = parse(text)
    assert generate(again).text == text                               # ida y vuelta
    assert [n.kind for n in again.children] == ["bevel_gear", "rotate"]


def test_cremallera_con_su_engranaje():
    """La cremallera lleva el engranaje a su radio primitivo de altura y en el centro de un hueco."""
    import math
    doc = Document()
    r = doc.add("rack")
    doc.set_param(r.id, "mod", 2)
    doc.set_param(r.id, "teeth", 8)
    new = doc.add_meshing_gear(r.id, 25)
    shift = doc.children[1]
    assert new.kind == "spur_gear" and new.params["teeth"] == 25
    assert new.params["mod"] == 2 and new.params["backlash"] == 0.1   # hereda lo que comparten
    assert "base" not in new.params                                   # y no lo que no comparten
    assert abs(shift.params["v"][0] - 4 * math.pi * 2) < 1e-5         # un hueco de la mitad
    assert shift.params["v"][1] == 25                                 # m·z/2 de altura
    text = generate(doc).text
    assert text.count("module rack(") == 1 and text.count("module spur_gear(") == 1
    again = parse(text)
    assert generate(again).text == text
    assert [n.kind for n in again.children] == ["rack", "translate"]


def test_cremallera_helicoidal_pide_un_helicoidal_de_la_misma_mano():
    import math
    doc = Document()
    r = doc.add("rack")
    for key, value in (("mod", 1), ("teeth", 12), ("thickness", 10), ("helix_angle", 20)):
        doc.set_param(r.id, key, value)
    new = doc.add_meshing_gear(r.id, 20)
    assert new.kind == "helical_gear" and new.params["helix_angle"] == 20
    assert new.params["left_hand"] is False                          # la misma mano que la cremallera
    mt = 1 / math.cos(math.radians(20))
    shift = doc.children[1].params["v"]
    assert abs(shift[0] - 6 * math.pi * mt) < 1e-5                   # paso aparente, no el normal
    assert abs(shift[1] - mt * 20 / 2) < 1e-5
    doc.set_param(r.id, "left_hand", True)
    assert doc.add_meshing_gear(r.id, 20).params["left_hand"] is True
    text = generate(doc).text
    assert text.count("module rack(") == 1 and text.count("module helical_gear(") == 1
    assert generate(parse(text)).text == text                        # ida y vuelta


def test_polea_dentada_medidas_del_handbook():
    """Comprueba Ø primitivo y Ø exterior contra la tabla 44 del Handbook (XL, N=20)."""
    import math
    from scadgui import gears
    d = gears.pulley_dims("XL", 20)
    assert abs(d["pitch_d"] - 20 * 5.08 / math.pi) < 1e-6
    assert abs(d["pitch_d"] - 32.334) < 0.05      # tabla 44: 1.273 in = 32.334 mm
    assert abs(d["outer_d"] - 31.826) < 0.05      # tabla 44: 1.253 in = 31.826 mm
    assert d["tip_half"] > 0                       # el hueco no acaba en punta
    # Con muy pocos dientes el aviso de borde a filo debe saltar.
    assert gears.pulley_warnings("XH", 3)


def test_polea_dentada_codigo_y_vuelta():
    doc = Document()
    pu = doc.add("pulley")
    for key, value in (("section", "XL"), ("teeth", 20), ("width", 6), ("bore", 5),
                       ("flange", "ambas"), ("flange_height", 2)):
        doc.set_param(pu.id, key, value)
    text = generate(doc).text
    assert text.count("module pulley(") == 1
    assert 'section = "XL"' in text and 'flange = "ambas"' in text
    again = parse(text)
    assert generate(again).text == text              # ida y vuelta
    assert [n.kind for n in again.children] == ["pulley"]

def test_polea_trapecial_medidas_del_handbook():
    """Comprueba ángulo y boca de ranura contra la tabla 9 del Handbook (sección A)."""
    from scadgui import gears
    d = gears.v_pulley_dims("A", 80, 3)            # Ø 80 <= 137.16 in -> tramo de 34°
    assert d["groove_angle"] == 34.0
    assert abs(d["groove_width"] - 12.5476) < 1e-6  # tabla 9: bg = 0.494 in = 12.5476 mm
    assert abs(d["groove_depth"] - 11.684) < 1e-6   # tabla 9: hg mín = 0.460 in = 11.684 mm
    assert abs(d["face_width"] - (15.875 * 2 + 2 * 9.525)) < 1e-6   # Sg*(ranuras-1) + 2*Se
    d2 = gears.v_pulley_dims("A", 300, 3)           # por encima del tramo -> 38°
    assert d2["groove_angle"] == 38.0
    assert d["bottom_half"] > 0                     # fondo plano, no en punta
    # Con un Ø por debajo del mínimo recomendado el aviso debe saltar.
    assert gears.v_pulley_warnings("A", 50, 1)


def test_polea_trapecial_codigo_y_vuelta():
    doc = Document()
    pu = doc.add("v_pulley")
    for key, value in (("section", "B"), ("datum_d", 150), ("grooves", 2), ("bore", 15),
                       ("center", True)):
        doc.set_param(pu.id, key, value)
    text = generate(doc).text
    assert text.count("module v_pulley(") == 1
    assert 'section = "B"' in text and "datum_d = 150" in text
    again = parse(text)
    assert generate(again).text == text              # ida y vuelta
    assert [n.kind for n in again.children] == ["v_pulley"]


def test_bridas_medidas_de_las_tablas():
    """Valores leídos de las tablas de ASME B16.5-2013 y EN 1092-1:2018, tal como salen en la pieza."""
    from scadgui import flanges as fl
    p = fl.flange("asme_b16_5", "150", "4", "weld_neck")       # tablas 7, 8 y 4
    assert (p["od"], p["thickness"], p["bolt_circle"], p["bolts"], p["hole"]) == (230, 22.3, 190.5, 8, 19.05)
    assert (p["face_d"], p["face_h"], p["hub_d"], p["hub_end_d"], p["length"], p["bore"]) == (
        157.2, 2.0, 135, 114.3, 77.0, 102.3)                     # Y = 75 desde la cara, más 2 de resalte
    assert p["bolt"] == "5/8 in" and p["hole_text"] == "3/4 in"
    p = fl.flange("asme_b16_5", "300", "1/2", "slip_on")        # tablas 10 y 11
    assert (p["od"], p["thickness"], p["bolt_circle"], p["bolts"], p["hole"]) == (95, 12.7, 66.7, 4, 15.88)
    assert (p["hub_d"], p["hub_end_d"], p["length"], p["bore"]) == (38, 38, 23.0, 22.2)
    p = fl.flange("asme_b16_5", "400", "2", "weld_neck")        # clase 400 pequeña: medidas de la 600
    assert p["used_class"] == 600 and p["od"] == 165 and p["face_h"] == 7.0 and p["bore"] is None
    assert "600" in fl.describe("asme_b16_5", "400", "2", "weld_neck", bore=50)[1]
    p = fl.flange("asme_b16_5", "150", "4", "weld_neck", "flat")
    assert p["face_h"] == 0 and p["face_d"] == 0 and p["thickness"] == 22.3 and p["length"] == 75
    assert fl.flange("asme_b16_5", "2500", "12", "blind")["thickness"] == 184.2
    p = fl.flange("en_1092_1", "16", "100", "weld_neck")        # tabla 13 y tabla 8
    assert (p["od"], p["bolt_circle"], p["bolts"], p["hole"], p["bolt"]) == (220, 180, 8, 18, "M16")
    assert (p["thickness"], p["face_h"], p["face_d"]) == (17.0, 3.0, 158)      # C2 = 20 incluye f1
    assert (p["hub_d"], p["hub_end_d"], p["length"], p["neck_length"], p["bore"]) == (131, 114.3, 52, 12, 107.1)
    assert fl.flange("en_1092_1", "16", "100", "weld_neck", "flat")["thickness"] == 20
    p = fl.flange("en_1092_1", "6", "100", "plate")              # tabla 11
    assert (p["od"], p["bolt_circle"], p["bolts"], p["bolt"], p["bore"], p["thickness"]) == (210, 170, 4, "M16",
                                                                                            116.0, 15.0)
    assert fl.flange("en_1092_1", "40", "100", "weld_neck", "flat")["thickness"] == 24   # celda C2/C3 unida
    assert fl.flange("en_1092_1", "6", "100", "weld_neck", "flat")["thickness"] == 16    # columna C2/C3 de PN 6
    assert [fl.en_face_height(dn) for dn in (32, 40, 250, 300, 500, 600)] == [2, 3, 3, 4, 4, 5]


def test_bridas_solo_lo_que_da_la_norma():
    """Ni tamaños ni tipos que la norma no tiene; sin agujero de la tabla, hay que darlo."""
    from scadgui import flanges as fl
    assert fl.available_sizes("asme_b16_5", "2500", "slip_on") == []
    assert fl.available_sizes("asme_b16_5", "1500", "slip_on")[-1] == "2 1/2"
    assert fl.available_sizes("asme_b16_5", "900", "weld_neck")[:2] == ["1/2", "3/4"]   # con las de la 1500
    assert fl.available_sizes("asme_b16_5", "150", "blind")[:3] == ["1/2", "3/4", "1"]
    assert "3 1/2" not in fl.available_sizes("asme_b16_5", "1500", "weld_neck")
    assert "350" not in fl.available_sizes("en_1092_1", "6", "slip_on")
    for bad in (lambda: fl.flange("asme_b16_5", "150", "22", "weld_neck"),
                lambda: fl.flange("asme_b16_5", "2500", "2", "slip_on"),
                lambda: fl.flange("asme_b16_5", "150", "4", "plate"),
                lambda: fl.flange("en_1092_1", "16", "2200", "weld_neck"),
                lambda: fl.create_flange_node("asme_b16_5", "600", "4", "weld_neck")):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("una brida que la norma no da no debe salir con otras medidas")
    node = fl.create_flange_node("asme_b16_5", "600", "4", "weld_neck", bore=97.2)
    assert node.kind == "pipe_flange" and node.params["bore"] == 97.2


def test_bridas_todas_las_medidas_son_coherentes_y_vuelven_igual():
    """Cada brida de las tablas tiene forma válida (los agujeros no tocan el cuello ni el borde) y su
    código vuelve igual al abrirlo."""
    from scadgui import flanges as fl
    doc = Document()
    count = 0
    for std in fl.STANDARDS:
        for rating in fl.ratings(std):
            for ftype in fl.TYPES[std]:
                for facing in fl.FACINGS:
                    for size in fl.available_sizes(std, rating, ftype, facing):
                        p = fl.flange(std, rating, size, ftype, facing)
                        assert not fl.flange_warnings(p), (std, rating, ftype, size, fl.flange_warnings(p))
                        bore = None if p["bore"] is not None else round(p["hub_end_d"] * 0.8, 1)
                        doc.children.append(fl.create_flange_node(std, rating, size, ftype, facing, bore))
                        count += 1
    assert count > 1000
    text = generate(doc).text
    assert text.count("module pipe_flange(") == 1
    again = parse(text)
    assert [n.params for n in again.children] == [n.params for n in doc.children]
    assert [n.name for n in again.children] == [n.name for n in doc.children]


def test_bridas_avisos_y_pieza_por_defecto():
    from scadgui import flanges as fl
    good = {k: v for k, v in fl.flange("asme_b16_5", "150", "4", "weld_neck").items() if k in fl.MODULE_PARAMS}
    assert not fl.flange_warnings(good)
    checks = (({"bolt_circle": 150}, "cuello"), ({"bolt_circle": 220}, "borde"), ({"face_d": 180}, "resalte"),
              ({"bolts": 40}, "tocan"), ({"bore": 120}, "pared"), ({"length": 20}, "largo"))
    for change, word in checks:
        assert any(word in w for w in fl.flange_warnings({**good, **change})), (change, fl.flange_warnings(
            {**good, **change}))
    doc = Document()
    node = doc.add("pipe_flange")                      # el botón de la cinta: la misma brida de la tabla
    assert node.params == {**good, "center": False}


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print("FALLA", name, "->", repr(exc))
    sys.exit(1 if failures else 0)
