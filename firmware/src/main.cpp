/*
 * MACROPAD BLE 4x4 — FINAL con config por BLE (GATT custom).
 * - kb.tap((uint8_t)code) para escribir (overload teclado)
 * - PERM definitivo
 * - NVS persistencia
 * - Servicio GATT custom "FFE0" con caracteristica "FFE1" (READ/WRITE) para el keymap.
 *   La app (Web Bluetooth / Android) lee el mapa y lo escribe.
 * - SIN CDC (rompe HID). SIN USB serial.
 */
#include <Arduino.h>
#include <HijelHID_BLEKeyboard.h>
#include <Preferences.h>
#include <NimBLEDevice.h>
#include <driver/rtc_io.h>
#include <driver/gpio.h>
#include <esp_sleep.h>
#include <esp_system.h>

// ==== Deep sleep / wake por tecla ====
// Cuando no se toca ninguna tecla por IDLE_SLEEP_MS, el chip entra en deep sleep
// (bajo consumo ~uA). Cualquier tecla lo despierta via EXT1 wake en las columnas.
// Al despertar, vuelve a anunciarse/nconectar por BLE.
#ifndef IDLE_SLEEP_MS
#define IDLE_SLEEP_MS 300000   // 5 minutos de inactividad -> deep sleep (produccion)
#endif

// ==== Reset por combinacion de esquinas opuestas ====
// Mantener presionadas SW1 (sup-izq) + tecla inf-der (esquina opuesta) por
// RESET_MS -> reinicia el advertising BLE (kb.end()+kb.begin()) para que
// Windows reconecte (NO usar esp_restart: NimBLE deja el advertising muerto).
// Posiciones de escaneo: SW1 = ROW[0]xCOL[2], inf-der = ROW[2]xCOL[0]
//   (SW1 = PERM[0][2]=0 -> 'A'   |   inf-der = PERM[2][0]=15 -> 'P')
#define RESET_MS 3000
#define RESET_SW1_R 0
#define RESET_SW1_C 2
#define RESET_INF_R 2
#define RESET_INF_C 0

bool wakeFromSleep = false;

HijelHID_BLEKeyboard kb("MacropadFx", "KAMIIKASEE", 100);
const uint8_t ROW[4] = {0, 2, 4, 6};
const uint8_t COL[4] = {1, 3, 5, 7};
const uint8_t PERM[4][4] = {
  {3, 1, 0, 2},
  {11, 9, 8, 10},
  {15, 13, 12, 14},
  {7, 5, 4, 6},
};

enum KeyType { KT_KEY, KT_MEDIA };
struct Key { KeyType type; uint16_t code; };
#define K(kc) {KT_KEY,(kc)}
#define M(mc) {KT_MEDIA,(mc)}

const Key DEFAULT_MAP[16] = {
  K(KEY_A), K(KEY_B), K(KEY_C), K(KEY_D),
  K(KEY_E), K(KEY_F), K(KEY_G), K(KEY_H),
  K(KEY_I), K(KEY_J), K(KEY_K), K(KEY_L),
  K(KEY_M), K(KEY_N), K(KEY_O), K(KEY_P),
};

Key KEYMAP[16];
Preferences prefs;
const char* NVS_NS = "keymap";
bool last[4][4] = {false};
uint32_t lastActivity = 0;

// ==== GATT custom (config por BLE) ====
NimBLECharacteristic* pCfgChar = nullptr;
const char* CFG_SERVICE_UUID = "FFE0";
const char* CFG_CHAR_UUID    = "FFE1";

void loadMap() {
  prefs.begin(NVS_NS, false);
  if (prefs.getBytes("data", KEYMAP, sizeof(KEYMAP)) != sizeof(KEYMAP))
    memcpy(KEYMAP, DEFAULT_MAP, sizeof(KEYMAP));
  prefs.end();
}
void saveMap() {
  prefs.begin(NVS_NS, false);
  prefs.putBytes("data", KEYMAP, sizeof(KEYMAP));
  prefs.end();
}

