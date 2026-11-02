"""Módulos de OpenSCAD que la interfaz escribe en el archivo cuando hacen falta.

Redondear o achaflanar aristas no existe en OpenSCAD, así que se usan dos módulos propios
(``cube_edges`` y ``cylinder_edges``). Cuando el modelo los usa, ``model.generate()`` añade su
definición al final del archivo; al abrirlo, ``parser.parse()`` quita esa definición si no se
ha modificado. Así el ``.scad`` funciona en cualquier OpenSCAD sin bibliotecas externas.

Cada arista de un cubo se nombra por los dos lados que toca, con 0 para el lado mínimo y 1
para el máximo: "x1y1" es la arista vertical en X máximo e Y máximo; "y0z1", la arista paralela
a X en Y mínimo y Z máximo.
"""

from __future__ import annotations

import re

CUBE_EDGE_KEYS = (
    "x0y0", "x0y1", "x1y0", "x1y1",   # paralelas a Z (verticales)
    "y0z0", "y0z1", "y1z0", "y1z1",   # paralelas a X
    "x0z0", "x0z1", "x1z0", "x1z1",   # paralelas a Y
)
CYLINDER_EDGE_KEYS = ("bottom", "top")

CUBE_EDGES = '''module cube_edges(size = [10, 10, 10], center = false, edges = [], rounding = 0, chamfer = 0) {
  // Cubo con aristas redondeadas o achaflanadas (lo escribe OpenSCAD GUI Mejorada).
  // "x1y1" es la arista vertical en X máximo e Y máximo; 0 es el lado mínimo.
  s = is_list(size) ? size : [size, size, size];
  // Un pelo menos que la mitad del lado: si dos redondeos se tocaran, sus puntos coincidirían.
  r = min(chamfer > 0 ? chamfer : rounding, min(s) / 2 * 0.9999);
  function has(k) = len([for (x = edges) if (x == k) 1]) > 0;
  n = max(1, ceil(($fn > 0 ? max($fn, 3) : ceil(max(min(360 / $fa, r * 2 * PI / $fs), 5))) / 4));
  translate(center ? -s / 2 : [0, 0, 0])
    if (r <= 0) cube(s);
    else if (chamfer > 0) chamfered();
    else rounded();

  // Redondeo: el cubo redondeado es convexo, así que es la envolvente (hull) de los puntos de sus
  // ocho esquinas. Una esquina con sus tres aristas redondeadas es un octante de esfera; si no, la
  // superficie de cada cilindro dentro de la esquina, recortada por el otro (lift sube el punto
  // hasta ese corte). CGAL falla con puntos repetidos o alineados: se evitan los dos.
  module rounded() {
    arc = [for (i = [0 : n]) let(a = 90 * i / n) [r - r * cos(a), r - r * sin(a)]];
    function lift(t, q) = q < r ? max(t, r - sqrt(max(0, r * r - (r - q) * (r - q)))) : t;
    function unique(v) = [for (i = [0 : len(v) - 1])
                            if (len([for (j = [0 : 1 : i - 1]) if (norm(v[j] - v[i]) < 1e-6) 1]) == 0) v[i]];
    // Esquina en el origen con la pieza hacia +X+Y+Z; z, x, y: si están redondeadas sus aristas
    // paralelas a Z, X e Y. A lo largo de cada cilindro bastan los extremos del tramo (0 y r).
    function corner(z, x, y) =
      z && x && y ? concat([for (i = [0 : n], j = [0 : n - 1]) let(a = 90 * i / n, b = 90 * j / n)
                             [r, r, r] - r * [cos(b) * cos(a), cos(b) * sin(a), sin(b)]], [[r, r, 0]])
      : !z && !x && !y ? [[0, 0, 0]]
      : unique(concat(
          z ? [for (p = arc, t = [0, r]) [p[0], p[1], x ? lift(t, p[1]) : y ? lift(t, p[0]) : t]] : [],
          x ? [for (p = arc, t = [0, r]) [z ? lift(t, p[0]) : y ? lift(t, p[1]) : t, p[0], p[1]]] : [],
          y ? [for (p = arc, t = [0, r]) [p[1], z ? lift(t, p[1]) : x ? lift(t, p[0]) : t, p[0]]] : []));
    pts = [for (i = [0, 1], j = [0, 1], k = [0, 1])
             for (p = corner(has(str("x", i, "y", j)), has(str("y", j, "z", k)), has(str("x", i, "z", k))))
               [i ? s.x - p[0] : p[0], j ? s.y - p[1] : p[1], k ? s.z - p[2] : p[2]]];
    hull() polyhedron(pts, [[for (i = [0 : len(pts) - 1]) i]]);
  }

  // Chaflán: intersección de tres prismas, uno por eje, con las esquinas de su perfil cortadas.
  module chamfered() {
    function corner(w, h, c, cut) = let(p = [c[0] * w, c[1] * h]) !cut ? [p]
      : c == [0, 0] ? [p + [0, r], p + [r, 0]] : c == [1, 0] ? [p - [r, 0], p + [0, r]]
      : c == [1, 1] ? [p - [0, r], p - [r, 0]] : [p + [r, 0], p - [0, r]];
    // Rectángulo w x h con las esquinas de keys cortadas, en orden (0,0), (1,0), (1,1), (0,1).
    module profile(w, h, keys) {
      polygon(concat(corner(w, h, [0, 0], has(keys[0])), corner(w, h, [1, 0], has(keys[1])),
                     corner(w, h, [1, 1], has(keys[2])), corner(w, h, [0, 1], has(keys[3]))));
    }
    intersection() {
      linear_extrude(s.z) profile(s.x, s.y, ["x0y0", "x1y0", "x1y1", "x0y1"]);
      multmatrix([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]])
        linear_extrude(s.x) profile(s.y, s.z, ["y0z0", "y1z0", "y1z1", "y0z1"]);
      multmatrix([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0]])
        linear_extrude(s.y) profile(s.z, s.x, ["x0z0", "x0z1", "x1z1", "x1z0"]);
    }
  }
}'''

