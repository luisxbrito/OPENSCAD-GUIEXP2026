"""Pruebas unitarias del generador de estructuras aligeradas y lattice TPMS Gyroid."""

import os
from scadgui import lattice
from scadgui.i18n import set_language, tr

def test_lattice_metrics_and_patterns():
    for pat in lattice.PATTERNS:
        assert lattice.pattern_name(pat)
        code = lattice.generate_scad_code(50, 50, 30, 10, 1.2, pattern=pat,
                                          has_shell=True, shell_thick=1.6,
                                          has_drain=True, drain_d=4.0)
        assert "module pieza_aligerada" in code
        assert "nucleo_lattice" in code

    # Métricas y ahorro de masa
    m = lattice.estimate_metrics(60, 40, 30, 10, 1.2, has_shell=True, shell_thick=1.2, material_key="pla")
    assert m["solid_mass_g"] > m["lattice_mass_g"]
    assert m["savings_pct"] > 0

    node = lattice.create_lattice_node(60, 40, 30, 10, 1.2, pattern="gyroid")
    assert node.kind == "__raw__"
    assert "module pieza_aligerada" in node.text
    assert "size" in node.params


def test_lattice_apply_to_solid():
    from scadgui.model import Document, Node, generate
    cube_node = Node("cube", {"size": [30, 30, 30], "center": True}, name="MiCubo")
    temp_doc = Document(children=[cube_node])
    solid_code = generate(temp_doc, header=False, library=False).text.strip()

    node = lattice.create_lattice_node(
        30, 30, 30, 10, 1.2, pattern="gyroid",
        has_shell=True, shell_thick=1.5,
        solid_code=solid_code, target_name="MiCubo"
    )
    assert "module solido_original() {" in node.text
    assert "cube([30, 30, 30], center = true);" in node.text
    assert "solido_interior()" in node.text
    assert "MiCubo" in node.name
    assert node.kind == "__raw__"
