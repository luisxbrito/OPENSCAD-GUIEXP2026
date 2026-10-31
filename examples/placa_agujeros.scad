// Generado con OpenSCAD GUI Mejorada
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