// Serializa el keymap a "K:4|K:5|...|M:205" (16 teclas)
void serializeKeymap(std::string& out) {
  out.clear();
  char buf[16];
  for (int i=0;i<16;i++) {
    char t=(KEYMAP[i].type==KT_KEY)?'K':'M';
    snprintf(buf,sizeof(buf),"%s%c:%u",(i?"|":""),t,KEYMAP[i].code);
    out += buf;
  }
}
bool parseKeymap(const std::string& in) {
  Key nk[16]; int idx=0; const char* p=in.c_str();
  while(*p&&idx<16){
    char t=*p; if(t!='K'&&t!='M') return false;
    p++; if(*p!=':') return false; p++;
    uint16_t code=(uint16_t)atoi(p);
    while(*p&&*p!='|') p++;
    nk[idx++]=(t=='K')?Key{KT_KEY,code}:Key{KT_MEDIA,code};
    if(*p=='|') p++;
  }
  if(idx==16){ memcpy(KEYMAP,nk,sizeof(KEYMAP)); saveMap(); return true; }
  return false;
}

// Callbacks de la caracteristica de config (GATT BLE)
// La caracteristica FFE1 tiene un "valor" que se lee/escribe.
// onRead: NO hacer setValue acá — eso sobreescribe el valor leído.
//         Solo serializar al valor inicial en setupCfgGatt.
// onWrite: procesar comandos y actualizar el valor con setValue.
class CfgCallbacks : public NimBLECharacteristicCallbacks {
  void onRead(NimBLECharacteristic* pChar, NimBLEConnInfo& connInfo) override {
    // No hacer nada — el valor ya está en la característica (seteado por onWrite o setupCfgGatt)
  }
  void onWrite(NimBLECharacteristic* pChar, NimBLEConnInfo& connInfo) override {
    std::string s = pChar->getValue();
    if (s == "PING") {
      pChar->setValue(std::string("PONG"));
    } else if (s == "GET") {
      std::string out; serializeKeymap(out);
      pChar->setValue(out);
    } else if (s == "RESET") {
      memcpy(KEYMAP, DEFAULT_MAP, sizeof(KEYMAP));
      saveMap();
      std::string out; serializeKeymap(out);
      pChar->setValue(out);
    } else if (s.rfind("SETL ", 0) == 0) {
      if (parseKeymap(s.substr(5))) {
        std::string out; serializeKeymap(out);
        pChar->setValue(out);
      } else {
        pChar->setValue(std::string("ERR"));
      }
    } else {
      // Aceptar keymap crudo sin prefijo (compatibilidad)
      if (parseKeymap(s)) {
        std::string out; serializeKeymap(out);
        pChar->setValue(out);
      }
    }
  }
};

void setupCfgGatt(NimBLEServer* server) {
  if (!server) return;
  NimBLEService* svc = server->createService(CFG_SERVICE_UUID);
  pCfgChar = svc->createCharacteristic(CFG_CHAR_UUID, NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::WRITE);
  pCfgChar->setCallbacks(new CfgCallbacks());
  std::string s; serializeKeymap(s);
  pCfgChar->setValue(s);
  svc->start();
}

// ==== Deep sleep: apagar y dormir hasta que se toque SOLO UNA tecla (SW1) ====
// SW1 = tecla superior-izquierda (letra 'A') = fila de escaneo 0 (ROW[0]=GPIO0)
// columna de escaneo 2 (COL[2]=GPIO5). Ambos pins RTC (válidos para deep sleep).
// - Mask de wake = SOLO COL[2] (GPIO5).
// - Hold a GND SOLO de ROW[0] (GPIO0) -> solo SW1 puede bajar GPIO5 a GND.
// Las demas teclas no despiertan (sus filas no estan a GND, y/o no estan en el mask).
void enterSleep() {
  // Fila de SW1 (fila 0) a GND. Las demas filas NO van a GND (para no despertar).
  pinMode(ROW[0], OUTPUT);
  digitalWrite(ROW[0], LOW);
  delay(10);

  // Columna de SW1 (col 2) con pull-up + wake. Las demas quedan pull-up sin wake.
  for (int c = 0; c < 4; c++) pinMode(COL[c], INPUT_PULLUP);

  // Hold SOLO de la fila 0 (GPIO0) para mantener GND en deep sleep
  gpio_hold_en((gpio_num_t)ROW[0]);

  // Wake: solo columna de SW1 (COL[2] = GPIO5)
  uint64_t mask = (1ULL << COL[2]);
  esp_deep_sleep_enable_gpio_wakeup(mask, ESP_GPIO_WAKEUP_GPIO_LOW);
  esp_deep_sleep_start();
}

