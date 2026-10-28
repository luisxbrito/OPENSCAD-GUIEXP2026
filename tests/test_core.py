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
    assert len(SPECS) == 30
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
    assert "difference() { // Restar" in gen.text
    assert "cube([40, 30, 10], center = true); // Cubo" in gen.text
    assert "translate([0, 0, 0]) { // Mover" in gen.text
    assert "cylinder(h = 12, r = 6, center = true); // Cilindro" in gen.text
    lines = gen.text.splitlines()
    a, b = gen.lines[hole.id]
    assert a == b and "cylinder" in lines[a]
    assert gen.node_at(a) == hole.id
    ta, tb = gen.lines[tr.id]
    assert ta < a <= tb


def test_nombres_unicos():
    doc = Document()
    assert doc.add("cube").name == "Cubo"
    assert doc.add("cube").name == "Cubo001"
    assert doc.add("cube").name == "Cubo002"


def test_operaciones_arbol():
    doc = Document()
    a, b, c = doc.add("cube"), doc.add("sphere"), doc.add("cylinder")
    assert doc.move(c.id, -1) and [n.id for n in doc.children] == [a.id, c.id, b.id]
    g = doc.wrap([a.id], "union")
    assert doc.indent(c.id) and c in g.children
    assert doc.outdent(c.id) and doc.children.index(c) == 1
    dup = doc.duplicate(b.id)
    assert dup.id != b.id and dup.name == "Esfera001"
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
    from scadgui.ui.sketch import create_sketch_node, PROFILES
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
    v1 = doc.set_variable("ancho", 50, "Ancho de la caja")
    v2 = doc.set_variable("alto", 25.5)
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
    assert "Escala 1:1  ·  A4" in code_a4
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
        SCREWS_ISO_4762, BEARINGS_ISO
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
    assert tr("Configuración y Preferencias") == "Settings & Preferences"
    assert tr("Motor OpenSCAD") == "OpenSCAD Engine"
    assert tr("Visor 3D y Gizmo") == "3D Viewport & Gizmo"
    assert tr("Componentes y Planos") == "Components & Drawings"
    assert tr("Editor y Proyecto") == "Editor & Project"
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
    from scadgui.ui.operation_helper import OPERATION_HELPERS

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
    x_plus_10 = next(fn for name, fn, key in tr_presets if name == "X +10")
    res = x_plus_10({"v": [5.0, 0.0, 0.0]})
    assert res == [15.0, 0.0, 0.0]

    # Comprobar presets de rotate
    rot_presets = OPERATION_HELPERS["rotate"]["presets"]
    z_plus_90 = next(fn for name, fn, key in rot_presets if "Z +90" in name)
    res_rot = z_plus_90({"a": [0.0, 0.0, 0.0]})
    assert res_rot[2] == 90.0


def test_codeview_snippets_y_plantillas():
    """Comprueba que los snippets y plantillas de código para el editor accesible estén completos."""
    from scadgui.ui.codeview import BOOLEAN_TEMPLATES, SNIPPETS_CATALOG

    # Plantillas booleanas
    assert "difference" in BOOLEAN_TEMPLATES
    assert "union" in BOOLEAN_TEMPLATES
    assert "intersection" in BOOLEAN_TEMPLATES
    for k, templ in BOOLEAN_TEMPLATES.items():
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
    from scadgui.ui.codeview import (
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
    """Verifica que el modelo de inicio Figura 5.31 (Rueda con eje giratorio) carga y ensambla 6 piezas."""
    path = os.path.join(os.path.dirname(__file__), "..", "examples", "rueda_con_eje_giratorio.scad")
    assert os.path.isfile(path), "No se encuentra rueda_con_eje_giratorio.scad"
    with open(path, encoding="utf-8") as f:
        code = f.read()
    doc = parse(code)
    assert doc.fn == 64
    piezas = [n for n in doc.children if isinstance(n, Node)]
    assert len(piezas) == 6, f"Esperadas 6 piezas principales, se encontraron {len(piezas)}"
    nombres = [p.name for p in piezas]
    assert "Pza 1 - Rueda" in nombres
    assert "Pza 2 - Poste giratorio" in nombres
    assert "Pza 3 - Perno de eje" in nombres
    assert "Pza 4 - Soporte" in nombres
    assert "Pza 5 - Buje" in nombres
    assert "Pza 6 - Tuerca Hex M6" in nombres

    # Generación de código de vuelta sin pérdida
    code_gen = generate(doc).text
    doc2 = parse(code_gen)
    piezas2 = [n for n in doc2.children if isinstance(n, Node)]
    assert len(piezas2) == 6

    # Geometría y mallas fantasma
    from scadgui import geometry as geo
    ghosts = geo.build_ghosts(doc)
    assert len(ghosts) > 0, "No se generaron mallas fantasma para la rueda giratoria"




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
