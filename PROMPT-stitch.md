# Prompt para Google Stitch — Web App estética del Macropad BLE 4×4

Generá una **web app de configuración para un macropad Bluetooth** (teclado BLE de 4×4 = 16 teclas físicas). La app debe ser **visualmente espectacular** y **100% funcional** conectándose al macropad por **Web Bluetooth API** (Chrome/Edge, escritorio o Android).

---

## PRODUCTO

Un macropad físico (teclado mini de 16 teclas, como un Stream Deck / keypad QMK) que se conecta por Bluetooth al PC. Cada una de sus 16 teclas ejecuta una acción configurable. Esta web app es el panel de configuración: el usuario conecta, ve las 16 teclas como una grilla, les asigna acciones y las guarda en el dispositivo.

---

## CONEXIÓN BLE (Web Bluetooth API — usar exactamente esto)

- Nombre del dispositivo BLE: **`MacropadFx`**
- Servicio GATT: `0000ffe0-0000-1000-8000-00805f9b34fb`
- Característica (lectura/escritura): `0000ffe1-0000-1000-8000-00805f9b34fb`
- Flujo:
  1. `navigator.bluetooth.requestDevice({ filters:[{name:"MacropadFx"}], optionalServices:[FFE0] })`
  2. Conectar GATT → servicio FFE0 → característica FFE1.
  3. **Escribir un comando** en la característica → esperar ~500-800ms → **leer la característica** para obtener la respuesta (es un esquema write-then-read, no notificaciones).

### Comandos (protocolo de la característica)

| Comando | Respuesta |
|---|---|
| `PING` | `PONG` |
| `GET` | keymap serializado (16 teclas separadas por `\|`) |
| `SETL <keymap>` | el keymap serializado de vuelta (confirmación) |
| `RESET` | el keymap default serializado |

### Formato del keymap (16 teclas, separadas por `|`)

Cada tecla es UNO de estos 5 tipos:

- `N` — ninguna acción
- `K:<código>` — tecla simple (código HID decimal). Ej: `K:4` = A
- `M:<código>` — tecla media/consumer (código HID decimal). Ej: `M:205` = Play/Pausa
- `A:<mods>:<código>` — atajo con modificadores. `mods` es bitmask decimal: **1=Ctrl, 2=Shift, 4=Alt, 8=Win** (se pueden combinar, ej 3=Ctrl+Shift). `<código>` es el keycode HID decimal de la tecla. Ej: `A:3:41` = Ctrl+Shift+Esc
- `S:<hex1> <hex2> ...` — secuencia de keycodes en **hexadecimal** separados por espacio (máx 8). Ej: `S:1B 18 10 04 28` = escribe "hola" + Enter (1B=h, 18=o, 10=l, 04=a, 28=Enter)

Ejemplo de keymap completo:
`K:4|A:3:41|S:1B 18 10 04 28|N|M:CD|K:5|K:6|K:7|K:8|K:9|K:10|K:11|K:12|K:13|K:14|K:15|K:16`

Nota: el firmware serializa la secuencia de vuelta en hex **mayúsculas sin padding** (`1B 18 10 4 28`). Al verificar, comparar normalizando.

---

## INTERFAZ (diseño + UX)

### Estética (LO MÁS IMPORTANTE — el objetivo es que sea IMPACTANTE)

- Tema **dark mode premium** estilo "mechanical keyboard / gaming peripheral" (tipo Razer Synapse, Wooting, VIA de QMK).
- **Fondo oscuro profundo** (ej. `#0a0e14`) con **glow/acento neón** (púrpura/cian/verde). Gradientes sutiles, blur, bordes con brillo.
- La grilla de 16 teclas debe verse como **teclas mecánicas reales**: keycaps con efecto 3D (gradiente, sombra, borde inferior grueso tipo perfil SA/OEM), **efecto de presión** al hacer hover/click (scale + glow), opcional animación de "pulsación".
- **Tipografía** limpia (system-ui / Inter / monospace para códigos).
- Micro-interacciones: hover glow, transiciones suaves, feedback visual al conectar/guardar.
- Animación de estado: indicador de conexión BLE (pulso/glow), spinner o señal animada mientras conecta.
- Responsive: grilla de 4 columnas en desktop, 2 en mobile (los macropads se configuran también desde el celular).

### Funcionalidad

