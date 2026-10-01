"""FastAPI: API local (loopback) + sirve la UI del configurador del macropad.

Endpoints (sin auth, solo 127.0.0.1):
  GET    /                          -> static/index.html
  GET    /api/status                -> {found, connected, name, address}
  POST   /api/connect               -> conecta (scan + GATT)
  POST   /api/disconnect
  GET    /api/keymap                -> {raw}
  POST   /api/keymap   {raw}        -> SETL <raw>
  POST   /api/reset                 -> RESET
  GET    /api/profiles              -> {profiles:{name:{raw,saved_at}}}
  POST   /api/profiles {name,raw}   -> guarda/sobrescribe
  DELETE /api/profiles/{name}
  POST   /api/profiles/{name}/apply -> conecta si hace falta + SETL
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import profiles as profiles_mod
from device import DeviceError, get_device

log = logging.getLogger("macropad.server")


# ------------------------------------------------------------------ static dir
def static_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    meipass = getattr(sys, "_MEIPASS", "")

    # Orden de busqueda (dev -> PyInstaller):
    #   1) <_MEIPASS>/static            (one-file / one-dir)
    #   2) <exe_dir>/_internal/static   (one-dir, PyInstaller 6.x)
    #   3) static junto al codigo       (desarrollo: python tray.py)
    candidates = [
        os.path.join(meipass, "static") if meipass else "",
        os.path.join(exe_dir, "_internal", "static"),
        os.path.join(here, "_internal", "static"),
        os.path.join(here, "static"),
        os.path.join(exe_dir, "static"),
        here,
    ]
    for c in candidates:
        if c and os.path.isdir(c) and os.path.exists(os.path.join(c, "index.html")):
            return c
    return os.path.join(here, "static")


# ------------------------------------------------------------------ app lifespan
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    dev = get_device()
    dev.set_loop(asyncio.get_running_loop())
    try:
        await dev.start_background()
    except Exception as exc:  # noqa: BLE001
        log.warning("no se pudo arrancar el scanner de fondo: %s", exc)
    try:
        yield
    finally:
        try:
            await dev.stop_background()
            await dev.disconnect()
        except Exception:  # noqa: BLE001
            pass


app = FastAPI(title="MacropadFX Configurator", lifespan=lifespan)


# ------------------------------------------------------------------ errores JSON
@app.exception_handler(DeviceError)
async def _device_error_handler(request: Request, exc: DeviceError):
    return JSONResponse(status_code=409, content={"error": str(exc)})


@app.exception_handler(ValueError)
async def _value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400, content={"error": f"Cuerpo invalido: {exc.errors()}"}
    )


@app.exception_handler(Exception)
async def _generic_error_handler(request: Request, exc: Exception):
    log.exception("error no controlado en %s", request.url.path)
    return JSONResponse(
        status_code=500, content={"error": f"Error interno: {exc}"}
    )


# ------------------------------------------------------------------ modelos
class KeymapBody(BaseModel):
    raw: str


class ProfileBody(BaseModel):
    name: str
    raw: str


def _device():
    return get_device()


# ------------------------------------------------------------------ rutas UI
@app.get("/")
async def index():
    path = os.path.join(static_dir(), "index.html")
    if not os.path.exists(path):
        return JSONResponse(status_code=500, content={"error": "Falta static/index.html"})
    return FileResponse(path, media_type="text/html")


@app.get("/favicon.ico")
async def favicon():
    path = os.path.join(static_dir(), "favicon.ico")
    if os.path.exists(path):
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"error": "sin favicon"})


# ------------------------------------------------------------------ device
@app.get("/api/status")
async def api_status():
    return _device().status()


@app.post("/api/connect")
async def api_connect():
    dev = _device()
    try:
        return await dev.connect()
    except DeviceError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DeviceError(f"No se pudo conectar: {exc}") from exc


@app.post("/api/disconnect")
async def api_disconnect():
    return await _device().disconnect()


@app.post("/api/reconnect")
async def api_reconnect():
    return await _device().reconnect()


@app.get("/api/keymap")
async def api_keymap_get():
    dev = _device()
    if not dev.connected:
        raise DeviceError("No hay dispositivo conectado. Usa Conectar primero.")
    raw = await dev.command("GET")
    return {"raw": raw}


@app.post("/api/keymap")
async def api_keymap_set(body: KeymapBody):
    dev = _device()
    raw = (body.raw or "").strip()
    if not raw:
        raise ValueError("El keymap esta vacio.")
    if not dev.connected:
        raise DeviceError("No hay dispositivo conectado. Usa Conectar primero.")
    resp = await dev.command("SETL " + raw)
    if resp.strip() == "ERR":
        return JSONResponse(
            status_code=400,
            content={"error": "El dispositivo rechazo el keymap (ERR). Revisa el formato."},
        )
    return {"raw": resp}


@app.post("/api/reset")
async def api_reset():
    dev = _device()
    if not dev.connected:
        raise DeviceError("No hay dispositivo conectado. Usa Conectar primero.")
    raw = await dev.command("RESET")
    return {"raw": raw}


@app.get("/api/ping")
async def api_ping():
    dev = _device()
    if not dev.connected:
        raise DeviceError("No hay dispositivo conectado. Usa Conectar primero.")
    resp = await dev.command("PING")
    return {"raw": resp}


# ------------------------------------------------------------------ profiles
@app.get("/api/profiles")
async def api_profiles_list():
    return {"profiles": profiles_mod.list_profiles(), "path": profiles_mod.profiles_path()}


@app.post("/api/profiles")
async def api_profiles_save(body: ProfileBody):
    entry = profiles_mod.save_profile(body.name, body.raw)
    return {"name": body.name.strip(), "profile": entry}


@app.delete("/api/profiles/{name}")
async def api_profiles_delete(name: str):
    if not profiles_mod.delete_profile(name):
        return JSONResponse(status_code=404, content={"error": f"No existe el perfil '{name}'."})
    return {"deleted": name}


@app.post("/api/profiles/{name}/apply")
async def api_profiles_apply(name: str):
    prof = profiles_mod.get_profile(name)
    if prof is None:
        return JSONResponse(status_code=404, content={"error": f"No existe el perfil '{name}'."})
    dev = _device()
    if not dev.connected:
        await dev.connect()  # conecta si hace falta
    raw = prof["raw"]
    resp = await dev.command("SETL " + raw)
    if resp.strip() == "ERR":
        return JSONResponse(
            status_code=400,
            content={"error": "El dispositivo rechazo el keymap del perfil (ERR)."},
        )
    return {"name": name, "raw": resp}
