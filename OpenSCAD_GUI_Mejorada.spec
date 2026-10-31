# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file para generar el ejecutable portable de OpenSCAD GUI Mejorada."""

import os
import sys

block_cipher = None

APP_ROOT = os.path.abspath(SPECPATH)

datas = [
    (os.path.join(APP_ROOT, 'examples'), 'examples'),
]
if os.path.isdir(os.path.join(APP_ROOT, 'resources')):
    datas.append((os.path.join(APP_ROOT, 'resources'), 'resources'))

icon_path = os.path.join(APP_ROOT, 'resources', 'icon.ico')
if not os.path.isfile(icon_path):
    icon_path = None

from PyInstaller.utils.hooks import collect_submodules

sys.path.insert(0, APP_ROOT)  # para que collect_submodules encuentre el paquete scadgui

# Todo el paquete scadgui (incluidas las traducciones de scadgui/locales); así la lista no se
# queda desfasada cuando se añade un módulo.
hidden_imports = collect_submodules('scadgui') + [
    'PySide6.QtSvg',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'pyqtgraph',
    'pyqtgraph.opengl',
    'OpenGL',
    'OpenGL.GL',
    'OpenGL.platform.win32',
    'OpenGL.arrays.numpymodule',
    'OpenGL.arrays.ctypesarrays',
    'OpenGL.arrays.ctypesparameters',
    'OpenGL.arrays.ctypespointers',
    'numpy',
]

excludes = [
    'tkinter',
    'matplotlib',
    'scipy',
    'django',
    'torch',
    'pandas',
    'IPython',
    'notebook',
    'test',
    'tests',
]

a = Analysis(
    [os.path.join(APP_ROOT, 'main.py')],
    pathex=[APP_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 1. Ejecutable portátil en un solo archivo (Single-File Standalone Portable EXE)
exe_standalone = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='OpenSCAD_GUI_Mejorada',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