1. **Header**: título "Macropad 4×4" + botón "Conectar por BLE" + estado de conexión (desconectado/conectado, verde cuando conecta, rojo al desconectarse, manejar el evento `gattserverdisconnected`).
2. **Grilla de 16 teclas** (cada celda = una tecla física):
   - Cada celda muestra el **nombre/número** de la tecla (Tecla 1..16 o posición).
   - Al **click** en una tecla → se abre un **editor** (modal o panel lateral) para asignar la acción:
     - **Selector de tipo**: Ninguna / Tecla simple / Media / Atajo / Secuencia.
     - **Tecla simple / Atajo**: dropdown con TODOS los keycodes HID (letras A-Z, números, F1-F24, Enter, Tab, Espacio, Esc, flechas, Home/End/PageUp/Down, Insert/Supr, Caps Lock) con etiquetas legibles ("A", "F5", "Enter"...).
     - **Atajo**: checkboxes/toggles de modificadores **Ctrl / Shift / Alt / Win** + dropdown de tecla.
     - **Media**: dropdown con consumer keys (Play/Pausa, Siguiente, Anterior, Mute, Vol+, Vol-, Detener, Grabar, Explorador, Calc, Mail).
     - **Secuencia**: campo de texto donde se escriben keycodes hex separados por espacio (ej `1B 18 10 04 28`), con placeholder explicativo. Mostrar en vivo la secuencia interpretada ("h o l a Enter").
   - La celda en la grilla muestra un **resumen visual** de la acción asignada (ej: "Ctrl+Shift+Esc", "▶ Play", "A", "Sec(5)").
3. **Barra de acciones**: botones **Cargar mapa** (GET), **Guardar** (SETL con verificación read-back), **Restaurar default** (RESET).
4. **Log/estado**: un panel de log con las operaciones (opcional, colapsable).
5. **Persistencia visual**: al guardar con éxito, feedback claro (check verde, toast).

### Estados de la grilla

- Tecla sin asignar: apagada/opaca ("Ninguna").
- Tecla asignada: iluminada con el color de su tipo (ej. simple=cian, atajo=púrpura, media=verde, secuencia=naranja).
- Al conectar el dispositivo: las celdas se llenan con lo que devuelve `GET`.

---

## REQUISITOS TÉCNICOS

- **Un solo archivo `index.html`** autocontenido (HTML+CSS+JS inline), sin dependencias externas ni build. Funciona abriendo el archivo local en Chrome/Edge (Web Bluetooth requiere contexto seguro: localhost o archivo local).
- Español (Argentina) como idioma de la interfaz.
- Manejar errores de BLE (dispositivo no encontrado, desconexión, error de GATT) con mensajes claros y estado visual.
- Verificación al guardar: leer de vuelta y comparar (normalizando mayúsculas/espacios de la secuencia).
- Código limpio, comentado, organizado (catálogo de keycodes separado de la lógica BLE).

---

## DATOS ÚTILES PARA EL CATÁLOGO DE KEYCODES (HID usage)

**Teclas normales** (código decimal):
A=4 B=5 C=6 D=7 E=8 F=9 G=10 H=11 I=12 J=13 K=14 L=15 M=16 N=17 O=18 P=19 Q=20 R=21 S=22 T=23 U=24 V=25 W=26 X=27 Y=28 Z=29
1=30 2=31 3=32 4=33 5=34 6=35 7=36 8=37 9=38 0=39
Enter=40 Esc=41 Backspace=42 Tab=43 Espacio=44
Guion-=45 Igual=46 CorcheteIzq=47 CorcheteDer=48 Backslash=49 PuntoYComa=51 Comilla=52 Tilde=53 Coma=54 Punto=55 Slash=56
CapsLock=57 F1=58 F2=59 F3=60 F4=61 F5=62 F6=63 F7=64 F8=65 F9=66 F10=67 F11=68 F12=69
PrtSc=70 ScrollLock=71 Pausa=72 Insert=73 Home=74 PageUp=75 Supr=76 Fin=77 PageDown=78
FlechaDer=79 FlechaIzq=80 FlechaAbajo=81 FlechaArriba=82
NumLock=83 TecladoSlash=84 TecladoAsterisco=85 TecladoMenos=86
F13=104 F14=105 F15=106 F16=107 F17=108 F18=109 F19=110 F20=111 F21=112 F22=113 F23=114 F24=115

**Media/consumer** (código decimal):
Play/Pausa=205 Siguiente=181 Anterior=182 Detener=183 Grabar=178
Mute=226 Vol+=233 Vol-=234
Explorador=404 Calc=402 Mail=394
Sleep=50

**Modificadores (solo para atajos `A:`):** Ctrl=1, Shift=2, Alt=4, Win=8