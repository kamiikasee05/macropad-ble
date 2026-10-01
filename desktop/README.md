# MacropadFX Desktop — configurador de bandeja

App de bandeja (systray) para Windows que configura el **macropad BLE 4x4**
(`E:\KAMIIKASEE\projects\macropad-ble`) **sin abrir Chrome + Web Bluetooth**.

- Servidor local **FastAPI/uvicorn** en `http://127.0.0.1:8791` (solo loopback).
- Icono en la bandeja (`pystray`) que lanza **Chrome en modo app**.
- BLE por **bleak** (WinRT, sin drivers extra).
- Perfiles de keymap guardados en disco.

## Requisitos

- Python 3.12
- Paquetes: `pip install -r requirements.txt`
  (`bleak`, `pystray`, `Pillow`, `fastapi`, `uvicorn`)
- Google Chrome instalado (para el modo app; si no está, abrí la URL a mano).

## Cómo correr

```powershell
cd E:\KAMIIKASEE\projects\macropad-ble\desktop
python tray.py
```

Al arrancar:
1. Levanta el server en `http://127.0.0.1:8791`.
2. Aparece el icono en la bandeja (click izquierdo = abrir configurador).
3. Abre Chrome en modo app apuntando a la UI.

Menú del icono: **Abrir configurador** · **Reconectar dispositivo** · **Salir**.

## Flujo de la UI

`CONECTAR DISPOSITIVO` → `CARGAR (GET)` → editar teclas (clic en cada keycap) →
`GUARDAR (SETL)` → `RESETEAR` si querés volver al default.

Panel **PERFILES**: escribí un nombre + **Guardar actual** (serializa el grid),
luego **Aplicar** o **Borrar** sobre cada perfil guardado.

## API (loopback, sin auth)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | UI (`static/index.html`) |
| GET | `/api/status` | `{found, connected, name, address}` |
| POST | `/api/connect` | conecta GATT por dirección (sin scan) o scan si hace falta |
| POST | `/api/disconnect` | desconecta |
| POST | `/api/reconnect` | reconecta |
| GET | `/api/keymap` | `GET` → `{raw}` |
| POST | `/api/keymap` | body `{raw}` → `SETL <raw>` |
| POST | `/api/reset` | `RESET` |
| GET | `/api/ping` | `PING` → `{raw:"PONG"}` |
| GET | `/api/profiles` | lista de perfiles |
| POST | `/api/profiles` | body `{name, raw}` (sobrescribe) |
| DELETE | `/api/profiles/{name}` | borra |
| POST | `/api/profiles/{name}/apply` | conecta si hace falta + `SETL` |

Los errores devuelven **JSON** `{"error": "..."}` con status 400/404/409.

## ⚠️ Conectarse aunque Windows tenga el macropad como teclado (fix clave)

Cuando Windows ya está conectado al macropad como **teclado HID**, el
dispositivo **deja de anunciar** (un perfil BLE solo anuncia mientras no tiene
central). Consecuencia: un **scan no lo encuentra** y bleak, si le pasás un
**string** de dirección, obliga a escanear (`BleakScanner.find_device_by_address`)
y falla con `BleakDeviceNotFoundError`.

**Solución (implementada en `device.py`):** conectarse pasándole a `BleakClient`
un objeto **`BLEDevice`** (no un string) construido a mano:

```python
from bleak.backends.device import BLEDevice
BleakClient(BLEDevice("34:B7:DA:F7:AD:AE", "MacropadFx", None))
```

Con un `BLEDevice`, bleak setea `_device_info` y va **directo** a
`BluetoothLEDevice.from_bluetooth_address_async`, sin escanear. Windows
**multiplexa el GATT sobre la conexión ATT que ya tiene abierta**, así que la
app y el teclado usan la MISMA conexión.

→ **Ya NO hay que "eliminar el macropad" en Windows** para configurarlo.
La MAC se puede sobreescribir con la env var `MACROPAD_ADDRESS`.

## Protocolo del dispositivo

