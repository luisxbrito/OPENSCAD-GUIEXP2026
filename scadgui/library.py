"""Módulos de OpenSCAD que la interfaz escribe en el archivo cuando hacen falta.

Redondear o achaflanar aristas no existe en OpenSCAD, así que se usan dos módulos propios
(``cube_edges`` y ``cylinder_edges``). Cuando el modelo los usa, ``model.generate()`` añade su
definición al final del archivo; al abrirlo, ``parser.parse()`` quita esa definición si no se
ha modificado. Así el ``.scad`` funciona en cualquier OpenSCAD sin bibliotecas externas.

Cada arista de un cubo se nombra por los dos lados que toca, con 0 para el lado mínimo y 1
para el máximo: "x1y1" es la arista vertical en X máximo e Y máximo; "y0z1", la arista paralela
a X en Y mínimo y Z máximo.

Los comentarios DENTRO de los módulos van en inglés, sea cual sea el idioma de la interfaz: es
código que acaba en el archivo del usuario. Si se cambia un módulo, la versión que había antes
se añade a ``PREVIOUS_VERSIONS`` para que los archivos ya guardados se sigan reconociendo.
"""

from __future__ import annotations

import re

from .library_old import SPANISH_COMMENTS

CUBE_EDGE_KEYS = (
    "x0y0", "x0y1", "x1y0", "x1y1",   # paralelas a Z (verticales)
    "y0z0", "y0z1", "y1z0", "y1z1",   # paralelas a X
    "x0z0", "x0z1", "x1z0", "x1z1",   # paralelas a Y
)
CYLINDER_EDGE_KEYS = ("bottom", "top")

