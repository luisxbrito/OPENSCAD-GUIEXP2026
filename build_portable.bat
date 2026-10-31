@echo off
REM Compilar OpenSCAD GUI Mejorada en ejecutable portable
echo ===================================================
echo  Iniciando compilacion portable...
echo ===================================================
python "%~dp0build_portable.py" %*
pause
