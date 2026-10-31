$fn = 64;

color("DimGray") { // Rueda
  rotate([0, 90, 0]) {
    difference() {
      cylinder(h = 28, r = 50, center = true); // Llanta
      cylinder(h = 32, r = 7, center = true); // Alojamiento del buje
      translate([0, 0, 11]) { // Rebaje derecho
        difference() {
          cylinder(h = 4, r = 35);
          cylinder(h = 5, r = 15);
        }
      }
      translate([0, 0, -15]) { // Rebaje izquierdo
        difference() {
          cylinder(h = 4, r = 35);
          cylinder(h = 5, r = 15);
        }
      }
    }
  }
}
color("Goldenrod") { // Buje
  rotate([0, 90, 0]) {
    difference() {
      cylinder(h = 28, r = 7, center = true);
      cylinder(h = 32, r = 4, center = true);
    }
  }
}
color("LightSteelBlue") { // Soporte
  union() {
    translate([-17.36, -15, 57.64]) { // Placa superior
      difference() {
        cube([34.72, 44, 2.36]);
        translate([17.36, 30, -1]) {
          cylinder(h = 4.36, r = 7.25); // Agujero del pivote
        }
      }
    }
    translate([-17.36, 0, 0]) { // Pata izquierda
      rotate([90, 0, 90]) {
        linear_extrude(height = 2.36) {
          difference() {
            union() {
              circle(r = 10);
              polygon(points = [[-10, 0], [10, 0], [29, 57.64], [-15, 57.64]]);
            }
            circle(r = 4);
          }
        }
      }
    }
    translate([15, 0, 0]) { // Pata derecha
      rotate([90, 0, 90]) {
        linear_extrude(height = 2.36) {
          difference() {
            union() {
              circle(r = 10);
              polygon(points = [[-10, 0], [10, 0], [29, 57.64], [-15, 57.64]]);
            }
            circle(r = 4);
          }
        }
      }
    }
  }
}
color("Silver") { // Perno del eje
  rotate([0, 90, 0]) {
    union() {
      translate([0, 0, -19.36]) {
        cylinder(h = 2, r1 = 6, r2 = 8); // Cabeza
      }
      translate([0, 0, -17.36]) {
        cylinder(h = 37, r = 3.75); // Vástago
      }
      translate([0, 0, 19.64]) {
        cylinder(h = 8, r = 3); // Rosca M6
      }
    }
  }
}
color("WhiteSmoke") { // Tuerca M6
  rotate([0, 90, 0]) {
    translate([0, 0, 18.5]) {
      difference() {
        cylinder(h = 5, r = 5.77, $fn = 6);
        cylinder(h = 7, r = 3, center = true);
      }
    }
  }
}
color("Silver") { // Poste giratorio
  translate([0, 15, 60]) {
    union() {
      translate([0, 0, -9.36]) {
        cylinder(h = 4, r = 5); // Remache
      }
      translate([0, 0, -5.36]) {
        cylinder(h = 3, r = 9); // Brida
      }
      translate([0, 0, -2.36]) {
        cylinder(h = 25, r = 7); // Pivote
      }
      translate([0, 0, 22.64]) {
        cylinder(h = 9, r = 3.75); // Cuello
      }
      translate([0, 0, 31.64]) {
        cylinder(h = 4, r1 = 3.75, r2 = 2.25); // Espiga
      }
    }
  }
}
