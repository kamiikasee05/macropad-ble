"""Entry point del configurador de bandeja (systray) para el macropad BLE 4x4.

- Levanta uvicorn (FastAPI) en un hilo -> http://127.0.0.1:8791
- Icono en la bandeja (pystray + Pillow) con menu:
    Abrir configurador (default) | Reconectar dispositivo | Salir
- "Abrir configurador" lanza Chrome en modo app apuntando al server local.

Uso:  python tray.py
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time

import uvicorn
from PIL import Image, ImageDraw
import pystray

from server import app

HOST = "127.0.0.1"
PORT = 8791
URL = f"http://{HOST}:{PORT}/"
APP_DIR_NAME = "MacropadFx"

log = logging.getLogger("macropad.tray")

_state = {"server": None, "icon": None, "chrome": None}


# --------------------------------------------------------------------- icono
def make_icon_image(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (10, 14, 20, 255))
    d = ImageDraw.Draw(img)
    margin = 6
    gap = 3
    cell = (size - 2 * margin - 3 * gap) / 4.0
    cyan = (0, 219, 231, 255)
    purple = (235, 178, 255, 255)
    for r in range(4):
        for c in range(4):
            x0 = margin + c * (cell + gap)
            y0 = margin + r * (cell + gap)
            x1 = x0 + cell
            y1 = y0 + cell
            fill = purple if (r == 0 and c == 0) else cyan
            d.rounded_rectangle([x0, y0, x1, y1], radius=3, fill=fill)
    return img


# --------------------------------------------------------------------- paths
def _localappdata_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def _setup_logging() -> None:
    """Log a %LOCALAPPDATA%\\MacropadFx\\tray.log + stderr si existe.

    En modo windowed (PyInstaller) sys.stderr es None: sin un archivo, los
    errores del arranque serian invisibles.
    """
    handlers: list[logging.Handler] = []
    try:
        handlers.append(
            logging.FileHandler(os.path.join(_localappdata_dir(), "tray.log"), encoding="utf-8")
        )
    except OSError:
        pass
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def _resource_dirs() -> list[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    meipass = getattr(sys, "_MEIPASS", "") or ""
    return [meipass, os.path.join(exe_dir, "_internal"), exe_dir, here,
            os.path.join(here, "_internal")]


def find_icon_file() -> str | None:
    """Ruta al .ico del bundle/exe (para la bandeja y la ventana de Chrome)."""
    for d in _resource_dirs():
        if not d:
            continue
        for rel in (("icon.ico",), ("static", "favicon.ico")):
            p = os.path.join(d, *rel)
            if os.path.exists(p):
                return p
    return None


def load_icon_image(size: int = 64) -> Image.Image:
    path = find_icon_file()
    if path:
        try:
            img = Image.open(path)
            img.load()
            return img
        except Exception as exc:  # noqa: BLE001
            log.debug("no se pudo cargar el icono %s: %s", path, exc)
    return make_icon_image(size)


# ------------------------------------------------------------------ autostart
STARTUP_NAME = "MacropadFX.lnk"


def _startup_dir() -> str:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return ""
    return os.path.join(
        appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
    )


def startup_shortcut_path() -> str:
    d = _startup_dir()
    return os.path.join(d, STARTUP_NAME) if d else ""


def is_autostart_enabled() -> bool:
    path = startup_shortcut_path()
    return bool(path) and os.path.exists(path)


def _ps_quote(value: str) -> str:
    """Comilla simple de PowerShell (duplica las comillas internas)."""
    return "'" + str(value).replace("'", "''") + "'"


def _run_hidden(args: list[str]) -> bool:
    creationflags = 0
    startupinfo = None
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        res = subprocess.run(
            args,
            creationflags=creationflags,
            startupinfo=startupinfo,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return res.returncode == 0
    except Exception as exc:  # noqa: BLE001
        log.error("fallo ejecutando %s: %s", args[0], exc)
        return False


def _autostart_target() -> tuple[str, str, str]:
    """(TargetPath, Arguments, WorkingDirectory) para el atajo de Startup."""
    if getattr(sys, "frozen", False):
        # El .exe instalado (no python): un solo archivo de config.
        target = os.path.realpath(sys.executable)
        return target, "", os.path.dirname(target)
    # Modo desarrollo: pythonw tray.py (sin consola).
    exe = sys.executable or ""
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    target = pyw if os.path.exists(pyw) else exe
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tray.py")
    return target, f'"{script}"', os.path.dirname(script)


def create_startup_shortcut() -> bool:
    path = startup_shortcut_path()
    if not path:
        _notify("MacropadFX", "No se pudo ubicar la carpeta de Inicio.")
        return False
    target, arguments, workdir = _autostart_target()
    icon = find_icon_file() or target
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$lnk = $ws.CreateShortcut({_ps_quote(path)}); "
        f"$lnk.TargetPath = {_ps_quote(target)}; "
        f"$lnk.Arguments = {_ps_quote(arguments)}; "
        f"$lnk.WorkingDirectory = {_ps_quote(workdir)}; "
        f"$lnk.IconLocation = {_ps_quote(icon)}; "
        "$lnk.Description = 'MacropadFX Configurator'; "
        "$lnk.WindowStyle = 7; "
        "$lnk.Save()"
    )
    ok = _run_hidden(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps,
        ]
    )
    ok = ok and os.path.exists(path)
    log.info("autostart: %s", "activado" if ok else "no se pudo activar")
    return ok


def delete_startup_shortcut() -> bool:
    path = startup_shortcut_path()
    if not path:
        return False
    try:
        if os.path.exists(path):
            os.remove(path)
        return not os.path.exists(path)
    except OSError as exc:
        log.error("no se pudo borrar el atajo de Startup: %s", exc)
        return False


def toggle_autostart(icon=None, item=None):
    if is_autostart_enabled():
        ok = delete_startup_shortcut()
        _notify("MacropadFX", "Autoarranque desactivado." if ok else "No se pudo desactivar.")
    else:
        ok = create_startup_shortcut()
        _notify("MacropadFX", "Autoarranque activado." if ok else "No se pudo activar.")
    if icon is not None:
        try:
            icon.update_menu()
        except Exception:  # noqa: BLE001
            pass


def find_chrome() -> str | None:
    candidates = [
        os.path.join(
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            "Google", "Chrome", "Application", "chrome.exe",
        ),
        os.path.join(
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            "Google", "Chrome", "Application", "chrome.exe",
        ),
        os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Google", "Chrome", "Application", "chrome.exe",
        ),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


# --------------------------------------------------------------------- chrome
def open_configurator():
    chrome = find_chrome()
    if not chrome:
        log.error("No se encontro chrome.exe; abri manualmente %s", URL)
        _notify("No se encontro Chrome", f"Abrilo manualmente: {URL}")
        return
    profile = os.path.join(_localappdata_dir(), "chrome-profile")
    args = [
        chrome,
        f"--app={URL}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1100,820",
    ]
    try:
        # Nota: Chrome es GUI; no hace falta CREATE_NO_WINDOW. Igual se evita consola.
        _state["chrome"] = subprocess.Popen(
            args,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info("Chrome lanzado en modo app: %s", URL)
    except OSError as exc:
        log.error("No se pudo lanzar Chrome: %s", exc)
        _notify("No se pudo abrir Chrome", str(exc))


def _notify(title: str, message: str) -> None:
    icon = _state.get("icon")
    if icon is not None:
        try:
            icon.notify(message, title)
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------- server
def start_server() -> threading.Thread:
    # log_config=None es obligatorio (si no, el exe PyInstaller falla con
    # "Unable to configure formatter 'default'").
    config = uvicorn.Config(
        app,
        host=HOST,
        port=PORT,
        log_level="warning",
        log_config=None,
        access_log=False,
    )
    server = uvicorn.Server(config)
    _state["server"] = server

    def _run():
        try:
            server.run()
        except Exception as exc:  # noqa: BLE001
            log.exception("el servidor termino: %s", exc)

    t = threading.Thread(target=_run, name="uvicorn", daemon=True)
    t.start()
    return t


def wait_server(timeout: float = 15.0) -> bool:
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://{HOST}:{PORT}/api/status", timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.3)
    return False


# --------------------------------------------------------------------- acciones
def do_reconnect(icon=None, item=None):
    """Reconecta al dispositivo desde otro hilo (usa el loop de uvicorn)."""
    from device import DeviceError, get_device, run_async

    def _worker():
        dev = get_device()
        try:
            st = run_async(dev.reconnect())
            if st.get("connected"):
                _notify("MacropadFX", "Reconectado correctamente.")
            else:
                _notify("MacropadFX", "No se encontro el dispositivo.")
        except DeviceError as exc:
            _notify("MacropadFX", str(exc))
        except Exception as exc:  # noqa: BLE001
            _notify("MacropadFX", f"Error: {exc}")

    threading.Thread(target=_worker, name="reconnect", daemon=True).start()


def do_open(icon=None, item=None):
    open_configurator()


def do_quit(icon=None, item=None):
    log.info("saliendo...")
    server = _state.get("server")
    if server is not None:
        server.should_exit = True
    if icon is not None:
        icon.stop()


# --------------------------------------------------------------------- menu
def build_menu() -> pystray.Menu:
    return pystray.Menu(
        pystray.MenuItem("Abrir configurador", do_open, default=True),
        pystray.MenuItem("Reconectar dispositivo", do_reconnect),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Iniciar con Windows",
            toggle_autostart,
            checked=lambda item: is_autostart_enabled(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Salir", do_quit),
    )


# --------------------------------------------------------------------- main
def main() -> int:
    _setup_logging()
    log.info("iniciando servidor en %s (frozen=%s)", URL, getattr(sys, "frozen", False))
    start_server()
    wait_server()

    icon = pystray.Icon(
        "MacropadFx",
        icon=load_icon_image(),
        title="MacropadFX Configurator",
        menu=build_menu(),
    )
    _state["icon"] = icon

    # Abre la UI al arrancar (es un configurador).
    # MACROPAD_NO_BROWSER=1 permite arrancar sin abrir Chrome (tests / headless).
    if not os.environ.get("MACROPAD_NO_BROWSER"):
        threading.Timer(0.6, do_open).start()

    icon.run()
    log.info("tray detenido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
