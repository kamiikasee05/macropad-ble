# Macropad BLE 4x4

Macropad Bluetooth de 16 teclas (4x4) con ESP32-C3. Configurable por BLE con una web app (Web Bluetooth). Sin cables, sin software instalado.

## Features

- **16 teclas BLE HID** — se conecta por Bluetooth y escribe como teclado real
- **4 tipos de acción por tecla** — tecla simple, media key, **atajo con modificadores** (Ctrl+Shift+Esc) y **secuencias de teclas** (escribe "hola" + Enter)
- **Config por BLE** — servicio GATT custom (FFE0/FFE1) para leer/escribir el keymap
- **Web Bluetooth App** — para configurar desde Chrome/Edge (PC o Android), **hosteada en GitHub Pages**
- **Persistencia NVS** — el keymap sobrevive reinicios del ESP32
- **Deep sleep + wake por tecla** — baja el consumo a ~µA; se despierta con la tecla SW1
- **Reset por combinación** — mantener SW1 + tecla inferior-derecha 3s reinicia el BLE
- **Sin USB, sin drivers** — todo funciona por Bluetooth

## Web App (Web Bluetooth)

**Online (GitHub Pages):** 👉 **https://kamiikasee05.github.io/macropad-ble/**

O abri `webapp/index.html` en Chrome o Edge (PC o Android).

1. Click en **"CONECTAR DISPOSITIVO"**
2. Selecciona **"MacropadFx"** en el dialogo de Bluetooth
3. Click en **"CARGAR (GET)"** para leer la config actual
4. Click en una tecla para abrir el editor (derecha):
   - **Tipo:** None / HID (tecla simple) / Media / Atajo / Secuencia
   - **Atajo:** checkboxes Ctrl/Shift/Alt/Win + keycode base
   - **Secuencia:** keycodes hex separados por espacio (ej: `1B 18 10 04 28` = "hola" + Enter), con preview en vivo
5. Click en **"GUARDAR (SETL)"** — verifica con read-back
6. **"RESETEAR"** para volver a A-P

> **Nota:** Web Bluetooth requiere HTTPS — GitHub Pages lo provee. Tambien funciona con el archivo local (`file://`).

## Hardware

| Componente | Qty | Nota |
|------------|-----|------|
| ESP32-C3 Super Mini | 1 | Devkit con BOOT+RST |
| Switches mecanicos | 16 | Cherry/Kailh compatible |
| Diodos 1N4148 | 16 | Anti-ghosting (obligatorio) |
| Cable CAT5 UTP | ~1m | Solidos=fila, Rayados=columna |
| LiPo 3.7V + TP4056 | 1 | (opcional) alimentacion por bateria |

### Pinout

```
FILA0 = GPIO0    COL0 = GPIO1
FILA1 = GPIO2    COL1 = GPIO3
FILA2 = GPIO4    COL2 = GPIO5
FILA3 = GPIO6    COL3 = GPIO7
```

> ⚠️ **Deep sleep:** en el ESP32-C3 SOLO los GPIO 0-5 son RTC. Por eso SOLO la tecla SW1 (fila0/col2 → GPIO0/GPIO5) despierta el macropad del deep sleep.

### Matriz 4x4

```
           COL0    COL1    COL2    COL3
FILA0 ──┬──[SW]────[SW]────[SW]────[SW]
FILA1 ──┤──[SW]────[SW]────[SW]────[SW]
FILA2 ──┤──[SW]────[SW]────[SW]────[SW]
FILA3 ──┘──[SW]────[SW]────[SW]────[SW]

[SW] = switch + diodo 1N4148 (anodo→fila, catodo→col)
```

## Firmware

### Requisitos

