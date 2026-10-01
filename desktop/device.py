"""Wrapper de bleak para el macropad BLE 4x4 (MacropadFx).

Protocolo verificado en vivo (firmware/src/main.cpp):
  - Nombre BLE: "MacropadFx" (MAC fija)
  - Servicio FFE0 / Caracteristica FFE1 (READ | WRITE)
  - Se escribe un string UTF-8 y se lee el nuevo valor de la misma caracteristica.
  - Comandos: PING -> PONG | GET -> keymap | RESET -> keymap | SETL <keymap> -> keymap o "ERR"

Este modulo mantiene viva la conexion entre requests y expone una API sincronica
para que el resto del codigo (FastAPI / pystray) no tenga que lidiar con asyncio.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

log = logging.getLogger("macropad.device")

DEVICE_NAME = "MacropadFx"
FFE0_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
FFE1_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

# MAC fija del macropad (el firmware usa setRandomAddress(false)).
# Se puede sobreescribir con la env var MACROPAD_ADDRESS.
KNOWN_ADDRESS = os.environ.get("MACROPAD_ADDRESS", "34:B7:DA:F7:AD:AE")

SCAN_TIMEOUT = 6.0
CONNECT_TIMEOUT = 15.0
IDLE_SCAN_INTERVAL = 12.0
IDLE_SCAN_TIMEOUT = 4.0
READ_RETRIES = 6


class DeviceError(Exception):
    """Error de negocio del dispositivo (se traduce a JSON, nunca a traceback)."""


def _address_to_int(address: str) -> int:
    return int(address.replace(":", "").replace("-", ""), 16)


async def _reachable_by_address() -> bool:
    """True si el macropad esta emparejado/conectado en Windows AUNQUE no anuncie.

    Cuando Windows lo tiene tomado como teclado HID, el dispositivo deja de
    anunciar (un scan no lo ve) pero sigue siendo alcanzable por direccion.
    """
    if not KNOWN_ADDRESS:
        return False
    try:
        from winrt.windows.devices.bluetooth import BluetoothLEDevice

        dev = await BluetoothLEDevice.from_bluetooth_address_async(
            _address_to_int(KNOWN_ADDRESS)
        )
        if dev is None:
            return False
        return int(dev.connection_status) != 0
    except Exception as exc:  # nunca romper el scan de fondo por esto
        log.debug("chequeo por direccion fallo: %s", exc)
        return False


class MacropadDevice:
    def __init__(self) -> None:
        self._client: Optional[BleakClient] = None
        self._lock = asyncio.Lock()
        self._address: Optional[str] = None
        self._name: Optional[str] = None
        self._found: bool = False
        self._last_error: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._scan_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------ estado
    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    def status(self) -> dict:
        return {
            "found": self._found or self.connected,
            "connected": self.connected,
            "name": self._name,
            "address": self._address,
            "error": self._last_error,
        }

    # --------------------------------------------------------------- ciclo de vida
    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def start_background(self) -> None:
        """Arranca el scanner liviano en segundo plano (no bloquea /api/status)."""
        if self._scan_task is None or self._scan_task.done():
            self._scan_task = asyncio.create_task(self._scanner_loop())

    async def stop_background(self) -> None:
        task = self._scan_task
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            self._scan_task = None

    async def _scanner_loop(self) -> None:
        while True:
            try:
                if not self.connected:
                    # Serializa con connect/command: en Windows WinRT no conviene
                    # tener dos operaciones de scanner a la vez.
                    async with self._lock:
                        if not self.connected:
                            await self._scan_once(IDLE_SCAN_TIMEOUT)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # nunca matar el loop por un scan fallido
                log.debug("scan de fondo fallo: %s", exc)
            await asyncio.sleep(IDLE_SCAN_INTERVAL)

    async def _scan_once(self, timeout: float) -> Optional[str]:
        """Escanea y cachea si el macropad esta presente. Devuelve la address o None."""
        def _match(device, adv_data) -> bool:
            return device.name == DEVICE_NAME or adv_data.local_name == DEVICE_NAME

        device = None
        try:
            device = await BleakScanner.find_device_by_filter(_match, timeout=timeout)
        except BleakError as exc:
            self._last_error = str(exc)

        if device is None:
            # Puede estar conectado a Windows (deja de anunciar). En ese caso
            # igual es alcanzable por direccion: lo damos por "encontrado".
            if await _reachable_by_address():
                self._found = True
                self._address = self._address or KNOWN_ADDRESS
                self._name = DEVICE_NAME
                return self._address
            self._found = False
            return None

        self._found = True
        self._address = device.address
        self._name = device.name or DEVICE_NAME
        return device.address

    # -------------------------------------------------------------------- BLE ops
    async def connect(self) -> dict:
        async with self._lock:
            if self.connected:
                return self.status()
            await self._connect_locked()
            return self.status()

    async def _connect_locked(self) -> None:
        self._last_error = None

        # 1) Escaneo corto: cubre el caso "el macropad esta anunciando"
        #    (recien despertado y Windows todavia no lo tomo).
        device = None
        try:
            device = await BleakScanner.find_device_by_filter(
                lambda d, a: d.name == DEVICE_NAME or a.local_name == DEVICE_NAME,
                timeout=SCAN_TIMEOUT,
            )
        except BleakError as exc:
            log.debug("scan fallo: %s", exc)

        # 2) Candidatos por direccion: lo escaneado, lo cacheado y la MAC conocida.
        addresses: list[str] = []
        for addr in (getattr(device, "address", None), self._address, KNOWN_ADDRESS):
            if addr and addr not in addresses:
                addresses.append(addr)

        last_exc: Optional[Exception] = None
        for addr in addresses:
            try:
                # Clave: se conecta POR DIRECCION y sin escanear (ver _connect_to).
                # Asi funciona aunque Windows ya tenga el macropad tomado como
                # teclado (el dispositivo deja de anunciar y un scan no lo ve).
                await self._connect_to(addr)
                self._found = True
                self._name = DEVICE_NAME
                return
            except DeviceError as exc:
                last_exc = exc
                log.debug("conexion a %s fallo: %s", addr, exc)

        self._found = False
        msg = (
            f"No se pudo conectar a '{DEVICE_NAME}'. "
            "Verifica que este encendido (presiona SW1 para despertarlo)."
        )
        if last_exc is not None:
            msg = f"{msg} Ultimo error: {last_exc}"
        self._last_error = msg
        raise DeviceError(msg)

    async def _connect_to(self, address: str) -> None:
        """Conecta a `address` SIN escanear.

        ⚠️ Se le pasa un objeto BLEDevice (NO un string) porque bleak 3.x, si
        recibe un string, obliga a resolver el dispositivo con un escaneo previo
        (`BleakScanner.find_device_by_address`) y falla con BleakDeviceNotFoundError
        cuando el dispositivo no esta anunciando. Con un BLEDevice va directo a
        `BluetoothLEDevice.from_bluetooth_address_async` y Windows multiplexa el
        GATT sobre la conexion ATT que YA tiene abierta (p. ej. la del teclado HID).
        """
        client = BleakClient(
            BLEDevice(address, DEVICE_NAME, None),
            disconnected_callback=self._on_disconnected,
            timeout=CONNECT_TIMEOUT,
        )
        try:
            await client.connect()
        except (BleakError, asyncio.TimeoutError, OSError) as exc:
            try:
                await client.disconnect()
            except Exception:
                pass
            raise DeviceError(f"No se pudo conectar a {address}: {exc}") from exc

        # Verificar que exista FFE1 antes de dar la conexion por buena.
        try:
            char = client.services.get_characteristic(FFE1_UUID)
            if char is None:
                await client.disconnect()
                raise DeviceError("El dispositivo no expone la caracteristica FFE1.")
        except DeviceError:
            raise
        except Exception as exc:
            try:
                await client.disconnect()
            except Exception:
                pass
            raise DeviceError(f"Error inspeccionando servicios BLE: {exc}") from exc

        self._client = client
        self._address = address
        log.info("conectado a %s (%s)", DEVICE_NAME, address)

    def _on_disconnected(self, client: BleakClient) -> None:
        log.info("desconectado de %s", DEVICE_NAME)
        self._client = None

    async def disconnect(self) -> dict:
        async with self._lock:
            await self._disconnect_locked()
        return self.status()

    async def _disconnect_locked(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            try:
                if client.is_connected:
                    await client.disconnect()
            except Exception as exc:
                log.debug("error al desconectar: %s", exc)

    async def reconnect(self) -> dict:
        async with self._lock:
            await self._disconnect_locked()
        return await self.connect()

    # ------------------------------------------------------------------ comando
    async def command(self, cmd: str) -> str:
        """Escribe cmd a FFE1 y devuelve el valor leido (write-then-read)."""
        async with self._lock:
            if not self.connected:
                raise DeviceError(
                    "No hay dispositivo conectado. Usa Conectar primero."
                )
            return await self._command_locked(cmd)

    async def _command_locked(self, cmd: str) -> str:
        client = self._client
        if client is None:
            raise DeviceError("No hay dispositivo conectado. Usa Conectar primero.")
        try:
            await client.write_gatt_char(FFE1_UUID, cmd.encode("utf-8"), response=True)
        except (BleakError, asyncio.TimeoutError, OSError) as exc:
            self._last_error = f"Error escribiendo al dispositivo: {exc}"
            raise DeviceError(self._last_error) from exc

        prev: Optional[str] = None
        last = ""
        for attempt in range(READ_RETRIES):
            await asyncio.sleep(0.08 + attempt * 0.07)
            try:
                raw = await client.read_gatt_char(FFE1_UUID)
            except (BleakError, asyncio.TimeoutError, OSError) as exc:
                self._last_error = f"Error leyendo del dispositivo: {exc}"
                raise DeviceError(self._last_error) from exc
            text = bytes(raw).decode("utf-8", errors="replace").strip()
            last = text
            if text and (text != prev or attempt >= 2):
                return text
            prev = text

        return last


# --------------------------------------------------------------------- puente sync
# La UI / el tray corren en otros hilos; estos helpers puentean al event loop de uvicorn.
_device: Optional[MacropadDevice] = None


def get_device() -> MacropadDevice:
    global _device
    if _device is None:
        _device = MacropadDevice()
    return _device


def run_async(coro, timeout: float = 40.0):
    """Corre una corrutina del device desde un hilo que no es el de asyncio."""
    dev = get_device()
    deadline = time.time() + 15.0
    while (dev._loop is None or dev._loop.is_closed()) and time.time() < deadline:
        time.sleep(0.1)
    loop = dev._loop
    if loop is None or loop.is_closed():
        raise DeviceError("El servidor aun no esta listo.")
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return future.result(timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        raise DeviceError(str(exc)) from exc