CYLINDER_EDGES = '''module cylinder_edges(h = 10, r = 5, center = false, edges = [], rounding = 0, chamfer = 0) {
  // Cilindro con el borde "top" y/o "bottom" redondeado o achaflanado (lo escribe OpenSCAD GUI Mejorada).
  c = min(chamfer > 0 ? chamfer : rounding, r, h / 2);
  function cut(k) = c > 0 && len([for (x = edges) if (x == k) 1]) > 0 ? c : 0;
  b = cut("bottom");
  t = cut("top");
  e = 0.001;
  translate([0, 0, center ? -h / 2 : 0]) rotate_extrude() intersection() {
    square([r, h]);
    hull() {
      square([e, h]);
      if (b == 0) translate([r - e, 0]) square(e);
      else if (chamfer > 0) polygon([[r - b, 0], [r, b], [r - b, b]]);
      else translate([r - b, b]) circle(b);
      if (t == 0) translate([r - e, h - e]) square(e);
      else if (chamfer > 0) polygon([[r - t, h], [r - t, h - t], [r, h - t]]);
      else translate([r - t, h - t]) circle(t);
    }
  }
}'''

SPUR_GEAR = '''module spur_gear(mod = 1, teeth = 20, thickness = 5, pressure_angle = 20, backlash = 0, bore = 0, center = false) {
  // Engranaje recto de evolvente por módulo (lo escribe OpenSCAD GUI Mejorada).
  // Diámetro primitivo = mod * teeth; exterior = mod * (teeth + 2); dos engranajes del mismo
  // módulo engranan con sus centros a mod * (z1 + z2) / 2. backlash: holgura en mm entre los dos.
  z = max(3, round(teeth));
  r = mod * z / 2;                      // radio primitivo
  rb = r * cos(pressure_angle);         // radio de base (de él sale la evolvente)
  ra = r + mod;                         // radio exterior
  rf = max(r - 1.25 * mod, mod * 0.1);  // radio de raíz
  r0 = max(rb, rf);
  function inv(a) = tan(a) - a * PI / 180;   // involuta, en radianes, de un ángulo en grados
  // Medio grueso del diente, en grados, a la distancia R del centro.
  function half(R) = max(0, ((PI * mod / 2 - backlash / 2) / (2 * r) + inv(pressure_angle)
                             - inv(acos(min(1, rb / R)))) * 180 / PI);
  n = 8;
  flank = [for (k = [0 : n]) r0 + (ra - r0) * k / n];
  root = rf < r0 - 1e-6;
  pts = [for (i = [0 : z - 1]) let(c = i * 360 / z) each concat(
           root ? [[rf * cos(c - half(r0)), rf * sin(c - half(r0))]] : [],
           [for (R = flank) [R * cos(c - half(R)), R * sin(c - half(R))]],
           [for (k = [n : -1 : 0]) let(R = flank[k]) [R * cos(c + half(R)), R * sin(c + half(R))]],
           root ? [[rf * cos(c + half(r0)), rf * sin(c + half(r0))]] : [],
           [[rf * cos(c + 180 / z), rf * sin(c + 180 / z)]])];
  translate([0, 0, center ? -thickness / 2 : 0]) difference() {
    linear_extrude(thickness) polygon(pts);
    if (bore > 0) translate([0, 0, -1]) cylinder(h = thickness + 2, d = bore);
  }
}'''