- [PlatformIO](https://platformio.org/) (`pip install platformio`)
- ESP32-C3 conectado por USB
- Librerias (clonar a `~/.platformio/lib/` si el registry falla):
  - [HijelHID_BLEKeyboard](https://github.com/hijelhub/HijelHID_BLEKeyboard)
  - [NimBLE-Arduino](https://github.com/h2zero/NimBLE-Arduino) (tag `2.3.8`)

### Compilar y flashear

```bash
cd firmware
pio run              # compilar
pio run -t upload    # flashear por USB
```

> ⚠️ Tras un `erase-flash`, SIEMPRE grabar el binario completo en 0x0:
> `python -m esptool --port COMx write-flash 0x0 .pio/build/macropad-ble/firmware.factory.bin`

### Config (por defecto)

Teclas default: A B C D / E F G H / I J K L / M N O P.

El keymap se guarda en NVS y persiste entre reinicios. Para cambiar las teclas, usar la Web App.

### Deep sleep y reset

- **Deep sleep:** tras 5 min sin actividad, el macropad duerme (~µA). Se despierta tocando **SW1** (tecla superior-izquierda).
- **Reset BLE:** mantener **SW1 + tecla inferior-derecha** por **3 segundos** → reinicia el advertising BLE (para cuando Windows se desincroniza).

## Protocolo GATT

Servicio: `FFE0` / Caracteristica: `FFE1` (READ | WRITE)

| Comando | Respuesta | Descripcion |
|---------|-----------|-------------|
| `PING` | `PONG` | Heartbeat |
| `GET` | keymap (16 teclas) | Lee el keymap |
| `SETL <keymap>` | keymap actualizado | Escribe el keymap |
| `RESET` | keymap default | Restaura A-P |

### Formato del keymap (16 teclas separadas por `|`)

| Formato | Tipo | Ejemplo |
|---------|------|---------|
| `N` | Ninguna | `N` |
| `K:<code>` | Tecla simple (HID decimal) | `K:4` = A |
| `M:<code>` | Media key (HID decimal) | `M:205` = Play/Pausa |
| `A:<mods>:<code>` | Atajo (mods bitmask decimal: 1=Ctrl, 2=Shift, 4=Alt, 8=Win) | `A:3:41` = Ctrl+Shift+Esc |
| `S:<hex codes>` | Secuencia (keycodes hex, max 8, sep por espacio) | `S:1B 18 10 04 28` = "hola"+Enter |

Codigos HID estandar (ej: A=0x04, F1=0x3A, Play=0xCD).

## Bugs resueltos (documentacion tecnica)

Si armas un macropad similar, esto te va a ahorrar horas:

1. **`kb.tap()` vs `press()/release()`** — usar SIEMPRE `kb.tap()` para teclas normales. `press()` + `release()` en loop (con delay) rompe el reporte HID y Windows lo descarta.

2. **`uint16_t code` en el struct `Key`** — `kb.tap(uint16_t)` llama al overload de **media keys** (consumer), no de teclado. Solucion: `kb.tap((uint8_t)code)`.

3. **`ARDUINO_USB_CDC_ON_BOOT=1`** — rompe el HID BLE en ESP32-C3 con NimBLE. Sin CDC, el ESP32-C3 usa USB-Serial-JTAG para el serial.

4. **Servicios GATT creados despues de `startAdvertising()`** — el callback `onWrite` no se dispara. Solucion: hook `onBeforeAdvertising()` en la libreria HijelHID para crear el servicio ANTES del advertising.

5. **`onRead` con `setValue()`** — sobreescribe el valor cada vez que se lee, pisando respuestas a comandos. `onRead` no debe hacer `setValue`.

6. **`esp_restart()` mata el advertising BLE (NimBLE)** — para el reset por combinacion usar `kb.end()` + `kb.begin()` (restart path de HijelHID). Con `esp_restart()` el chip corre pero nunca re-anuncia.

7. **Deep sleep solo con pines RTC (GPIO 0-5)** — `esp_deep_sleep_enable_gpio_wakeup()` rechaza el mask con error si contiene un pin no-RTC y cancela TODO el wake. Para que SOLO una tecla despierte: mask de 1 sola columna + solo esa fila a GND.

8. **Secuencias en el protocolo: hex con `strtol` base 16** — parsear `S:1B 18 10...` con `atoi` rompe (`1B`→`1`). Media keys SIEMPRE decimal (`M:205`, no `M:CD`).

## Deploy de la web app (GitHub Pages)

El repo publica `webapp/` automaticamente en **https://kamiikasee05.github.io/macropad-ble/** via GitHub Actions (`.github/workflows/pages.yml`). Cada push a `master` que toque `webapp/` re-despliega en ~20s. El prompt para regenerar la UI con Google Stitch esta en `PROMPT-stitch.md`.

## Stack

- **Plataforma:** pioarduino (Arduino 3.x + ESP-IDF 5.x)
- **Libreria HID:** [HijelHID_BLEKeyboard](https://github.com/hijelhub/HijelHID_BLEKeyboard)
- **BLE:** NimBLE-Arduino 2.3.8
- **Web App:** HTML vanilla + Web Bluetooth API (estetica generada con Google Stitch)

## Licencia

MIT