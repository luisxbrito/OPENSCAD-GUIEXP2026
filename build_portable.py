"""Script automatizado para compilar OpenSCAD GUI Mejorada como ejecutable portable.

Uso:
    python build_portable.py
    python build_portable.py --onedir
    python build_portable.py --zip
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile


def build(onedir: bool = False, create_zip: bool = True) -> int:
    root = os.path.abspath(os.path.dirname(__file__))
    os.chdir(root)

    print("==================================================================")
    print(" Compilando OpenSCAD GUI Mejorada como Ejecutable Portable")
    print("==================================================================")
    print(f"Directorio base: {root}")
    print(f"Python: {sys.executable} ({sys.version.split()[0]})")

    # Asegurar que PyInstaller esté instalado
    try:
        import PyInstaller
        print(f"PyInstaller detectado: versión {PyInstaller.__version__}")
    except ImportError:
        print("ERROR: PyInstaller no está instalado. Ejecute: pip install pyinstaller")
        return 1

    # Asegurar que resources/icon.ico existe
    icon_src = os.path.join(root, "..", "resources", "icons", "openscad.ico")
    icon_dst = os.path.join(root, "resources", "icon.ico")
    if not os.path.isfile(icon_dst) and os.path.isfile(icon_src):
        os.makedirs(os.path.join(root, "resources"), exist_ok=True)
        shutil.copy(icon_src, icon_dst)
        print(f"Icono copiado a: {icon_dst}")

    dist_dir = os.path.join(root, "dist")
    build_dir = os.path.join(root, "build")

    spec_file = os.path.join(root, "OpenSCAD_GUI_Mejorada.spec")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        spec_file,
    ]

    print(f"Ejecutando: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("ERROR durante la compilación con PyInstaller.")
        return result.returncode

    exe_path = os.path.join(dist_dir, "OpenSCAD_GUI_Mejorada.exe")
    if not os.path.isfile(exe_path):
        print(f"ERROR: No se encontró el ejecutable en {exe_path}")
        return 1

    exe_size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print("------------------------------------------------------------------")
    print(f"¡Éxito! Ejecutable generado:")
    print(f"  Ruta:   {exe_path}")
    print(f"  Tamaño: {exe_size_mb:.2f} MB")

    if create_zip:
        zip_path = os.path.join(dist_dir, "OpenSCAD_GUI_Mejorada_Portable.zip")
        print(f"Empaquetando en ZIP portable: {zip_path}")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(exe_path, "OpenSCAD_GUI_Mejorada.exe")
            # Incluir carpeta de ejemplos para acceso rápido si se descomprime
            examples_dir = os.path.join(root, "examples")
            if os.path.isdir(examples_dir):
                for f in os.listdir(examples_dir):
                    if f.endswith(".scad"):
                        zf.write(os.path.join(examples_dir, f), f"ejemplos/{f}")
        zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        print(f"  Archivo ZIP: {zip_path} ({zip_size_mb:.2f} MB)")

    print("==================================================================")
    print(" Distribución portable lista para usar en cualquier PC con Windows")
    print("==================================================================")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compilar OpenSCAD GUI portable")
    parser.add_argument("--onedir", action="store_true", help="Generar carpeta portable en vez de un solo .exe")
    parser.add_argument("--no-zip", action="store_true", help="No crear archivo .zip")
    args = parser.parse_args()

    sys.exit(build(onedir=args.onedir, create_zip=not args.no_zip))