HELICAL_GEAR = '''module helical_gear(mod = 1, teeth = 20, thickness = 10, helix_angle = 20, left_hand = false, pressure_angle = 20, backlash = 0, bore = 0, center = false) {
  // Engranaje helicoidal de evolvente (lo escribe OpenSCAD GUI Mejorada).
  // mod y pressure_angle son los NORMALES (medidos perpendiculares al diente). En el plano de
  // giro valen más: mt = mod / cos(hélice) y tan(at) = tan(pressure_angle) / cos(hélice).
  // Ø primitivo = mod * teeth / cos(hélice). Dos engranajes del mismo módulo y la misma hélice,
  // uno a derechas y otro a izquierdas, engranan a mod * (z1 + z2) / (2 * cos(hélice)).
  z = max(3, round(teeth));
  b = max(0.001, thickness);
  mt = mod / cos(helix_angle);                        // módulo aparente
  at = atan(tan(pressure_angle) / cos(helix_angle));  // ángulo de presión aparente
  r = mt * z / 2;                       // radio primitivo
  rb = r * cos(at);                     // radio de base
  ra = r + mod;                         // la cabeza se mide con el módulo normal
  rf = max(r - 1.25 * mod, mod * 0.1);  // y el pie también
  r0 = max(rb, rf);
  function inv(a) = tan(a) - a * PI / 180;
  function half(R) = max(0, ((PI * mt / 2 - backlash / 2) / (2 * r) + inv(at)
                             - inv(acos(min(1, rb / R)))) * 180 / PI);
  n = 8;
  flank = [for (k = [0 : n]) r0 + (ra - r0) * k / n];
  root = rf < r0 - 1e-6;
  pts = [for (i = [0 : z - 1]) let(c = i * 360 / z) each concat(
           root ? [[rf * cos(c - half(r0)), rf * sin(c - half(r0))]] : [],
           [for (R = flank) [R * cos(c - half(R)), R * sin(c - half(R))]],
           [for (k = [n : -1 : 0]) let(R = flank[k]) [R * cos(c + half(R)), R * sin(c + half(R))]],
           root ? [[rf * cos(c + half(r0)), rf * sin(c + half(r0))]] : [],
           [[rf * cos(c + 180 / z), rf * sin(c + 180 / z)]])];
  // Giro del perfil sobre el grueso: 2 * b * sen(hélice) / (z * mod) radianes. OpenSCAD gira en
  // sentido horario con twist positivo, así que la hélice a derechas lleva twist negativo.
  turn = 2 * b * sin(helix_angle) / (z * mod) * 180 / PI;
  translate([0, 0, center ? -b / 2 : 0]) difference() {
    linear_extrude(b, twist = left_hand ? turn : -turn, slices = max(8, ceil(turn / 2)),
                   convexity = 10) polygon(pts);
    if (bore > 0) translate([0, 0, -1]) cylinder(h = b + 2, d = bore);
  }
}'''

