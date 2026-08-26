# Macropad BLE 4x4

Macropad Bluetooth de 16 teclas (4x4) con ESP32-C3. Configurable por BLE con una web app (Web Bluetooth). Sin cables, sin software instalado.

## Features

- **16 teclas BLE HID** — se conecta por Bluetooth y escribe como teclado real
- **Config por BLE** — servicio GATT custom (FFE0/FFE1) para leer/escribir el keymap
- **Web Bluetooth App** — `webapp/index.html` para configurar desde Chrome/Edge (PC o Android)
- **Persistencia NVS** — el keymap sobrevive reinicios del ESP32
- **Sin USB, sin drivers** — todo funciona por Bluetooth

## Hardware

| Componente | Qty | Nota |
|------------|-----|------|
| ESP32-C3 Super Mini | 1 | Devkit con BOOT+RST |
| Switches mecanicos | 16 | Cherry/Kailh compatible |
| Diodos 1N4148 | 16 | Anti-ghosting (obligatorio) |
| Cable CAT5 UTP | ~1m | Solidos=fila, Rayados=columna |

### Pinout

```
FILA0 = GPIO0    COL0 = GPIO1
FILA1 = GPIO2    COL1 = GPIO3
FILA2 = GPIO4    COL2 = GPIO5
FILA3 = GPIO6    COL3 = GPIO7
```

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

### Compilar y flashear

```bash
cd firmware
pio run              # compilar
pio run -t upload    # flashear por USB
```

### Config (por defecto)

Teclas default: A B C D / E F G H / I J K L / M N O P.

El keymap se guarda en NVS y persiste entre reinicios. Para cambiar las teclas, usar la Web App (ver abajo).

## Web App (Web Bluetooth)

Abri `webapp/index.html` en Chrome o Edge (PC o Android).

1. Click en **"Conectar por BLE"**
2. Selecciona **"MacropadFx"** en el dialogo de Bluetooth
3. Click en **"Cargar mapa"** para leer la config actual
4. Edita las 16 teclas (dropdown con teclado, media, funciones)
5. Click en **"Guardar"** para escribir al macropad
6. **"Restaurar default"** para volver a A-P

> **Nota:** Web Bluetooth requiere HTTPS o archivo local. Chrome en Android tambien funciona.

## Protocolo GATT

Servicio: `FFE0` / Caracteristica: `FFE1` (READ | WRITE)

| Comando | Respuesta | Descripcion |
|---------|-----------|-------------|
| `PING` | `PONG` | Heartbeat |
| `GET` | `K:4\|K:5\|...` | Lee el keymap (16 teclas) |
| `SETL K:4\|K:5\|...` | keymap actualizado | Escribe el keymap |
| `RESET` | keymap default | Restaura A-P |

Formato de tecla: `K:<codigo>` (teclado) o `M:<codigo>` (media). Codigos HID estandar (ej: A=0x04, F1=0x3A, Play=0xCD).

## Bugs resueltos (documentacion tecnica)

Si armas un macropad similar, esto te va a ahorrar horas:

1. **`kb.tap()` vs `press()/release()`** — usar SIEMPRE `kb.tap()` para teclas normales. `press()` + `release()` en loop (con delay) rompe el reporte HID y Windows lo descarta.

2. **`uint16_t code` en el struct `Key`** — `kb.tap(uint16_t)` llama al overload de **media keys** (consumer), no de teclado. Solucion: `kb.tap((uint8_t)code)`.

3. **`ARDUINO_USB_CDC_ON_BOOT=1`** — rompe el HID BLE en ESP32-C3 con NimBLE. Sin CDC, el ESP32-C3 usa USB-Serial-JTAG para el serial.

4. **Servicios GATT creados despues de `startAdvertising()`** — el callback `onWrite` no se dispara. Solucion: hook `onBeforeAdvertising()` en la libreria HijelHID para crear el servicio ANTES del advertising.

5. **`onRead` con `setValue()`** — sobreescribe el valor cada vez que se lee, pisando respuestas a comandos. `onRead` no debe hacer `setValue`.

## Stack

- **Plataforma:** pioarduino (Arduino 3.x + ESP-IDF 5.x)
- **Libreria HID:** [HijelHID_BLEKeyboard](https://github.com/hijelhub/HijelHID_BLEKeyboard)
- **BLE:** NimBLE-Arduino 2.3.8
- **Web App:** HTML vanilla + Web Bluetooth API

## Licencia

MIT