CUBE_EDGES = '''module cube_edges(size = [10, 10, 10], center = false, edges = [], rounding = 0, chamfer = 0) {
  // Cube with rounded or chamfered edges (written by OpenSCAD GUI Mejorada).
  // "x1y1" is the vertical edge at maximum X and maximum Y; 0 is the minimum side.
  s = is_list(size) ? size : [size, size, size];
  // Just under half the side: if two fillets touched, their points would coincide.
  r = min(chamfer > 0 ? chamfer : rounding, min(s) / 2 * 0.9999);
  function has(k) = len([for (x = edges) if (x == k) 1]) > 0;
  n = max(1, ceil(($fn > 0 ? max($fn, 3) : ceil(max(min(360 / $fa, r * 2 * PI / $fs), 5))) / 4));
  translate(center ? -s / 2 : [0, 0, 0])
    if (r <= 0) cube(s);
    else if (chamfer > 0) chamfered();
    else rounded();

  // Rounding: the rounded cube is convex, so it is the hull of the points of its eight corners.
  // A corner with its three edges rounded is a sphere octant; otherwise, the surface of each
  // cylinder inside the corner, trimmed by the other one (lift raises the point up to that cut).
  // CGAL fails with repeated or collinear points: both are avoided.
  module rounded() {
    arc = [for (i = [0 : n]) let(a = 90 * i / n) [r - r * cos(a), r - r * sin(a)]];
    function lift(t, q) = q < r ? max(t, r - sqrt(max(0, r * r - (r - q) * (r - q)))) : t;
    function unique(v) = [for (i = [0 : len(v) - 1])
                            if (len([for (j = [0 : 1 : i - 1]) if (norm(v[j] - v[i]) < 1e-6) 1]) == 0) v[i]];
    // Corner at the origin with the part towards +X+Y+Z; z, x, y: whether its edges parallel to
    // Z, X and Y are rounded. Along each cylinder the ends of the stretch (0 and r) are enough.
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

  // Chamfer: intersection of three prisms, one per axis, with the corners of their profile cut.
  module chamfered() {
    function corner(w, h, c, cut) = let(p = [c[0] * w, c[1] * h]) !cut ? [p]
      : c == [0, 0] ? [p + [0, r], p + [r, 0]] : c == [1, 0] ? [p - [r, 0], p + [0, r]]
      : c == [1, 1] ? [p - [0, r], p - [r, 0]] : [p + [r, 0], p - [0, r]];
    // Rectangle w x h with the corners in keys cut, in the order (0,0), (1,0), (1,1), (0,1).
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
  // Cylinder with its "top" and/or "bottom" rim rounded or chamfered (written by OpenSCAD GUI Mejorada).
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

SPUR_GEAR = '''module spur_gear(mod = 1, teeth = 20, thickness = 5, pressure_angle = 20, backlash = 0, bore = 0, center = false, keyway = false, key_width = 0, key_depth = 0) {
  // Involute spur gear by module (written by OpenSCAD GUI Mejorada).
  // Pitch diameter = mod * teeth; outside = mod * (teeth + 2); two gears of the same module
  // mesh with their centres mod * (z1 + z2) / 2 apart. backlash: clearance in mm between the two.
  z = max(3, round(teeth));
  r = mod * z / 2;                      // pitch radius
  rb = r * cos(pressure_angle);         // base radius (the involute starts from it)
  ra = r + mod;                         // outside radius
  rf = max(r - 1.25 * mod, mod * 0.1);  // root radius
  r0 = max(rb, rf);
  function inv(a) = tan(a) - a * PI / 180;   // involute, in radians, of an angle in degrees
  // Half the tooth thickness, in degrees, at distance R from the centre.
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
    if (bore > 0) translate([0, 0, -1]) shaft_bore(bore, thickness + 2, keyway, key_width, key_depth);
  }
}'''

HELICAL_GEAR = '''module helical_gear(mod = 1, teeth = 20, thickness = 10, helix_angle = 20, left_hand = false, pressure_angle = 20, backlash = 0, bore = 0, center = false, keyway = false, key_width = 0, key_depth = 0) {
  // Involute helical gear (written by OpenSCAD GUI Mejorada).
  // mod and pressure_angle are the NORMAL ones (measured perpendicular to the tooth). In the
  // transverse plane they are larger: mt = mod / cos(helix), tan(at) = tan(pressure_angle) / cos(helix).
  // Pitch diameter = mod * teeth / cos(helix). Two gears of the same module and helix angle,
  // one right-handed and one left-handed, mesh at mod * (z1 + z2) / (2 * cos(helix)).
  z = max(3, round(teeth));
  b = max(0.001, thickness);
  mt = mod / cos(helix_angle);                        // transverse module
  at = atan(tan(pressure_angle) / cos(helix_angle));  // transverse pressure angle
  r = mt * z / 2;                       // pitch radius
  rb = r * cos(at);                     // base radius
  ra = r + mod;                         // the addendum uses the normal module
  rf = max(r - 1.25 * mod, mod * 0.1);  // and so does the dedendum
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
  // Twist of the profile over the thickness: 2 * b * sin(helix) / (z * mod) radians. OpenSCAD turns
  // clockwise with a positive twist, so a right-hand helix takes a negative twist.
  turn = 2 * b * sin(helix_angle) / (z * mod) * 180 / PI;
  s_per_turn = ($fn > 0 ? $fn : 16);
  sl = max(4, ceil(abs(turn) * s_per_turn / 360));
  translate([0, 0, center ? -b / 2 : 0]) difference() {
    linear_extrude(b, twist = left_hand ? turn : -turn, slices = sl,
                   convexity = 10) polygon(pts);
    if (bore > 0) translate([0, 0, -1]) shaft_bore(bore, b + 2, keyway, key_width, key_depth);
  }
}'''

HERRINGBONE_GEAR = '''module herringbone_gear(mod = 1, teeth = 20, thickness = 10, helix_angle = 20, left_hand = false, pressure_angle = 20, backlash = 0, bore = 0, groove = 0, center = false, keyway = false, key_width = 0, key_depth = 0) {
  // Herringbone (double helical) gear (written by OpenSCAD GUI Mejorada).
  // Two helical halves of opposite hand, meeting phase-aligned (same untwisted profile) at the
  // center plane, so the axial thrust of one half cancels the other's -- no thrust bearing
  // needed, unlike a plain helical gear. groove opens a small gap at the center plane (hobbing
  // clearance on a real gear; usually 0 for 3D printing). Same involute profile as helical_gear;
  // see that module for how the normal module and pressure angle relate to the transverse ones.
  // Meshes like a plain helical pair: with ANOTHER ONE of OPPOSITE hand (left_hand toggled).
  z = max(3, round(teeth));
  half_b = max(0.001, (thickness - groove) / 2);
  mt = mod / cos(helix_angle);                        // transverse module
  at = atan(tan(pressure_angle) / cos(helix_angle));  // transverse pressure angle
  r = mt * z / 2;                       // pitch radius
  rb = r * cos(at);                     // base radius
  ra = r + mod;                         // the addendum uses the normal module
  rf = max(r - 1.25 * mod, mod * 0.1);  // and so does the dedendum
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
  // Twist of one half over half_b: 2 * half_b * sin(helix) / (z * mod) radians, in degrees.
  turn = 2 * half_b * sin(helix_angle) / (z * mod) * 180 / PI;
  s_per_turn = ($fn > 0 ? $fn : 16);
  sl = max(4, ceil(abs(turn) * s_per_turn / 360));
  module half_profile() {
    linear_extrude(half_b, twist = left_hand ? -turn : turn, slices = sl,
                   convexity = 10) polygon(pts);
  }
  translate([0, 0, center ? -thickness / 2 : 0]) difference() {
    union() {
      // Lower half: mirrored, so it has zero twist where it meets the center plane.
      translate([0, 0, half_b]) mirror([0, 0, 1]) half_profile();
      // Upper half: zero twist at its own base, which sits at the center plane (plus the groove).
      translate([0, 0, half_b + groove]) half_profile();
    }
    if (bore > 0) translate([0, 0, -1]) shaft_bore(bore, thickness + 2, keyway, key_width, key_depth);
  }
}'''

WORM = '''module worm(mod = 2, starts = 1, diam = 20, length = 30, pressure_angle = 20, left_hand = false, backlash = 0, bore = 0, center = false, keyway = false, key_width = 0, key_depth = 0) {
  // Worm screw thread (written by OpenSCAD GUI Mejorada).
  // mod is the AXIAL module (the one the thread is cut with, like a lead screw on a lathe);
  // axial pitch px = PI * mod. starts: number of parallel threads (entradas/filetes); lead
  // L = starts * px. diam is the PITCH diameter, a free design choice (see worm_gear's hint for
  // the usual bounds). Addendum/dedendum follow the same convention as the other gears here:
  // head = mod, root = 1.25 * mod. pressure_angle is the flank half-angle measured in the AXIAL
  // plane, like an ACME thread (14.5 deg simple/double, 20 deg reinforced, 29-30 deg for long pitches).
  n = max(1, round(starts));
  r = diam / 2;
  ra = r + mod;
  rf = max(r - 1.25 * mod, mod * 0.1);
  px = PI * mod;
  lead = n * px;
  t = tan(pressure_angle);
  // Half the AXIAL thickness of the thread at radius R (straight flank, like an ACME thread).
  // A profile drawn in the TRANSVERSE (XY) plane and swept with linear_extrude(twist = ...)
  // reproduces this axial profile at every Z because, near a thread crossing the axial cutting
  // plane, the local twist is linear in Z: an axial half-thickness h there corresponds to a twist
  // of h turns of the full lead, i.e. a circumferential half-angle of h * 360 / lead degrees.
  function half(R) = max(0, px / 4 - (R - r) * t) * 360 / lead;
  nn = 2;
  flank = [for (k = [0 : nn]) rf + (ra - rf) * k / nn];
  pts = [for (i = [0 : n - 1]) let(c = i * 360 / n) each concat(
           [for (R = flank) [R * cos(c - half(R)), R * sin(c - half(R))]],
           [for (k = [nn : -1 : 0]) let(R = flank[k]) [R * cos(c + half(R)), R * sin(c + half(R))]])];
  turn = 360 * length / lead;
  s_per_turn = ($fn > 0 ? $fn : 16);
  sl = max(8, ceil(abs(turn) * s_per_turn / 360));
  fn_core = ($fn > 0 ? $fn : 16);
  translate([0, 0, center ? -length / 2 : 0]) difference() {
    union() {
      cylinder(h = length, r = rf, $fn = fn_core);
      linear_extrude(length, twist = left_hand ? turn : -turn, slices = sl,
                     convexity = 10) polygon(pts);
    }
    if (bore > 0) translate([0, 0, -1]) shaft_bore(bore, length + 2, keyway, key_width, key_depth);
  }
}'''

WORM_GEAR = '''module worm_gear(mod = 2, teeth = 30, worm_diam = 20, worm_starts = 1, thickness = 10, pressure_angle = 20, left_hand = false, backlash = 0, bore = 0, center = false, keyway = false, key_width = 0, key_depth = 0) {
  // Worm wheel / rueda corona (written by OpenSCAD GUI Mejorada).
  // mod is the mating worm's AXIAL module, which is this wheel's TRANSVERSE circular module
  // directly (circular pitch at the pitch circle = PI * mod): unlike helical_gear, mod here is
  // NOT divided by cos(helix) first, because that is how a worm pair is specified (Shigley,
  // Sec. 15-6: translated, a worm's normal diametral pitch equals that of a helical gear with
  // the same helix (psi) as the worm's lead angle (lambda). The helix (lead) angle is derived from the worm it mates
  // with: tan(lead_angle) = worm_starts * mod / worm_diam. Pitch diameter = mod * teeth, same
  // formula as a spur gear.
  z = max(3, round(teeth));
  ha = atan(worm_starts * mod / max(0.001, worm_diam));   // lead angle of the worm = helix angle here
  at = atan(tan(pressure_angle) / cos(ha));
  r = mod * z / 2;                      // pitch radius (mod is already the transverse module)
  rb = r * cos(at);
  ra = r + mod;
  rf = max(r - 1.25 * mod, mod * 0.1);
  r0 = max(rb, rf);
  function inv(a) = tan(a) - a * PI / 180;
  function half(R) = max(0, ((PI * mod / 2 - backlash / 2) / (2 * r) + inv(at)
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
  turn = 2 * thickness * tan(ha) / (z * mod) * 180 / PI;
  s_per_turn = ($fn > 0 ? $fn : 16);
  sl = max(4, ceil(abs(turn) * s_per_turn / 360));
  translate([0, 0, center ? -thickness / 2 : 0]) difference() {
    linear_extrude(thickness, twist = left_hand ? turn : -turn, slices = sl,
                   convexity = 10) polygon(pts);
    if (bore > 0) translate([0, 0, -1]) shaft_bore(bore, thickness + 2, keyway, key_width, key_depth);
  }
}'''

RACK = '''module rack(mod = 1, teeth = 10, thickness = 5, base = 5, pressure_angle = 20, backlash = 0, helix_angle = 0, left_hand = false, center = false) {
  // Rack of the module system (written by OpenSCAD GUI Mejorada).
  // It is the "basic rack" that defines the tooth form: straight flanks inclined at the pressure
  // angle, pitch PI * mod, addendum mod and dedendum 1.25 * mod. It meshes with any gear of the
  // same module. The pitch line sits at y = 0 and the teeth point towards +Y, so the gear goes
  // with its centre one pitch radius above it; each tooth is centred in its pitch, so the
  // spaces fall on the multiples of the pitch.
  // With helix_angle it meshes with a helical gear OF THE SAME HAND: the tooth is a straight line
  // at that angle to the gear axis, so the profile is sheared tan(helix) per mm of thickness.
  // Then mod and pressure_angle are the NORMAL ones and the pitch and flanks come from the
  // transverse ones, as in helical_gear. The ends follow the slant of the teeth; to square them
  // off, trim them with a difference.
  z = max(1, round(teeth));
  mt = mod / cos(helix_angle);                        // transverse module
  at = atan(tan(pressure_angle) / cos(helix_angle));  // transverse pressure angle
  p = PI * mt;                  // pitch (in the transverse plane)
  total = z * p;                // total length
  ha = mod;                     // addendum (above the pitch line), with the normal module
  hf = 1.25 * mod;              // dedendum, likewise
  t = tan(at);
  hp = p / 4 - backlash / 4;    // half the tooth thickness at the pitch line
  // With a large pressure angle the flanks of two neighbouring teeth cross before reaching the
  // bottom: the space ends in a V instead of a flat land.
  y_v = (2 * hp - p) / (2 * t);
  y_bot = max(-hf, y_v);
  land = y_v <= -hf + 1e-12;    // is there a flat land at the bottom of the space?
  hb = hp - y_bot * t;          // half thickness at the bottom of the space
  tip = hp - ha * t;            // half thickness at the tip (if not positive, it ends in a point)
  y_back = -hf - max(0, base);
  pts = concat(
    land ? [[0, y_bot]] : [],
    [for (i = [0 : z - 1]) let(c = (i + 0.5) * p) each concat(
       [[c - hb, y_bot]],
       tip > 0 ? [[c - tip, ha], [c + tip, ha]] : [[c, hp / t]],
       [[c + hb, y_bot]])],
    land ? [[total, y_bot]] : [],
    [[total, y_back], [0, y_back]]);
  shear = (left_hand ? -1 : 1) * tan(helix_angle);    // how far the teeth shift with the thickness
  translate([0, 0, center ? -thickness / 2 : 0])
    multmatrix([[1, 0, shear, 0], [0, 1, 0, 0], [0, 0, 1, 0]])
      linear_extrude(thickness) polygon(pts);
}'''

BEVEL_GEAR = '''module bevel_gear(mod = 1, teeth = 20, mate_teeth = 20, shaft_angle = 90, face_width = 4, pressure_angle = 20, backlash = 0, bore = 0, keyway = false, key_width = 0, key_depth = 0) {
  // Straight bevel gear (written by OpenSCAD GUI Mejorada).
  // Machinery's Handbook 27, "Rules and Formulas for Calculating Dimensions of Milled Bevel
  // Gears", p. 2087. The cone apex sits at the ORIGIN and the gear faces +Z, so its mate is the
  // same part turned by the shaft angle: there is no need to move it.
  // The tooth comes from Tredgold's virtual gear (a spur gear of the same module with
  // teeth/cos(cone) teeth) and the profile is swept towards the apex, which makes the face,
  // pitch and root cones exact.
  z = max(3, round(teeth));
  zm = max(3, round(mate_teeth));
  g = atan2(sin(shaft_angle), zm / z + cos(shaft_angle));   // pitch cone angle
  C = mod * z / (2 * sin(g));                               // outer cone distance
  ha = atan(mod / C);                                       // addendum angle
  hf = atan(1.25 * mod / C);                                // dedendum angle
  // The back face is turned flat, in the plane where the face cone reaches the outside
  // diameter D + 2*mod*cos(g): this is the "vertex distance" J of the Handbook.
  zo = (mod * z / 2 + mod * cos(g)) / tan(g + ha);
  F = min(max(0.01, face_width), zo / cos(g) * 0.95);       // face width, along the pitch cone
  zi = zo - F * cos(g);
  rv = mod * (z / cos(g)) / 2;                              // pitch radius of the virtual gear
  rbv = rv * cos(pressure_angle);
  rf = max(rv - 1.25 * mod, mod * 0.1);
  r0 = max(rbv, rf);
  function inv(a) = tan(a) - a * PI / 180;
  // Half the tooth thickness AROUND THE AXIS: that of the virtual gear, divided by cos(cone).
  function half(p) = max(0, ((PI * mod / 2 - backlash / 2) / (2 * rv) + inv(pressure_angle)
                             - inv(acos(min(1, rbv / p)))) * 180 / PI) / cos(g);
  // A point at p from the centre of the virtual gear lies on the cone g + atan((p - rv)/C).
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
    // Sweep towards the apex: the front face profile is the back one, scaled.
    translate([0, 0, zi])
      linear_extrude(zo - zi, scale = zo / zi) polygon([for (q = pts) q * zi / zo]);
    if (bore > 0) translate([0, 0, -1]) shaft_bore(bore, zo + 2, keyway, key_width, key_depth);
  }
}'''

PULLEY = '''module pulley(section = "XL", teeth = 20, width = 6, bore = 0, flange = "none",
               flange_height = 1.5, center = false, keyway = false, key_width = 0, key_depth = 0) {
  // Toothed pulley for a synchronous belt (written by OpenSCAD GUI Mejorada).
  // Classic trapezoidal sections ANSI/RMA IP-24 (Machinery's Handbook 27, tables 40 and 44):
  // pitch, tooth angle, height (ht) and pitch-line tooth width (bt), and how far the pitch
  // circle PD = z*pitch/PI lies above the outside one (outside diameter = PD - 2*PLD).
  // The groove is the negative of the belt tooth, with straight flanks (without the ra/rr radii
  // of the table, just as the rack has none either).
  // The flanges are plain cylindrical collars standing flange_height above the outside
  // diameter, on one side or both: without them the belt can slip off along the axis.
  // The flange value is written in the language of the interface, so all of them are accepted.
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
  tip_half = max(0, bt / 2 - (ht + pld) * t);      // half width of the groove at the bottom
  top_half = max(0, bt / 2 - pld * t);             // half width of the groove at the mouth
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
  fn_c = $fn > 0 ? $fn : 16;
  function flange_is(names) = len([for (x = names) if (x == flange) 1]) > 0;
  both = flange_is(["ambas", "both", "les deux", "beide", "entrambe"]);
  bot = both || flange_is(["inferior", "bottom", "inférieur", "unten", "inferiore"]) ? max(0, flange_height) : 0;
  top = both || flange_is(["superior", "top", "supérieur", "oben", "superiore"]) ? max(0, flange_height) : 0;
  total = bot + width + top;
  fd = outer_d + 2 * max(0, flange_height);
  translate([0, 0, center ? -total / 2 : 0]) difference() {
    union() {
      translate([0, 0, bot]) linear_extrude(width) polygon(pts);
      if (bot > 0) cylinder(h = bot, d = fd, $fn = fn_c);
      if (top > 0) translate([0, 0, bot + width]) cylinder(h = top, d = fd, $fn = fn_c);
    }
    if (bore > 0) translate([0, 0, -1]) shaft_bore(bore, total + 2, keyway, key_width, key_depth, $fn = fn_c);
  }
}'''

V_PULLEY = '''module v_pulley(section = "A", datum_d = 80, grooves = 1, bore = 0, center = false, keyway = false, key_width = 0, key_depth = 0) {
  // V-belt pulley (written by OpenSCAD GUI Mejorada).
  // Classic sections ANSI/RMA IP-20 (Machinery's Handbook 27, table 9): groove angle (ang) and
  // width at the mouth (bg) by ranges of pitch/datum diameter; hg (depth), Sg (spacing between
  // grooves) and Se (edge margin) are fixed per section. The face width follows from the
  // grooves: Sg*(grooves - 1) + 2*Se. Axisymmetric part (without the bottom radius RB of the
  // table, just as the rack and the toothed pulley have none):
  // a profile is revolved once with rotate_extrude.
  hg = section == "A" ? 11.684 : section == "B" ? 13.97 : section == "C" ? 19.05 : 25.908;
  se = section == "A" ? 9.525 : section == "B" ? 12.7 : section == "C" ? 17.4752 : 22.225;
  sg = section == "A" ? 15.875 : section == "B" ? 19.05 : section == "C" ? 25.4 : 36.5252;
  tier = section == "A" ? (datum_d <= 137.16 ? [34, 12.5476] : [38, 12.8016]) :
         section == "B" ? (datum_d <= 177.8 ? [34, 16.1798] : [38, 16.51]) :
         section == "C" ? (datum_d <= 202.946 ? [34, 22.3266] :
                            datum_d <= 304.8 ? [36, 22.5298] : [38, 22.733]) :
                           (datum_d <= 329.946 ? [34, 31.9886] :
                            datum_d <= 431.8 ? [36, 32.2834] : [38, 32.5782]);
  ang = tier[0]; bg = tier[1];
  ng = max(1, round(grooves));
  width = sg * (ng - 1) + 2 * se;
  t = tan(ang / 2);
  bot = bg / 2 - hg * t;
  r_top = datum_d / 2;
  r_bot = r_top - hg;
  profile = concat(
    [[r_top, 0]],
    [for (k = [0 : ng - 1]) let(zc = se + k * sg) each
       (bot > 0 ? [[r_top, zc - bg / 2], [r_bot, zc - bot], [r_bot, zc + bot], [r_top, zc + bg / 2]]
                : [[r_top, zc - bg / 2], [r_top - (bg / 2) / t, zc], [r_top, zc + bg / 2]])],
    [[r_top, width], [0, width], [0, 0]]);
  translate([0, 0, center ? -width / 2 : 0]) difference() {
    rotate_extrude($fn = $fn > 0 ? $fn : 16) polygon(profile);
    if (bore > 0) translate([0, 0, -1]) shaft_bore(bore, width + 2, keyway, key_width, key_depth);
  }
}'''

SPLINE = '''module spline(mod = 1, teeth = 20, length = 20, pressure_angle = 30, fillet_root = false, internal = false, hub_d = 0, clearance = 0, center = false) {
  // Involute spline by module, side fit (written by OpenSCAD GUI Mejorada).
  // ANSI B92.2M-1980, derived from ISO 4156 (Machinery's Handbook 27, table 13, p. 2179). The shaft
  // and the hub (internal = true) mesh in the same place, without moving or turning either: a
  // shaft tooth and a hub space are both centred on +X. clearance is the tooth thickness
  // modification es: it only thins the shaft, the hub always keeps the basic space width.
  z = max(3, round(teeth));
  // Table 13, times mod: [external major, internal major, minor, rack dimension hs, internal form].
  k = pressure_angle == 45 ? [0.8, 1.2, 1.2, 0.5, 0.8] :
      pressure_angle == 37.5 ? [0.9, 1.4, 1.4, 0.55, 0.9] :
      fillet_root ? [1, 1.8, 1.8, 0.6, 1] : [1, 1.5, 1.5, 0.6, 1];
  a = pressure_angle;
  d = mod * z;                          // pitch diameter
  rb = d / 2 * cos(a);                  // base radius
  es = internal ? 0 : max(0, clearance);
  function form(e) = 2 * sqrt(rb * rb + pow(max(0, d / 2 * sin(a) - (k[3] * mod + e / 2 / tan(a)) / sin(a)), 2));
  cf = 0.1 * mod;                       // form clearance
  dei = mod * (z + k[1]);               // internal major diameter
  dii = form(0) + 2 * cf;               // internal minor: always from the form diameter of the H/h fit
  dfi = mod * (z + k[4]) + 2 * cf;      // internal form diameter
  dee = mod * (z + k[0]) - es / tan(a); // external major diameter
  die = mod * (z - k[2]) - es / tan(a); // external minor diameter
  r_low = internal ? dii / 2 : die / 2;
  lo = max(rb, internal ? dii / 2 : form(es) / 2);    // the involute runs from lo to hi
  hi = internal ? dfi / 2 : dee / 2;
  high = internal ? dei / 2 : dee / 2;
  s = PI * mod / 2 - es;                // tooth thickness (or space width) on the pitch circle
  function inv(x) = tan(x) - x * PI / 180;
  // Half the tooth (or space), in degrees, at distance R from the centre.
  function half(R) = min(max(0, (s / d + inv(a) - inv(acos(min(1, rb / R)))) * 180 / PI), 179.9 / z);
  n = 8;
  flank = [for (j = [0 : n]) lo + (hi - lo) * j / n];
  root = r_low < lo - 1e-6;
  tip = high > hi + 1e-6;
  pts = [for (i = [0 : z - 1]) let(c = i * 360 / z) each concat(
           root ? [[r_low * cos(c - half(lo)), r_low * sin(c - half(lo))]] : [],
           [for (R = flank) [R * cos(c - half(R)), R * sin(c - half(R))]],
           tip ? [[high * cos(c - half(hi)), high * sin(c - half(hi))],
                  [high * cos(c + half(hi)), high * sin(c + half(hi))]] : [],
           [for (j = [n : -1 : 0]) let(R = flank[j]) [R * cos(c + half(R)), R * sin(c + half(R))]],
           root ? [[r_low * cos(c + half(lo)), r_low * sin(c + half(lo))]] : [])];
  translate([0, 0, center ? -length / 2 : 0]) linear_extrude(length, convexity = 10)
    if (internal) difference() {
      circle(d = hub_d > 0 ? hub_d : dei + 4 * mod);
      polygon(pts);
    }
    else polygon(pts);
}'''

# Lo usan los engranajes y las poleas, así que needed_definitions lo añade después de ellos.
SHAFT_BORE = '''module shaft_bore(d, h, keyway = false, key_width = 0, key_depth = 0) {
  // Shaft bore, optionally with a keyway on +X (written by OpenSCAD GUI Mejorada).
  // Metric parallel keys BS 4235-1, same sizes as ISO R773 (Machinery's Handbook 27, table 12):
  // [bore over, up to and including, keyway width b, depth in the hub t2]. The bottom of the
  // keyway lies d / 2 + t2 from the axis. key_width and key_depth replace the table values;
  // outside the table, without them, there is no keyway.
  table = [[6, 8, 2, 1], [8, 10, 3, 1.4], [10, 12, 4, 1.8], [12, 17, 5, 2.3], [17, 22, 6, 2.8],
           [22, 30, 8, 3.3], [30, 38, 10, 3.3], [38, 44, 12, 3.3], [44, 50, 14, 3.8], [50, 58, 16, 4.3],
           [58, 65, 18, 4.4], [65, 75, 20, 4.9], [75, 85, 22, 5.4], [85, 95, 25, 5.4], [95, 110, 28, 6.4],
           [110, 130, 32, 7.4], [130, 150, 36, 8.4], [150, 170, 40, 9.4], [170, 200, 45, 10.4], [200, 230, 50, 11.4],
           [230, 260, 56, 12.4], [260, 290, 63, 12.4], [290, 330, 70, 14.4], [330, 380, 80, 15.4], [380, 440, 90, 17.4],
           [440, 500, 100, 19.5]];
  row = [for (r = table) if (d > r[0] && d <= r[1]) r];
  b = key_width > 0 ? key_width : len(row) > 0 ? row[0][2] : 0;
  t2 = key_depth > 0 ? key_depth : len(row) > 0 ? row[0][3] : 0;
  cylinder(h = h, d = d, $fn = $fn > 0 ? $fn : 16);
  if (keyway && b > 0 && t2 > 0) translate([0, -b / 2, 0]) cube([d / 2 + t2, b, h]);
}'''

CAM = '''module cam(base_d = 40, lift = 10, rise_angle = 90, dwell_angle = 30, fall_angle = 90,
          motion = "cicloidal", thickness = 8, bore = 0, center = false) {
  // Plate cam (written by OpenSCAD GUI Mejorada).
  // The profile is the base radius plus the lift set by the chosen motion law, over the rise
  // angle; it stays up for the dwell angle, falls with the same law mirrored, and the rest of
  // the turn stays at the base radius. 4 classic laws from "Cams and Cam Design" (Machinery's
  // Handbook 27, pp. 2190-2192), normalized to lift 1 and angle 1 (t from 0 to 1).
  r0 = base_d / 2;
  rise = max(0, rise_angle); dwell = max(0, dwell_angle); fall = max(0, fall_angle);
  rest = max(0, 360 - rise - dwell - fall);
  step = 1;
  function mot(t) = motion == "velocidad_constante" ? t :
                     motion == "parabolica" ? (t <= 0.5 ? 2 * t * t : 1 - 2 * (1 - t) * (1 - t)) :
                     motion == "armonica" ? 0.5 * (1 - cos(180 * t)) :
                     t - sin(360 * t) / (2 * PI);                              // cycloidal (default)
  n_rise = max(1, ceil(rise / step));
  rise_pts = rise > 0 ? [for (i = [0 : n_rise - 1]) let(f = i / n_rise, r = r0 + lift * mot(f),
                          a = rise * f) [r * cos(a), r * sin(a)]] : [];
  n_dwell = max(1, ceil(dwell / step));
  dwell_pts = dwell > 0 ? [for (i = [0 : n_dwell - 1]) let(a = rise + dwell * i / n_dwell)
                           [(r0 + lift) * cos(a), (r0 + lift) * sin(a)]] : [];
  n_fall = max(1, ceil(fall / step));
  fall_pts = fall > 0 ? [for (i = [0 : n_fall - 1]) let(f = i / n_fall,
                          r = r0 + lift * (1 - mot(f)), a = rise + dwell + fall * f)
                         [r * cos(a), r * sin(a)]] : [];
  n_rest = max(1, ceil(rest / step));
  rest_pts = rest > 0 ? [for (i = [0 : n_rest - 1]) let(a = rise + dwell + fall + rest * i / n_rest)
                         [r0 * cos(a), r0 * sin(a)]] : [];
  profile = concat(rise_pts, dwell_pts, fall_pts, rest_pts);
  translate([0, 0, center ? -thickness / 2 : 0]) difference() {
    linear_extrude(thickness) polygon(profile);
    if (bore > 0) translate([0, 0, -1]) cylinder(h = thickness + 2, d = bore, $fn = $fn > 0 ? $fn : 16);
  }
}'''

PIPE_FLANGE = '''module pipe_flange(od = 230, thickness = 22.3, bolt_circle = 190.5, bolts = 8, hole = 19.05, bore = 0, face_d = 0, face_h = 0, hub_d = 0, hub_end_d = 0, length = 0, neck_length = 0, center = false) {
  // Pipe flange (written by OpenSCAD GUI Mejorada).
  // Gasket face at z = 0 and the body towards +Z: the raised face (face_d x face_h), then the
  // flange ring (od x thickness) and the hub, which narrows from hub_d at the back face to
  // hub_end_d and ends in a straight run of neck_length; length is measured from the gasket
  // face. Without a hub (hub_d = 0) it is a plate or blind flange; without a bore, a blind one.
  // The flange wizard fills in the sizes of ASME B16.5-2013 or EN 1092-1:2018. As both standards
  // draw them, the bolt holes straddle the X and Y axes. No fillet radii or weld bevel.
  fh = max(0, face_h);
  back = fh + thickness;
  he = hub_end_d > 0 ? hub_end_d : hub_d;
  top = hub_d > 0 ? max(length, back) : back;
  cone = max(back, top - max(0, neck_length));
  rb = max(0, bore) / 2;
  profile = concat(
    [[rb, 0]],
    fh > 0 ? [[face_d / 2, 0], [face_d / 2, fh]] : [],
    [[od / 2, fh], [od / 2, back]],
    hub_d > 0 ? concat([[hub_d / 2, back], [he / 2, cone]], cone < top ? [[he / 2, top]] : []) : [],
    [[rb, top]]);
  translate([0, 0, center ? -top / 2 : 0]) difference() {
    rotate_extrude($fn = $fn > 0 ? $fn : 16) polygon(profile);
    if (bolts > 0 && hole > 0)
      for (k = [0 : bolts - 1]) rotate(180 / bolts + 360 * k / bolts)
        translate([bolt_circle / 2, 0, -1]) cylinder(h = back + 2, d = hole, $fn = $fn > 0 ? $fn : 16);
  }
}'''

CAMSHAFT_MAIN_SHAFT = '''module camshaft_main_shaft(length = 250, d = 25) {
  // Main shaft of a camshaft (written by OpenSCAD GUI Mejorada): a plain cylinder along Z,
  // from z = 0 to z = length. The lobes (cam_lobe) are placed on it by their own position.
  cylinder(h = length, d = d, $fn = $fn > 0 ? $fn : 16);
}'''

CAM_LOBE = '''module cam_lobe(base_r = 15, lift = 8, width = 12, rise_angle = 110, dwell_angle = 20, fall_angle = 110,
                motion = "cicloidal", angle = 0, position = 20, step = 1, profile = "ley", nose_r = 0) {
  // Camshaft lobe (written by OpenSCAD GUI Mejorada), extruded along Z (the camshaft axis) and
  // centred on z = position, with its nose (full lift) pointing at angle degrees.
  // profile = "ley": base radius plus the lift given by the motion law. It rises over rise_angle,
  // stays at full lift for dwell_angle centred on the nose, falls over fall_angle and the rest of
  // the turn stays on the base circle; rise and fall may differ (asymmetric lobe). Same 4 laws as
  // the plate cam ("Cams and Cam Design", Machinery's Handbook 27, pp. 2190-2192).
  // The other profiles are geometric constructions, not from a standard. All of them keep the
  // base radius and the lift exact and, being convex hulls, cannot cross themselves:
  //   "circular"   disc of the base radius, no lift;
  //   "excentrico" circle of radius base_r + lift/2, moved lift/2 towards the nose;
  //   "eliptico"   hull of the base circle and an ellipse (base_r + lift/2 by base_r) moved lift/2;
  //   "periforme"  hull of the base circle and a nose circle of radius nose_r reaching base_r + lift.
  // step is degrees per point: circles use $fn = ceil(360 / step).
  rise = max(0, rise_angle); dwell = max(0, dwell_angle); fall = max(0, fall_angle);
  rest = max(0, 360 - rise - dwell - fall);
  s = max(0.1, step);
  n = max(3, ceil(360 / s));
  h = max(0, lift);
  function mot(t) = motion == "velocidad_constante" ? t :
                     motion == "parabolica" ? (t <= 0.5 ? 2 * t * t : 1 - 2 * (1 - t) * (1 - t)) :
                     motion == "armonica" ? 0.5 * (1 - cos(180 * t)) :
                     t - sin(360 * t) / (2 * PI);                              // cycloidal (default)
  // Polar points of one stretch: it starts at angle a0, spans span degrees, radius r(f) for f in [0, 1).
  function stretch(a0, span, kind) = span <= 0 ? [] :
    let(k = max(1, ceil(span / s)))
    [for (i = [0 : k - 1]) let(f = i / k,
       r = base_r + h * (kind == 0 ? mot(f) : kind == 1 ? 1 : kind == 2 ? 1 - mot(f) : 0),
       a = a0 + span * f) [r * cos(a), r * sin(a)]];
  a0 = -rise - dwell / 2;
  law = concat(stretch(a0, rise, 0), stretch(a0 + rise, dwell, 1),
               stretch(a0 + rise + dwell, fall, 2), stretch(a0 + rise + dwell + fall, rest, 3));
  translate([0, 0, position - width / 2]) rotate(angle) linear_extrude(width)
    if (profile == "circular") circle(base_r, $fn = n);
    else if (profile == "excentrico") translate([h / 2, 0]) circle(base_r + h / 2, $fn = n);
    else if (profile == "eliptico") hull() {
      circle(base_r, $fn = n);
      translate([h / 2, 0]) scale([base_r + h / 2, base_r]) circle(1, $fn = n);
    }
    else if (profile == "periforme") hull() {
      circle(base_r, $fn = n);
      if (nose_r > 0) translate([base_r + h - nose_r, 0]) circle(nose_r, $fn = n);
    }
    else polygon(law);
}'''

LIBRARY = {"cube_edges": CUBE_EDGES, "cylinder_edges": CYLINDER_EDGES, "spur_gear": SPUR_GEAR,
           "helical_gear": HELICAL_GEAR, "herringbone_gear": HERRINGBONE_GEAR, "rack": RACK,
           "bevel_gear": BEVEL_GEAR, "worm": WORM, "worm_gear": WORM_GEAR, "pulley": PULLEY,
           "v_pulley": V_PULLEY, "spline": SPLINE, "cam": CAM, "shaft_bore": SHAFT_BORE,
           "pipe_flange": PIPE_FLANGE,
           "camshaft_main_shaft": CAMSHAFT_MAIN_SHAFT, "cam_lobe": CAM_LOBE}

# Versiones anteriores que ya pueden estar en archivos guardados. Al abrir el archivo se
# reconocen como nuestras y se sustituyen por la versión actual (no se conservan como código
# del usuario). No borrar: los archivos viejos dejarían de actualizarse.
PREVIOUS_VERSIONS = {
    # 2026-11-03: fase 1 del árbol de levas, solo con el perfil por ley (sin profile ni nose_r).
    "cam_lobe": ('''module cam_lobe(base_r = 15, lift = 8, width = 12, rise_angle = 110, dwell_angle = 20, fall_angle = 110,
                motion = "cicloidal", angle = 0, position = 20, step = 1) {
  // Camshaft lobe (written by OpenSCAD GUI Mejorada).
  // The profile is the base radius plus the lift given by the motion law: it rises over
  // rise_angle, stays at full lift for dwell_angle centred on the nose, falls over fall_angle
  // and the rest of the turn stays on the base circle. The nose points at angle degrees, and
  // rise and fall may differ (asymmetric lobe). Same 4 laws as the plate cam ("Cams and Cam
  // Design", Machinery's Handbook 27, pp. 2190-2192), normalized to lift 1 and angle 1.
  // Extruded along Z (the camshaft axis), centred on z = position; step is degrees per point.
  rise = max(0, rise_angle); dwell = max(0, dwell_angle); fall = max(0, fall_angle);
  rest = max(0, 360 - rise - dwell - fall);
  s = max(0.1, step);
  function mot(t) = motion == "velocidad_constante" ? t :
                     motion == "parabolica" ? (t <= 0.5 ? 2 * t * t : 1 - 2 * (1 - t) * (1 - t)) :
                     motion == "armonica" ? 0.5 * (1 - cos(180 * t)) :
                     t - sin(360 * t) / (2 * PI);                              // cycloidal (default)
  // Polar points of one stretch: it starts at angle a0, spans span degrees, radius r(f) for f in [0, 1).
  function stretch(a0, span, kind) = span <= 0 ? [] :
    let(n = max(1, ceil(span / s)))
    [for (i = [0 : n - 1]) let(f = i / n,
       r = base_r + lift * (kind == 0 ? mot(f) : kind == 1 ? 1 : kind == 2 ? 1 - mot(f) : 0),
       a = a0 + span * f) [r * cos(a), r * sin(a)]];
  a0 = angle - rise - dwell / 2;
  profile = concat(stretch(a0, rise, 0), stretch(a0 + rise, dwell, 1),
                   stretch(a0 + rise + dwell, fall, 2), stretch(a0 + rise + dwell + fall, rest, 3));
  translate([0, 0, position - width / 2]) linear_extrude(width) polygon(profile);
}''',),
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
    # 2026-11-02: el valor de flange solo se entendía en español.
    "pulley": ('''module pulley(section = "XL", teeth = 20, width = 6, bore = 0, flange = "ninguna",
               flange_height = 1.5, center = false) {
  // Toothed pulley for a synchronous belt (written by OpenSCAD GUI Mejorada).
  // Classic trapezoidal sections ANSI/RMA IP-24 (Machinery's Handbook 27, tables 40 and 44):
  // pitch, tooth angle, height (ht) and pitch-line tooth width (bt), and how far the pitch
  // circle PD = z*pitch/PI lies above the outside one (outside diameter = PD - 2*PLD).
  // The groove is the negative of the belt tooth, with straight flanks (without the ra/rr radii
  // of the table, just as the rack has none either).
  // The flanges are plain cylindrical collars standing flange_height above the outside
  // diameter, on one side or both: without them the belt can slip off along the axis.
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
  tip_half = max(0, bt / 2 - (ht + pld) * t);      // half width of the groove at the bottom
  top_half = max(0, bt / 2 - pld * t);             // half width of the groove at the mouth
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
}''',
               # 2026-11-02: sin cuñero.
               '''module pulley(section = "XL", teeth = 20, width = 6, bore = 0, flange = "none",
               flange_height = 1.5, center = false) {
  // Toothed pulley for a synchronous belt (written by OpenSCAD GUI Mejorada).
  // Classic trapezoidal sections ANSI/RMA IP-24 (Machinery's Handbook 27, tables 40 and 44):
  // pitch, tooth angle, height (ht) and pitch-line tooth width (bt), and how far the pitch
  // circle PD = z*pitch/PI lies above the outside one (outside diameter = PD - 2*PLD).
  // The groove is the negative of the belt tooth, with straight flanks (without the ra/rr radii
  // of the table, just as the rack has none either).
  // The flanges are plain cylindrical collars standing flange_height above the outside
  // diameter, on one side or both: without them the belt can slip off along the axis.
  // The flange value is written in the language of the interface, so all of them are accepted.
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
  tip_half = max(0, bt / 2 - (ht + pld) * t);      // half width of the groove at the bottom
  top_half = max(0, bt / 2 - pld * t);             // half width of the groove at the mouth
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
  fn_c = $fn > 0 ? $fn : 16;
  function flange_is(names) = len([for (x = names) if (x == flange) 1]) > 0;
  both = flange_is(["ambas", "both", "les deux", "beide", "entrambe"]);
  bot = both || flange_is(["inferior", "bottom", "inférieur", "unten", "inferiore"]) ? max(0, flange_height) : 0;
  top = both || flange_is(["superior", "top", "supérieur", "oben", "superiore"]) ? max(0, flange_height) : 0;
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
}''',),
    # 2026-11-02: sin cuñero.
    "spur_gear": ('''module spur_gear(mod = 1, teeth = 20, thickness = 5, pressure_angle = 20, backlash = 0, bore = 0, center = false) {
  // Involute spur gear by module (written by OpenSCAD GUI Mejorada).
  // Pitch diameter = mod * teeth; outside = mod * (teeth + 2); two gears of the same module
  // mesh with their centres mod * (z1 + z2) / 2 apart. backlash: clearance in mm between the two.
  z = max(3, round(teeth));
  r = mod * z / 2;                      // pitch radius
  rb = r * cos(pressure_angle);         // base radius (the involute starts from it)
  ra = r + mod;                         // outside radius
  rf = max(r - 1.25 * mod, mod * 0.1);  // root radius
  r0 = max(rb, rf);
  function inv(a) = tan(a) - a * PI / 180;   // involute, in radians, of an angle in degrees
  // Half the tooth thickness, in degrees, at distance R from the centre.
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
}''',),
    "helical_gear": ('''module helical_gear(mod = 1, teeth = 20, thickness = 10, helix_angle = 20, left_hand = false, pressure_angle = 20, backlash = 0, bore = 0, center = false) {
  // Involute helical gear (written by OpenSCAD GUI Mejorada).
  // mod and pressure_angle are the NORMAL ones (measured perpendicular to the tooth). In the
  // transverse plane they are larger: mt = mod / cos(helix), tan(at) = tan(pressure_angle) / cos(helix).
  // Pitch diameter = mod * teeth / cos(helix). Two gears of the same module and helix angle,
  // one right-handed and one left-handed, mesh at mod * (z1 + z2) / (2 * cos(helix)).
  z = max(3, round(teeth));
  b = max(0.001, thickness);
  mt = mod / cos(helix_angle);                        // transverse module
  at = atan(tan(pressure_angle) / cos(helix_angle));  // transverse pressure angle
  r = mt * z / 2;                       // pitch radius
  rb = r * cos(at);                     // base radius
  ra = r + mod;                         // the addendum uses the normal module
  rf = max(r - 1.25 * mod, mod * 0.1);  // and so does the dedendum
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
  // Twist of the profile over the thickness: 2 * b * sin(helix) / (z * mod) radians. OpenSCAD turns
  // clockwise with a positive twist, so a right-hand helix takes a negative twist.
  turn = 2 * b * sin(helix_angle) / (z * mod) * 180 / PI;
  translate([0, 0, center ? -b / 2 : 0]) difference() {
    linear_extrude(b, twist = left_hand ? turn : -turn, slices = max(8, ceil(turn / 2)),
                   convexity = 10) polygon(pts);
    if (bore > 0) translate([0, 0, -1]) cylinder(h = b + 2, d = bore);
  }
}''',),
    "bevel_gear": ('''module bevel_gear(mod = 1, teeth = 20, mate_teeth = 20, shaft_angle = 90, face_width = 4, pressure_angle = 20, backlash = 0, bore = 0) {
  // Straight bevel gear (written by OpenSCAD GUI Mejorada).
  // Machinery's Handbook 27, "Rules and Formulas for Calculating Dimensions of Milled Bevel
  // Gears", p. 2087. The cone apex sits at the ORIGIN and the gear faces +Z, so its mate is the
  // same part turned by the shaft angle: there is no need to move it.
  // The tooth comes from Tredgold's virtual gear (a spur gear of the same module with
  // teeth/cos(cone) teeth) and the profile is swept towards the apex, which makes the face,
  // pitch and root cones exact.
  z = max(3, round(teeth));
  zm = max(3, round(mate_teeth));
  g = atan2(sin(shaft_angle), zm / z + cos(shaft_angle));   // pitch cone angle
  C = mod * z / (2 * sin(g));                               // outer cone distance
  ha = atan(mod / C);                                       // addendum angle
  hf = atan(1.25 * mod / C);                                // dedendum angle
  // The back face is turned flat, in the plane where the face cone reaches the outside
  // diameter D + 2*mod*cos(g): this is the "vertex distance" J of the Handbook.
  zo = (mod * z / 2 + mod * cos(g)) / tan(g + ha);
  F = min(max(0.01, face_width), zo / cos(g) * 0.95);       // face width, along the pitch cone
  zi = zo - F * cos(g);
  rv = mod * (z / cos(g)) / 2;                              // pitch radius of the virtual gear
  rbv = rv * cos(pressure_angle);
  rf = max(rv - 1.25 * mod, mod * 0.1);
  r0 = max(rbv, rf);
  function inv(a) = tan(a) - a * PI / 180;
  // Half the tooth thickness AROUND THE AXIS: that of the virtual gear, divided by cos(cone).
  function half(p) = max(0, ((PI * mod / 2 - backlash / 2) / (2 * rv) + inv(pressure_angle)
                             - inv(acos(min(1, rbv / p)))) * 180 / PI) / cos(g);
  // A point at p from the centre of the virtual gear lies on the cone g + atan((p - rv)/C).
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
    // Sweep towards the apex: the front face profile is the back one, scaled.
    translate([0, 0, zi])
      linear_extrude(zo - zi, scale = zo / zi) polygon([for (q = pts) q * zi / zo]);
    if (bore > 0) translate([0, 0, -1]) cylinder(h = zo + 2, d = bore);
  }
}''',),
    "v_pulley": ('''module v_pulley(section = "A", datum_d = 80, grooves = 1, bore = 0, center = false) {
  // V-belt pulley (written by OpenSCAD GUI Mejorada).
  // Classic sections ANSI/RMA IP-20 (Machinery's Handbook 27, table 9): groove angle (ang) and
  // width at the mouth (bg) by ranges of pitch/datum diameter; hg (depth), Sg (spacing between
  // grooves) and Se (edge margin) are fixed per section. The face width follows from the
  // grooves: Sg*(grooves - 1) + 2*Se. Axisymmetric part (without the bottom radius RB of the
  // table, just as the rack and the toothed pulley have none):
  // a profile is revolved once with rotate_extrude.
  hg = section == "A" ? 11.684 : section == "B" ? 13.97 : section == "C" ? 19.05 : 25.908;
  se = section == "A" ? 9.525 : section == "B" ? 12.7 : section == "C" ? 17.4752 : 22.225;
  sg = section == "A" ? 15.875 : section == "B" ? 19.05 : section == "C" ? 25.4 : 36.5252;
  tier = section == "A" ? (datum_d <= 137.16 ? [34, 12.5476] : [38, 12.8016]) :
         section == "B" ? (datum_d <= 177.8 ? [34, 16.1798] : [38, 16.51]) :
         section == "C" ? (datum_d <= 202.946 ? [34, 22.3266] :
                            datum_d <= 304.8 ? [36, 22.5298] : [38, 22.733]) :
                           (datum_d <= 329.946 ? [34, 31.9886] :
                            datum_d <= 431.8 ? [36, 32.2834] : [38, 32.5782]);
  ang = tier[0]; bg = tier[1];
  ng = max(1, round(grooves));
  width = sg * (ng - 1) + 2 * se;
  t = tan(ang / 2);
  bot = bg / 2 - hg * t;
  r_top = datum_d / 2;
  r_bot = r_top - hg;
  profile = concat(
    [[r_top, 0]],
    [for (k = [0 : ng - 1]) let(zc = se + k * sg) each
       (bot > 0 ? [[r_top, zc - bg / 2], [r_bot, zc - bot], [r_bot, zc + bot], [r_top, zc + bg / 2]]
                : [[r_top, zc - bg / 2], [r_top - (bg / 2) / t, zc], [r_top, zc + bg / 2]])],
    [[r_top, width], [0, width], [0, 0]]);
  translate([0, 0, center ? -width / 2 : 0]) difference() {
    rotate_extrude() polygon(profile);
    if (bore > 0) translate([0, 0, -1]) cylinder(h = width + 2, d = bore);
  }
}''',),
}


def _normalized(text: str) -> str:
    return " ".join(text.split())


_NORMALIZED = {_normalized(code): name for name, code in LIBRARY.items()}
_NORMALIZED.update({_normalized(code): name for name, codes in PREVIOUS_VERSIONS.items() for code in codes})
_NORMALIZED.update({_normalized(code): name for name, code in SPANISH_COMMENTS.items()})


def library_name(text: str) -> str:
    """Nombre del módulo si ``text`` es una definición de la biblioteca sin cambios; si no, ''."""
    return _NORMALIZED.get(_normalized(text), "")


def needed_definitions(code: str) -> list[str]:
    """Definiciones que hay que añadir: módulos usados en ``code`` que no están definidos en él.
    Un módulo puede usar otro que va después en ``LIBRARY``: se busca también en lo ya añadido."""
    out = []
    for name, definition in LIBRARY.items():
        used = re.search(rf"(?<![\w$]){name}\s*\(", code)
        defined = re.search(rf"\bmodule\s+{name}\s*\(", code)
        if used and not defined:
            out.append(definition)
            code += "\n" + definition
    return out