RACK = '''module rack(mod = 1, teeth = 10, thickness = 5, base = 5, pressure_angle = 20, backlash = 0, helix_angle = 0, left_hand = false, center = false) {
  // Cremallera del sistema por módulo (lo escribe OpenSCAD GUI Mejorada).
  // Es el "dentado básico" que define la forma del diente: flancos rectos inclinados el ángulo
  // de presión, paso PI * mod, cabeza mod y pie 1.25 * mod. Engrana con cualquier engranaje del
  // mismo módulo. La línea primitiva queda en y = 0 y los dientes miran a +Y, así que el
  // engranaje va con su centro a su radio primitivo de altura; cada diente está centrado en su
  // paso, o sea que los huecos caen en los múltiplos del paso.
  // Con helix_angle engrana con un engranaje helicoidal DE LA MISMA MANO: el diente es una recta
  // que forma ese ángulo con el eje del engranaje, o sea que el perfil se sesga tan(hélice) por
  // cada mm de grueso. Entonces mod y pressure_angle son los NORMALES y el paso y los flancos
  // salen de los aparentes, como en helical_gear. Los extremos quedan al sesgo del dentado; si se
  // quieren a escuadra, recortarlos con una resta.
  z = max(1, round(teeth));
  mt = mod / cos(helix_angle);                        // módulo aparente
  at = atan(tan(pressure_angle) / cos(helix_angle));  // ángulo de presión aparente
  p = PI * mt;                  // paso (en el plano de giro)
  total = z * p;                // longitud total
  ha = mod;                     // cabeza (sobre la línea primitiva), con el módulo normal
  hf = 1.25 * mod;              // pie, también
  t = tan(at);
  hp = p / 4 - backlash / 4;    // medio grueso del diente en la línea primitiva
  // Con un ángulo de presión grande los flancos de dos dientes vecinos se cortan antes de llegar
  // al fondo: el hueco acaba en V en vez de tener meseta.
  y_v = (2 * hp - p) / (2 * t);
  y_bot = max(-hf, y_v);
  land = y_v <= -hf + 1e-12;    // ¿queda meseta en el fondo del hueco?
  hb = hp - y_bot * t;          // medio grueso en el fondo del hueco
  tip = hp - ha * t;            // medio grueso en la cabeza (si no es positivo, acaba en punta)
  y_back = -hf - max(0, base);
  pts = concat(
    land ? [[0, y_bot]] : [],
    [for (i = [0 : z - 1]) let(c = (i + 0.5) * p) each concat(
       [[c - hb, y_bot]],
       tip > 0 ? [[c - tip, ha], [c + tip, ha]] : [[c, hp / t]],
       [[c + hb, y_bot]])],
    land ? [[total, y_bot]] : [],
    [[total, y_back], [0, y_back]]);
  shear = (left_hand ? -1 : 1) * tan(helix_angle);    // lo que se corre el dentado con el grueso
  translate([0, 0, center ? -thickness / 2 : 0])
    multmatrix([[1, 0, shear, 0], [0, 1, 0, 0], [0, 0, 1, 0]])
      linear_extrude(thickness) polygon(pts);
}'''

BEVEL_GEAR = '''module bevel_gear(mod = 1, teeth = 20, mate_teeth = 20, shaft_angle = 90, face_width = 4, pressure_angle = 20, backlash = 0, bore = 0) {
  // Engranaje cónico recto (lo escribe OpenSCAD GUI Mejorada).
  // Machinery's Handbook 27, "Rules and Formulas for Calculating Dimensions of Milled Bevel
  // Gears", p. 2087. El vértice del cono queda en el ORIGEN y la rueda mira hacia +Z, así que
  // su pareja es la misma pieza girada el ángulo entre ejes: no hay que moverla.
  // El diente sale del engranaje virtual de Tredgold (uno recto del mismo módulo con
  // teeth/cos(cono) dientes) y el perfil se barre hacia el vértice, con lo que los conos de
  // cabeza, primitivo y pie salen exactos.
  z = max(3, round(teeth));
  zm = max(3, round(mate_teeth));
  g = atan2(sin(shaft_angle), zm / z + cos(shaft_angle));   // ángulo del cono primitivo
  C = mod * z / (2 * sin(g));                               // distancia de cono exterior
  ha = atan(mod / C);                                       // ángulo de cabeza
  hf = atan(1.25 * mod / C);                                // ángulo de pie
  // La cara trasera se tornea plana, en el plano donde el cono de cabeza llega al diámetro
  // exterior D + 2*mod*cos(g): es la "vertex distance" J del Handbook.
  zo = (mod * z / 2 + mod * cos(g)) / tan(g + ha);
  F = min(max(0.01, face_width), zo / cos(g) * 0.95);       // ancho de cara, sobre el primitivo
  zi = zo - F * cos(g);
  rv = mod * (z / cos(g)) / 2;                              // radio primitivo del virtual
  rbv = rv * cos(pressure_angle);
  rf = max(rv - 1.25 * mod, mod * 0.1);
  r0 = max(rbv, rf);
  function inv(a) = tan(a) - a * PI / 180;
  // Medio grueso del diente ALREDEDOR DEL EJE: el del virtual, dividido por cos(cono).
  function half(p) = max(0, ((PI * mod / 2 - backlash / 2) / (2 * rv) + inv(pressure_angle)
                             - inv(acos(min(1, rbv / p)))) * 180 / PI) / cos(g);
  // Un punto que en el virtual está a p del centro queda sobre el cono g + atan((p - rv)/C).
  function rad(p) = zo * tan(g + atan((p - rv) / C));
  n = 8;
  flank = [for (k = [0 : n]) r0 + (rv + mod - r0) * k / n];
  root = rf < r0 - 1e-6;
  pts = [for (i = [0 : z - 1]) let(c = i * 360 / z) each concat(
           root ? [[rad(rf) * cos(c - half(r0)), rad(rf) * sin(c - half(r0))]] : [],
           [for (p = flank) [rad(p) * cos(c - half(p)), rad(p) * sin(c - half(p))]],
           [for (k = [n : -1 : 0]) let(p = flank[k])
              [rad(p) * cos(c + half(p)), rad(p) * sin(c + half(p))]],
           root ? [[rad(rf) * cos(c + half(r0)), rad(rf) * sin(c + half(r0))]] : [],
           [[rad(rf) * cos(c + 180 / z), rad(rf) * sin(c + 180 / z)]])];
  difference() {
    // Barrido hacia el vértice: el perfil de la cara delantera es el de la trasera a escala.
    translate([0, 0, zi])
      linear_extrude(zo - zi, scale = zo / zi) polygon([for (q = pts) q * zi / zo]);
    if (bore > 0) translate([0, 0, -1]) cylinder(h = zo + 2, d = bore);
  }
}'''

