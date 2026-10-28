// OpenSCAD GUI Mejorada — Figura 5.31. Rueda con eje giratorio
// Ensamblaje mecanico normalizado segun plano de ingenieria
$fn = 64;

// ====================================================================
// PZA 1: RUEDA (1 pza, Matl: Hule Duro)
// ====================================================================
color("DimGray") { // Pza 1 - Rueda
  rotate([0, 90, 0]) { // Eje horizontal X
    difference() { // Torneado de rueda
      cylinder(h = 28, r = 50, center = true); // Llanta exterior D100
      cylinder(h = 32, r = 7, center = true); // Alojamiento buje D14
      translate([0, 0, 11]) { // Rebaje cara derecha
        difference() {
          cylinder(h = 4, r = 35); // Vaciado D70
          cylinder(h = 5, r = 15); // Maza central D30
        }
      }
      translate([0, 0, -15]) { // Rebaje cara izquierda
        difference() {
          cylinder(h = 4, r = 35); // Vaciado D70
          cylinder(h = 5, r = 15); // Maza central D30
        }
      }
    }
  }
}

// ====================================================================
// PZA 5: BUJE (1 pza, Matl: Laton)
// ====================================================================
color("Goldenrod") { // Pza 5 - Buje
  rotate([0, 90, 0]) { // Eje horizontal X
    difference() { // Buje cilindrico de laton
      cylinder(h = 28, r = 7, center = true); // Diametro exterior D14
      cylinder(h = 32, r = 4, center = true); // Diametro interior D8
    }
  }
}

// ====================================================================
// PZA 4: SOPORTE (1 pza QD, Matl: Lamina 2.36 mm)
// ====================================================================
color("LightSteelBlue") { // Pza 4 - Soporte
  union() { // Horquilla estampada
    translate([-17.36, -15, 57.64]) { // Placa superior
      difference() { // Placa con agujero de pivote
        cube([34.72, 44, 2.36]); // Placa horizontal 34.72x44
        translate([17.36, 30, -1]) { // Posicion agujero pivote
          cylinder(h = 4.36, r = 7.25); // Agujero para pivote D14.5
        }
      }
    }
    translate([-17.36, 0, 0]) { // Pata izquierda
      rotate([90, 0, 90]) {
        linear_extrude(height = 2.36) {
          difference() {
            union() {
              circle(r = 10); // Extremo redondeado R10
              polygon(points = [[-10, 0], [10, 0], [29, 57.64], [-15, 57.64]]); // Cuerpo ahusado
            }
            circle(r = 4); // Agujero pasante de eje D8
          }
        }
      }
    }
    translate([15, 0, 0]) { // Pata derecha
      rotate([90, 0, 90]) {
        linear_extrude(height = 2.36) {
          difference() {
            union() {
              circle(r = 10); // Extremo redondeado R10
              polygon(points = [[-10, 0], [10, 0], [29, 57.64], [-15, 57.64]]); // Cuerpo ahusado
            }
            circle(r = 4); // Agujero pasante de eje D8
          }
        }
      }
    }
  }
}

// ====================================================================
// PZA 3: PERNO DE EJE (1 pza, Matl: Acero Maquinado)
// ====================================================================
color("Silver") { // Pza 3 - Perno de eje
  rotate([0, 90, 0]) { // Eje horizontal X
    union() { // Perno maquinado escalonado
      translate([0, 0, -19.36]) { // Cabeza
        cylinder(h = 2, r1 = 6, r2 = 8); // Cabeza con chaflan D16
      }
      translate([0, 0, -17.36]) { // Vastago
        cylinder(h = 37, r = 3.75); // Vastago liso D7.5
      }
      translate([0, 0, 19.64]) { // Extremo roscado
        cylinder(h = 8, r = 3); // Rosca M6
      }
    }
  }
}

// ====================================================================
// PZA 6: TUERCA HEX M6-1 (1 pza, Matl: Acero)
// ====================================================================
color("WhiteSmoke") { // Pza 6 - Tuerca Hex M6
  rotate([0, 90, 0]) { // Eje horizontal X
    translate([0, 0, 18.5]) { // Roscar sobre perno
      difference() { // Tuerca hexagonal
        cylinder(h = 5, r = 5.77, $fn = 6); // Hexagono e=10 mm
        cylinder(h = 7, r = 3, center = true); // Rosca interior M6
      }
    }
  }
}

// ====================================================================
// PZA 2: POSTE GIRATORIO (1 pza, Matl: Acero Maquinado)
// ====================================================================
color("Silver") { // Pza 2 - Poste giratorio
  translate([0, 15, 60]) { // Eje de giro vertical Z
    union() { // Eje torneado escalonado
      translate([0, 0, -9.36]) { // Remache inferior
        cylinder(h = 4, r = 5); // Espiga a martillar D10
      }
      translate([0, 0, -5.36]) { // Brida
        cylinder(h = 3, r = 9); // Brida apoyo D18
      }
      translate([0, 0, -2.36]) { // Pivote
        cylinder(h = 25, r = 7); // Vastago D14
      }
      translate([0, 0, 22.64]) { // Cuello
        cylinder(h = 9, r = 3.75); // Cuello D7.5
      }
      translate([0, 0, 31.64]) { // Espiga
        cylinder(h = 4, r1 = 3.75, r2 = 2.25); // Espiga chaflanada
      }
    }
  }
}
