// Generado con OpenSCAD GUI Mejorada

// Árbol de levas, fase 1: eje y un lóbulo.
//
// Cada pieza es una llamada con sus medidas, y su definición va al final del archivo:
//   camshaft_main_shaft(length, d)  eje a lo largo de Z, de z = 0 a z = length.
//   cam_lobe(...)                   lóbulo centrado en z = position, con la punta hacia angle grados.
// Para cambiar las medidas desde otro programa, basta con reescribir los números de estas llamadas
// (por ejemplo "position = 60") y abrir o renderizar el archivo: no hace falta tocar los módulos.
// Para añadir un lóbulo, copie la línea de cam_lobe y cambie position y angle.
camshaft_main_shaft(length = 250, d = 25);
cam_lobe(base_r = 15, lift = 8, width = 12, rise_angle = 110, dwell_angle = 20, fall_angle = 110, motion = "cicloidal", angle = 0, position = 60, step = 1);

module camshaft_main_shaft(length = 250, d = 25) {
  // Main shaft of a camshaft (written by OpenSCAD GUI Mejorada): a plain cylinder along Z,
  // from z = 0 to z = length. The lobes (cam_lobe) are placed on it by their own position.
  cylinder(h = length, d = d);
}

module cam_lobe(base_r = 15, lift = 8, width = 12, rise_angle = 110, dwell_angle = 20, fall_angle = 110,
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
}