PULLEY = '''module pulley(section = "XL", teeth = 20, width = 6, bore = 0, flange = "ninguna",
               flange_height = 1.5, center = false) {
  // Polea dentada para correa síncrona (lo escribe OpenSCAD GUI Mejorada).
  // Secciones trapeciales clásicas ANSI/RMA IP-24 (Machinery's Handbook 27, tablas 40 y 44):
  // paso, ángulo de diente, altura (ht) y grueso en la línea primitiva (bt), y cuánto la
  // circunferencia primitiva PD = z*paso/PI queda por encima de la exterior (Ø ext = PD - 2*PLD).
  // El hueco es el negativo del diente de la correa, de flancos rectos (sin los redondeos ra/rr
  // de la tabla, igual que la cremallera tampoco los lleva).
  // Las pestañas (flange) son simples collares cilíndricos que sobresalen flange_height del Ø
  // exterior, a un lado, al otro o a los dos: sin ellas la correa puede salirse por el eje.
  data = section == "MXL" ? [2.032, 40, 0.508, 1.143, 0.254] :
         section == "XL" ? [5.08, 50, 1.27, 2.5654, 0.254] :
         section == "L" ? [9.525, 40, 1.905, 4.6482, 0.381] :
         section == "H" ? [12.7, 40, 2.286, 6.1214, 0.6858] :
         [22.225, 40, 6.35, 12.573, 1.397];                 // XH
  p = data[0]; ang = data[1]; ht = data[2]; bt = data[3]; pld = data[4];
  z = max(3, round(teeth));
  pitch_d = z * p / PI;
  outer_d = pitch_d - 2 * pld;
  root_d = outer_d - 2 * ht;
  t = tan(ang / 2);
  tip_half = max(0, bt / 2 - (ht + pld) * t);      // medio grueso del hueco en el fondo
  top_half = max(0, bt / 2 - pld * t);             // medio grueso del hueco en la boca
  r_out = outer_d / 2;
  r_root = max(0.1, root_d / 2);
  half_step = 180 / z;
  top_a = min(top_half / r_out * 180 / PI, half_step - 0.01);
  bot_a = min(tip_half / r_root * 180 / PI, half_step - 0.01);
  pts = [for (i = [0 : z - 1]) let(c = i * 360 / z) each [
           [r_out * cos(c - top_a), r_out * sin(c - top_a)],
           [r_root * cos(c - bot_a), r_root * sin(c - bot_a)],
           [r_root * cos(c + bot_a), r_root * sin(c + bot_a)],
           [r_out * cos(c + top_a), r_out * sin(c + top_a)]]];
  fn_c = max(32, z * 2);
  bot = (flange == "inferior" || flange == "ambas") ? max(0, flange_height) : 0;
  top = (flange == "superior" || flange == "ambas") ? max(0, flange_height) : 0;
  total = bot + width + top;
  fd = outer_d + 2 * max(0, flange_height);
  translate([0, 0, center ? -total / 2 : 0]) difference() {
    union() {
      translate([0, 0, bot]) linear_extrude(width) polygon(pts);
      if (bot > 0) cylinder(h = bot, d = fd, $fn = fn_c);
      if (top > 0) translate([0, 0, bot + width]) cylinder(h = top, d = fd, $fn = fn_c);
    }
    if (bore > 0) translate([0, 0, -1]) cylinder(h = total + 2, d = bore, $fn = fn_c);
  }
}'''

