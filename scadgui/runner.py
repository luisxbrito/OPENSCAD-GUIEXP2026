"""Ejecuta el programa openscad por línea de comandos (vista previa en PNG y exportación)."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, QProcess, QTimer, Signal


def _candidates() -> list[str]:
    paths: list[str] = []
    # Búsqueda en directorio local (para versiones portables)
    local_dirs = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        local_dirs += [exe_dir, os.path.join(exe_dir, "openscad"), os.path.join(exe_dir, "bin")]
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            local_dirs += [meipass, os.path.join(meipass, "openscad")]
    else:
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_dirs += [app_dir, os.path.join(app_dir, "openscad")]

    for ldir in local_dirs:
        for exe in ("openscad.com", "openscad.exe"):
            p = os.path.join(ldir, exe)
            if os.path.isfile(p):
                paths.append(p)

    if sys.platform.startswith("win"):
        roots = [os.environ.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "LOCALAPPDATA")]
        for root in filter(None, roots):
            for folder in ("OpenSCAD", "OpenSCAD (Nightly)", os.path.join("Programs", "OpenSCAD")):
                for exe in ("openscad.com", "openscad.exe"):
                    paths.append(os.path.join(root, folder, exe))
    elif sys.platform == "darwin":
        paths += ["/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
                  os.path.expanduser("~/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD")]
    for name in ("openscad", "openscad-nightly"):
        found = shutil.which(name)
        if found:
            paths.append(found)
    return paths


def console_exe(path: str) -> str:
    """En Windows, openscad.com escribe en la consola; openscad.exe no devuelve mensajes."""
    if path.lower().endswith(".exe"):
        com = path[:-4] + ".com"
        if os.path.isfile(com):
            return com
    return path


def find_openscad(configured: str = "") -> str:
    if configured and os.path.isfile(configured):
        return console_exe(configured)
    for p in _candidates():
        if os.path.isfile(p):
            return console_exe(p)
    return ""


@dataclass
class Camera:
    rx: float = 55.0
    ry: float = 0.0
    rz: float = 25.0

    def arg(self) -> str:
        return f"--camera=0,0,0,{self.rx:.1f},{self.ry:.1f},{self.rz:.1f},0"


VIEWS = {
    "Isométrica": Camera(55, 0, 25),
    "Frontal": Camera(90, 0, 0),
    "Superior": Camera(0, 0, 0),
    "Derecha": Camera(90, 0, 90),
}


def wrap_2d(code: str) -> str:
    """Envuelve un modelo 2D en una extrusión muy fina para poder verlo en 3D."""
    head, body = [], []
    for line in code.splitlines():
        (head if line.lstrip().startswith(("include ", "include<", "use ", "use<")) else body).append(line)
    return "\n".join(head + ["linear_extrude(height = 0.02) {"] + ["  " + b for b in body] + ["}"]) + "\n"


class OpenScadRunner(QObject):
    """Lanza openscad sin bloquear la interfaz. Si llega un pedido nuevo, cancela el anterior."""

    imageReady = Signal(str, float)        # ruta del png, segundos
    failed = Signal(str)                   # mensaje
    log = Signal(str)                      # cada línea que escribe openscad
    started = Signal(str)                  # descripción de la tarea
    exportDone = Signal(str, bool)         # ruta, ok
    meshReady = Signal(str, float)         # ruta del STL, segundos
    meshEmpty = Signal()                   # el modelo no tiene geometría

    def __init__(self, parent=None):
        super().__init__(parent)
        self.exe = ""
        self.backend = ""          # "", "manifold" o "cgal"
        self.extra_args: list[str] = []
        self._tmp = tempfile.mkdtemp(prefix="scadgui_")
        self._proc: Optional[QProcess] = None
        self._job = None
        self._counter = 0
        self._backend_ok = True
        self._pending = None  # vista pedida mientras se exportaba

    # ----- utilidades
    def _write_source(self, code: str, base_dir: str) -> str:
        """Escribe el código a un .scad temporal.

        Si el documento ya está guardado, el temporal se crea en su misma carpeta
        para que import("pieza.stl") y include <...> encuentren los archivos relativos.
        """
        self._counter += 1
        folder = base_dir if base_dir and os.access(base_dir, os.W_OK) else self._tmp
        path = os.path.join(folder, f".scadgui_preview_{os.getpid()}_{self._counter % 2}.scad")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(code)
        return path

    def _common(self) -> list[str]:
        args = list(self.extra_args)
        if self.backend and self._backend_ok:
            args.append(f"--backend={self.backend}")
        return args

    def busy(self) -> bool:
        return self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning

    def cancel(self) -> None:
        if self.busy():
            proc = self._proc
            self._proc = None
            proc.kill()
            proc.waitForFinished(2000)
            self._remove_source(self._job[2])

    def _remove_source(self, src: str) -> None:
        if os.path.dirname(src) != self._tmp:
            try:
                os.remove(src)
            except OSError:
                pass

    # ----- tareas
    def render_image(self, code: str, base_dir: str, size: tuple[int, int], camera: Camera,
                     full_render: bool = False) -> None:
        src = self._write_source(code, base_dir)
        png = os.path.join(self._tmp, f"view_{self._counter}.png")
        args = ["-o", png, f"--imgsize={max(64, size[0])},{max(64, size[1])}", camera.arg(),
                "--viewall", "--autocenter", "--projection=p", "--colorscheme=Tomorrow Night",
                "--view=axes"]
        args.append("--render" if full_render else "--preview")
        args += self._common() + [src]
        self._start(("image", png, src, code, base_dir, size, camera, full_render), args,
                    "Render final…" if full_render else "Vista previa…")

    def export_mesh(self, code: str, base_dir: str, wrapped_2d: bool = False) -> None:
        """Calcula la malla final (para el visor OpenGL) exportando a STL."""
        src = self._write_source(code, base_dir)
        # OFF: formato simple que, en las versiones recientes de OpenSCAD, incluye el color de cada cara
        stl = os.path.join(self._tmp, f"mesh_{self._counter}.off")
        if os.path.exists(stl):
            os.remove(stl)
        args = ["-o", stl, "--export-format=off"] + self._common() + [src]
        self._start(("mesh", stl, src, code, base_dir, wrapped_2d), args,
                    "Calculando 2D…" if wrapped_2d else "Calculando…")

    def export(self, code: str, base_dir: str, out_path: str) -> None:
        src = self._write_source(code, base_dir)
        args = ["-o", out_path] + self._common() + [src]
        self._start(("export", out_path, src), args, f"Exportando {os.path.basename(out_path)}…")

    def _start(self, job, args, description) -> None:
        if not self.exe:
            self.failed.emit("No se encontró OpenSCAD. Usa Archivo › Configurar OpenSCAD…")
            return
        if self.busy() and self._job and self._job[0] == "export" and job[0] != "export":
            self._pending = (job, args, description)  # no interrumpir una exportación
            return
        self.cancel()
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda p=proc: self._read(p))
        proc.finished.connect(lambda code, status, p=proc, j=job: self._finished(p, j, code))
        proc.errorOccurred.connect(lambda err, p=proc: self._error(p, err))
        self._proc = proc
        self._job = job
        self._buffer = ""
        self._all_output = ""
        self._args = args
        self._description = description
        self._t0 = time.monotonic()
        self.started.emit(description)
        proc.start(self.exe, args)

    def _read(self, proc: QProcess) -> None:
        text = proc.readAllStandardOutput().data().decode("utf-8", errors="replace")
        if proc is not self._proc:
            return
        self._buffer += text
        self._all_output += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line.strip():
                self.log.emit(line)

    def _error(self, proc: QProcess, err) -> None:
        if proc is self._proc and err == QProcess.ProcessError.FailedToStart:
            self._proc = None
            self.failed.emit(f"No se pudo ejecutar OpenSCAD: {self.exe}")

    def _finished(self, proc: QProcess, job, exit_code: int) -> None:
        if proc is not self._proc:
            return  # tarea cancelada
        self._read(proc)
        if self._buffer.strip():
            self.log.emit(self._buffer.strip())
        output = self._all_output.lower()
        self._proc = None
        elapsed = time.monotonic() - self._t0
        kind = job[0]
        src = job[2]
        if exit_code != 0 and self.backend and self._backend_ok and "backend" in output \
                and ("unrecogni" in output or "unknown" in output or "invalid" in output):
            # versión de OpenSCAD sin --backend: se repite sin esa opción
            self._backend_ok = False
            self.log.emit("Esta versión de OpenSCAD no admite --backend; se usa el motor por defecto.")
            args = [a for a in self._args if not a.startswith("--backend=")]
            self._start(job, args, self._description)
            return
        self._remove_source(src)
        if self._pending is not None and kind == "export":
            pending, self._pending = self._pending, None
            QTimer.singleShot(0, lambda: self._start(*pending))
        if kind == "image":
            png = job[1]
            if exit_code == 0 and os.path.isfile(png):
                self.imageReady.emit(png, elapsed)
            else:
                self.failed.emit("OpenSCAD no pudo generar la vista. Revisa la consola.")
        elif kind == "mesh":
            stl, code, base_dir, wrapped = job[1], job[3], job[4], job[5]
            if exit_code == 0 and os.path.isfile(stl) and os.path.getsize(stl) > 16:
                self.meshReady.emit(stl, elapsed)
            elif "not a 3d object" in output and not wrapped:
                # modelo 2D: se muestra como una lámina fina
                self.export_mesh(wrap_2d(code), base_dir, wrapped_2d=True)
            elif "empty" in output or (exit_code == 0 and not os.path.isfile(stl)) or \
                    (exit_code == 0 and os.path.getsize(stl) <= 16):
                self.meshEmpty.emit()
            else:
                self.failed.emit("OpenSCAD no pudo calcular el modelo. Revisa la consola.")
        else:
            out = job[1]
            ok = exit_code == 0 and os.path.isfile(out)
            self.exportDone.emit(out, ok)

    def check_backend_support(self, version_text: str) -> None:
        """Las versiones estables antiguas (2021.01) no conocen --backend ni --enable."""
        self._backend_ok = not version_text.startswith("2021")

    def version(self) -> str:
        if not self.exe:
            return ""
        proc = QProcess()
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.start(self.exe, ["--version"])
        if not proc.waitForFinished(8000):
            proc.kill()
            return ""
        text = proc.readAllStandardOutput().data().decode("utf-8", errors="replace").strip()
        return text.replace("OpenSCAD version", "").strip()
