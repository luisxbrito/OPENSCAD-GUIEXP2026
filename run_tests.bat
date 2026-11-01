@echo off
rem Pruebas de OpenSCAD GUI Mejorada en Windows.
rem Las de ventana (test_ventana_qt) necesitan PySide6 y pyqtgraph; las de OpenSCAD, OpenSCAD instalado.
rem Si falta algo, esas pruebas se omiten y lo dicen.
cd /d "%~dp0"
set FALLOS=0
for %%t in (test_core test_geometry test_i18n test_tema test_openscad test_ventana_qt) do (
    echo.
    echo === %%t ===
    python tests\%%t.py || set FALLOS=1
)
for %%s in (tests\simulacion\sim_ventana_visor_imagen.py tests\simulacion\sim_ventana_visor_opengl.py) do (
    echo.
    echo === %%s ===
    python %%s || set FALLOS=1
)
echo.
if %FALLOS%==1 (echo HAY PRUEBAS QUE FALLAN) else (echo TODAS LAS PRUEBAS PASAN)
pause
