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

void setup(){
  loadMap();
  for(int c=0;c<4;c++) pinMode(COL[c],INPUT_PULLUP);
  kb.setRandomAddress(true);
  kb.setLogLevel(HIDLogLevel::Off);
  kb.onBeforeAdvertising(setupCfgGatt);   // crea el servicio FFE0 ANTES del advertising
  kb.begin();
  kb.setBatteryLevel(100);
}

void loop(){
  for(int r=0;r<4;r++){
    pinMode(ROW[r],OUTPUT); digitalWrite(ROW[r],LOW);
    for(int c=0;c<4;c++){
      bool pressed=(digitalRead(COL[c])==LOW);
      if(pressed&&!last[r][c]){ delay(2); pressed=(digitalRead(COL[c])==LOW); }
      uint8_t idx=PERM[r][c];
      Key& k=KEYMAP[idx];
      if(pressed&&!last[r][c]){
        if(k.type==KT_KEY) kb.tap((uint8_t)k.code);
        else if(k.type==KT_MEDIA) kb.tap(k.code);
        last[r][c]=true;
      }
      if(!pressed&&last[r][c]) last[r][c]=false;
    }
    digitalWrite(ROW[r],HIGH); pinMode(ROW[r],INPUT);
  }
  delay(5);
}
