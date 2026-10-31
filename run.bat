@echo off
rem Abre OpenSCAD GUI Mejorada. La primera vez instala las bibliotecas necesarias.
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo No se encontro Python. Instalalo desde https://www.python.org marcando "Add Python to PATH".
  pause
  exit /b 1
)
python -c "import PySide6, pyqtgraph, OpenGL, numpy" >nul 2>nul
if errorlevel 1 (
  echo Instalando PySide6, pyqtgraph, PyOpenGL y numpy ^(solo la primera vez^)...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo No se pudieron instalar las bibliotecas.
    pause
    exit /b 1
  )
)
python main.py %*
if errorlevel 1 pause