LIBRARY = {"cube_edges": CUBE_EDGES, "cylinder_edges": CYLINDER_EDGES, "spur_gear": SPUR_GEAR,
           "helical_gear": HELICAL_GEAR, "rack": RACK, "bevel_gear": BEVEL_GEAR, "pulley": PULLEY}

# Versiones anteriores que ya pueden estar en archivos guardados. Al abrir el archivo se
# reconocen como nuestras y se sustituyen por la versión actual (no se conservan como código
# del usuario). No borrar: los archivos viejos dejarían de actualizarse.
PREVIOUS_VERSIONS = {
    # 2026-10-31: intersección de tres prismas; las esquinas con tres aristas redondeadas
    # salían como cruce de cilindros ("pellizcadas") en vez de esféricas.
    "cube_edges": ('''module cube_edges(size = [10, 10, 10], center = false, edges = [], rounding = 0, chamfer = 0) {
  // Cubo con aristas redondeadas o achaflanadas (lo escribe OpenSCAD GUI Mejorada).
  // "x1y1" es la arista vertical en X máximo e Y máximo; 0 es el lado mínimo.
  // Es la intersección de tres prismas, uno por eje, cada uno con las esquinas de su perfil
  // tratadas: solo usa polígonos e intersecciones, que no fallan ni con CGAL ni con Manifold.
  s = is_list(size) ? size : [size, size, size];
  r = min(chamfer > 0 ? chamfer : rounding, min(s) / 2);
  function has(k) = len([for (x = edges) if (x == k) 1]) > 0;
  n = max(1, ceil(($fn > 0 ? max($fn, 3) : ceil(max(min(360 / $fa, r * 2 * PI / $fs), 5))) / 4));
  // Puntos de la esquina c = [lado en u, lado en v] de un rectángulo w x h, en sentido antihorario:
  // redondeada, un arco de n tramos; achaflanada, los dos extremos del arco; viva, la esquina.
  function corner(w, h, c, cut) =
    let(p = [c[0] * w, c[1] * h], o = p + r * [c[0] ? -1 : 1, c[1] ? -1 : 1],
        a0 = c == [0, 0] ? 180 : c == [1, 0] ? 270 : c == [1, 1] ? 0 : 90)
    !cut || r <= 0 ? [p]
    : [for (k = chamfer > 0 ? [0, n] : [0 : n]) o + r * [cos(a0 + 90 * k / n), sin(a0 + 90 * k / n)]];
  // Rectángulo w x h con las esquinas de keys tratadas, en orden (0,0), (1,0), (1,1), (0,1).
  module profile(w, h, keys) {
    polygon(concat(corner(w, h, [0, 0], has(keys[0])), corner(w, h, [1, 0], has(keys[1])),
                   corner(w, h, [1, 1], has(keys[2])), corner(w, h, [0, 1], has(keys[3]))));
  }
  translate(center ? -s / 2 : [0, 0, 0]) intersection() {
    linear_extrude(s.z) profile(s.x, s.y, ["x0y0", "x1y0", "x1y1", "x0y1"]);
    multmatrix([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]])
      linear_extrude(s.x) profile(s.y, s.z, ["y0z0", "y1z0", "y1z1", "y0z1"]);
    multmatrix([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0]])
      linear_extrude(s.y) profile(s.z, s.x, ["x0z0", "x0z1", "x1z1", "x1z0"]);
  }
}''',),
}


def _normalized(text: str) -> str:
    return " ".join(text.split())


_NORMALIZED = {_normalized(code): name for name, code in LIBRARY.items()}
_NORMALIZED.update({_normalized(code): name for name, codes in PREVIOUS_VERSIONS.items() for code in codes})


def library_name(text: str) -> str:
    """Nombre del módulo si ``text`` es una definición de la biblioteca sin cambios; si no, ''."""
    return _NORMALIZED.get(_normalized(text), "")


def needed_definitions(code: str) -> list[str]:
    """Definiciones que hay que añadir: módulos usados en ``code`` que no están definidos en él."""
    out = []
    for name, definition in LIBRARY.items():
        used = re.search(rf"(?<![\w$]){name}\s*\(", code)
        defined = re.search(rf"\bmodule\s+{name}\s*\(", code)
        if used and not defined:
            out.append(definition)
    return out
