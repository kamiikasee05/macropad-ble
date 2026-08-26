# Macropad BLE 4×4 — ESP32-C3 con capas

Macropad Bluetooth de 16 teclas (4×4) con **capas** estilo QMK, usando ESP32-C3 + ESP32-BLE-Keyboard.

## Hardware

- **MCU:** ESP32-C3 (devkit con botones BOOT+RST, mismo modelo que el bricked)
- **Switches:** 16 mecánicos de 2 patas (Cherry/Kailh compatible)
- **Diodos:** 16× 1N4148 (anti-ghosting, obligatorio en matriz)
- **Conexión:** Bluetooth LE (HID) — sin cable

## Matriz 4×4 (8 pines)

```
           COL0    COL1    COL2    COL3
FILA0 ──┬──[◆]────[◆]────[◆]────[◆]
FILA1 ──┤──[◆]────[◆]────[◆]────[◆]
FILA2 ──┤──[◆]────[◆]────[◆]────[◆]
FILA3 ──┘──[◆]────[◆]────[◆]────[◆]

[◆] = switch mecánico + diodo 1N4148
```

### Conexión del diodo 1N4148 (CRÍTICO)

```
        switch
    ┌────││────┐        ┌──────┐
    │   [SW]   │        │      │
FILA ┼─────────┼──▶|─── COL
              ánodo   cátodo
```

- **Ánodo del diodo → lado de la FILA** (hacia el pin de fila)
- **Cátodo del diodo → lado de la COLUMNA** (hacia el pin de columna)
- El switch va en serie con el diodo (fila → switch → diodo → columna)

## Pinout ESP32-C3 (elegido a propósito)

| Función | GPIO | Nota |
|---------|------|------|
| FILA0 | GPIO0 | |
| FILA1 | GPIO1 | |
| FILA2 | GPIO2 | |
| FILA3 | GPIO3 | |
| COL0 | GPIO4 | |
| COL1 | GPIO5 | |
| COL2 | GPIO6 | |
| COL3 | GPIO7 | |
| (libre) | GPIO8-10 | ❌ strap pins, NO usar |
| (libre) | GPIO18-21 | ❌ USB/UART |

## Firmware

- **Plataforma:** PlatformIO + Arduino framework + `esp32-c3-devkitm-1`
- **Librería:** `ESP32-BLE-Keyboard` (t-vk) — BLE HID madura
- **Capas:** implementadas en C++ en `src/main.cpp` (3 capas: base/media/navegación + teclas de capa estilo QMK `MO()`)

### Capas

| Capa | Contenido |
|------|-----------|
| **0 — BASE** | F13-F20 + macros productividad (copiar/pegar/deshacer) |
| **1 — MEDIA** | play/pause, vol+-, mute, next/prev |
| **2 — NAV** | flechas, Home/End, PageUp/Down, Tab, Enter |

### Teclas de capa (estilo QMK)
- **MO(1)** = manteniendo la tecla, activa capa MEDIA
- **MO(2)** = manteniendo la tecla, activa capa NAV
- **TT(0)** = toggle base (alterna entre capa actual y base)

## Compilar y flashear

```bash
# En projects/macropad-ble/firmware/
pio run                 # compila
pio run -t upload       # flashea por USB (COM8, USB nativo del C3)
```

## ✅ ESTADO: FUNCIONA COMO TECLADO BLE (24/8/2026)

El macropad 4×4 BLE con capas **funciona** — Windows lo reconoce como teclado real (Batería + HID presentes). Solución definitiva: **HijelHID_BLEKeyboard + pioarduino (Arduino 3.x) + NimBLE 2.3.8**.

## 🗺️ ROADMAP

### Fase 1: Batería + TP4056 (en desarrollo)
- Batería LiPo **3.7V 600mAh** + cargador **TP4056**
- El ESP32-C3 Super Mini tiene pin 5V (entrada USB) y 3V3 (salida regulada)
- Conexión: batería → TP4056 (BAT+ / BAT-) + TP4056 5V → VBUS/5V del ESP32
- El TP4056 protege la batería (overcharge/overdischarge) y carga por USB
- **Monitoreo de batería:** el ESP32-C3 tiene ADC para leer el voltaje de la batería (vía divisor) y reportar al HID (setBatteryLevel en HijelHID ya soporta esto)
- ⚠️ El Super Mini comparte pin 5V para USB y carga — verificar diodo de aislamiento si se quiere cargar y usar a la vez

### Fase 2: Piezo para feedback sonoro
- **Piezo buzzer** en GPIO8 (pin libre, no está en la matriz, no es el BOOT)
- **Beep al cambiar de capa**: un tono distinto por capa (base=440Hz, media=523Hz, nav=587Hz, macros=659Hz, f13=698Hz) para saber dónde estás por sonido
- **Beep de batería baja**: patrón de alerta (2 beeps cortos) cuando la batería < 20%
- USO: `tone(GPIO8, freq, dur)` (LEDC PWM en ESP32-C3)

### Fase 3: App de personalización de capas
- Aplicación (web o escritorio) para editar las capas del macropad
- Guardar config en NVS del ESP32-C3
- Comunicación por BLE (GATT custom) o por el USB cuando está conectado
- UI para mapear cada tecla de cada capa

## Notas técnicas importantes (del camino recorrido)
- **HID en ESP32-C3:** SOLO funciona con HijelHID + pioarduino (Arduino 3.x). t-vK y forks NO registran el HID en este chip. Ver MEMORY.md para la config exacta.
- El firmware.factory.bin (completo con bootloader+particiones) es el que se flashea.
- Pinout real: filas GPIO0,2,4,6 (sólidos) / columnas GPIO1,3,5,7 (rayados), CAT5 UTP.
- Booleano: `setRandomAddress(true)` en setup evita el bug del loop conecta/desconecta de Windows.

## Estados

- [ ] Cables soldados (fila/columna/diodos)
- [ ] Firmware compilado
- [ ] Flasheado al ESP32-C3
- [ ] Prueba BLE + capas