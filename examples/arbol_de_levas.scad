// Generado con OpenSCAD GUI Mejorada

// Árbol de levas, fase 2: un lóbulo de cada perfil, girados 72° entre sí.
//
// Cada pieza es una llamada con sus medidas, y su definición va al final del archivo:
//   camshaft_main_shaft(length, d)  eje a lo largo de Z, de z = 0 a z = length.
//   cam_lobe(...)                   lóbulo centrado en z = position, con la punta hacia angle grados.
//   profile = "ley" | "circular" | "excentrico" | "eliptico" | "periforme" (este usa nose_r).
// Para cambiar las medidas desde otro programa, basta con reescribir los números de estas llamadas
// (por ejemplo "position = 60") y abrir o renderizar el archivo: no hace falta tocar los módulos.
// Para añadir un lóbulo, copie una línea de cam_lobe y cambie position y angle.
camshaft_main_shaft(length = 250, d = 25);
cam_lobe(base_r = 15, lift = 8, width = 12, rise_angle = 110, dwell_angle = 20, fall_angle = 110, motion = "cicloidal", angle = 0, position = 30, step = 1, profile = "ley");
cam_lobe(base_r = 15, lift = 8, width = 12, rise_angle = 110, dwell_angle = 20, fall_angle = 110, motion = "cicloidal", angle = 72, position = 75, step = 1, profile = "circular"); // cam_lobe001
cam_lobe(base_r = 15, lift = 8, width = 12, rise_angle = 110, dwell_angle = 20, fall_angle = 110, motion = "cicloidal", angle = 144, position = 120, step = 1, profile = "excentrico"); // cam_lobe002
cam_lobe(base_r = 15, lift = 8, width = 12, rise_angle = 110, dwell_angle = 20, fall_angle = 110, motion = "cicloidal", angle = 216, position = 165, step = 1, profile = "eliptico"); // cam_lobe003
cam_lobe(base_r = 15, lift = 8, width = 12, rise_angle = 110, dwell_angle = 20, fall_angle = 110, motion = "cicloidal", angle = 288, position = 210, step = 1, profile = "periforme", nose_r = 6); // cam_lobe004

module camshaft_main_shaft(length = 250, d = 25) {
  // Main shaft of a camshaft (written by OpenSCAD GUI Mejorada): a plain cylinder along Z,
  // from z = 0 to z = length. The lobes (cam_lobe) are placed on it by their own position.
  cylinder(h = length, d = d);
}

module cam_lobe(base_r = 15, lift = 8, width = 12, rise_angle = 110, dwell_angle = 20, fall_angle = 110,
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
}