Servicio `0000ffe0-...` / característica `0000ffe1-...` (READ|WRITE).
Se escribe un string UTF-8 y se lee el nuevo valor (write-then-read).

- `PING` → `PONG`
- `GET` → keymap serializado
- `RESET` → default + keymap serializado
- `SETL <keymap>` → keymap serializado o `ERR`

Formato del keymap: 16 teclas separadas por `|`:
`N` · `K:<dec>` · `M:<dec>` · `A:<mods>:<dec>` · `S:<hex...>` (`mods:code` en hex).

## Perfiles en disco

`%APPDATA%\MacropadFx\profiles.json`
(fallback: `desktop\profiles.json` si no hay `APPDATA`).

```json
{
  "Gaming": { "raw": "K:4|K:5|...", "saved_at": "2026-09-30T12:00:00+00:00" }
}
```

Escritura atómica (temp + `os.replace`), UTF-8 sin BOM.

## Iniciar con Windows

Dos formas, siempre opcionales:

1. **Toggle en la bandeja**: menú del icono → **"Iniciar con Windows"** (con
   checkmark que refleja el estado actual). Crea/borra
   `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MacropadFX.lnk`
   apuntando al ejecutable real (`os.path.realpath(sys.executable)`; en modo
   desarrollo apunta a `pythonw tray.py`).
2. **Checkbox del instalador** (`task autostart`, **desmarcado por defecto**).

## Empaquetado (exe + instalador)

### 1) Compilar el `.exe` (PyInstaller, one-dir, sin consola)

```powershell
cd E:\KAMIIKASEE\projects\macropad-ble\desktop
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

`build.ps1` genera `icon.ico`, instala PyInstaller si falta, limpia y compila
`MacropadFX.spec`. Salidas:

- **exe**: `desktop\dist\MacropadFX\MacropadFX.exe` (~13-14 MB)
- **carpeta**: `desktop\dist\MacropadFX\` (~70-80 MB, incluye `_internal\`)

Flags: `-SkipIcon` (no regenerar el ico), `-NoClean` (no borrar build/dist).

### 2) Compilar el instalador (Inno Setup, sin admin)

```powershell
& "C:\Users\KAMIIKASEE\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss
```

Salida: `desktop\dist\MacropadFX-Setup-1.0.0.exe` (~20-30 MB).

Instala en `%LOCALAPPDATA%\Programs\MacropadFX` (`PrivilegesRequired=lowest`),
con accesos en Menú Inicio/Escritorio, desinstalador y el task de autoarranque.

### Instalación silenciosa (CI / pruebas)

```powershell
# instalar (autostart solo si se pide: /MERGETASKS=autostart)
.\dist\MacropadFX-Setup-1.0.0.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
# desinstalar
& "$env:LOCALAPPDATA\Programs\MacropadFX\unins000.exe" /VERYSILENT
```

### Icono

`icon.ico` (multi-resolución 16→256) lo genera `make_icon.py` con Pillow y se
usa en el exe, el instalador, la bandeja y `static/favicon.ico` (ventana de
Chrome). Regenerar: `python make_icon.py`.

### Notas de empaquetado (gotchas ya resueltos)

- El server usa `uvicorn.Config(..., log_config=None)` (obligatorio: sin eso el
  `.exe` falla con `Unable to configure formatter 'default'`).
- `index.html` se busca con fallback `sys._MEIPASS/static` →
  `<exe_dir>/_internal/static` → `static` junto al script (ver
  `server.static_dir()`).
- El log del exe va a `%LOCALAPPDATA%\MacropadFX\tray.log` (en modo windowed
  `sys.stderr` es `None`, así que sin archivo los errores serían invisibles).
- El atajo de Startup se crea con PowerShell `WScript.Shell` vía
  `subprocess.run(..., creationflags=CREATE_NO_WINDOW)` (sin parpadeo de consola).
- **NO se usa `pywebview`** (cuelga en esta PC): la UI se abre con **Chrome modo
  app**.

## Fuera de alcance (TODO)

- `TODO:` porcentaje real de batería (el firmware reporta 100 fijo).
- `TODO:` watcher de reconexión automática al perder el enlace.