void setup(){
  // Detectar si despertamos de deep sleep (GPIO = tecla presionada)
  if (esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_GPIO) {
    wakeFromSleep = true;
    // Soltar el hold de la fila 0 (GPIO0) puesto en enterSleep
    gpio_hold_dis((gpio_num_t)ROW[0]);
  }

  loadMap();
  for(int c=0;c<4;c++) pinMode(COL[c],INPUT_PULLUP);
  // MAC FIJA para que Windows reconecte el MISMO dispositivo tras deep sleep.
  // (Con MAC random, cada wake es un "dispositivo nuevo" y no reconecta auto.)
  kb.setRandomAddress(false);
  kb.setLogLevel(HIDLogLevel::Off);
  kb.onBeforeAdvertising(setupCfgGatt);   // crea el servicio FFE0 ANTES del advertising
  kb.begin();
  kb.setBatteryLevel(100);
  lastActivity = millis();
}

void loop(){
  // Esperar reconexion BLE tras despertar: retrasar el envio de las teclas
  // que se presionen durante el wake (para no perder la tecla despertadora).
  static uint32_t wakeWaitStart = 0;
  static bool     waitingWake = wakeFromSleep;
  if (waitingWake) {
    if (wakeWaitStart == 0) wakeWaitStart = millis();
    // Reconecto parea con timeout: si stay presionada la tecla, la captura
    if (kb.isPaired() || (millis() - wakeWaitStart > 8000)) {
      waitingWake = false;
    } else {
      delay(50);
    }
  }

  // Force sleep (debug): descomentar para dormir rapidito al boot
  // if (millis() < 3000 && millis() > 2000) { enterSleep(); }

  for(int r=0;r<4;r++){
    pinMode(ROW[r],OUTPUT); digitalWrite(ROW[r],LOW);
    for(int c=0;c<4;c++){
      bool pressed=(digitalRead(COL[c])==LOW);
      if(pressed&&!last[r][c]){ delay(2); pressed=(digitalRead(COL[c])==LOW); }
      uint8_t idx=PERM[r][c];
      Key& k=KEYMAP[idx];
      if(pressed&&!last[r][c]){
        // Solo enviar si no estamos esperando la reconexion
        if (!waitingWake) lastActivity = millis();
        if (!waitingWake) {
          if(k.type==KT_KEY) kb.tap((uint8_t)k.code);
          else if(k.type==KT_MEDIA) kb.tap(k.code);
        }
        last[r][c]=true;
      }
      if(!pressed&&last[r][c]) last[r][c]=false;
    }
    digitalWrite(ROW[r],HIGH); pinMode(ROW[r],INPUT);
  }
  delay(5);

  // ==== Reset por combinacion de esquinas opuestas (mantener 3s) ====
  // Reinicia el advertising BLE (end + begin) para que Windows reconecte.
  // NO usar esp_restart() aqui: NimBLE deja el advertising muerto tras esp_restart().
  static uint32_t resetHoldStart = 0;
  static bool resetTriggered = false;
  if (last[RESET_SW1_R][RESET_SW1_C] && last[RESET_INF_R][RESET_INF_C]) {
    if (resetHoldStart == 0) resetHoldStart = millis();
    if (millis() - resetHoldStart >= RESET_MS && !resetTriggered) {
      resetTriggered = true;
      kb.end();
      delay(50);
      kb.begin();          // re-anuncia (restart path de la lib, stack ya inicializado)
      resetHoldStart = 0;
    }
  } else {
    resetHoldStart = 0;
  }

  // Deep sleep por inactividad
  if (!waitingWake && (millis() - lastActivity) > IDLE_SLEEP_MS) {
    enterSleep();
  }
}
