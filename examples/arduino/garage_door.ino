/*
 * Jarvis 3.0 — firmware Arduino exemple : porte de garage
 *
 * Protocole JSON-line sur USB série (115200 baud).
 *
 *  PC → Arduino : {"id":"garage_door","action":"open"}
 *  PC → Arduino : {"id":"garage_door","action":"close"}
 *  PC → Arduino : {"id":"garage_door","action":"status"}
 *  Arduino → PC : {"id":"garage_door","state":"opened"}
 *  Arduino → PC : {"id":"garage_door","state":"closed"}
 *  Arduino → PC : {"id":"garage_door","event":"reed_changed","state":"opened"}
 *
 * Câblage minimal (Arduino Uno) :
 *   - relais de commande      → D7 (impulsion 500 ms pour basculer le moteur)
 *   - capteur reed (ouvert)   → D2 (INPUT_PULLUP, LOW = porte ouverte)
 *
 * Dépendances : ArduinoJson (Library Manager).
 */

#include <ArduinoJson.h>

const uint8_t PIN_RELAY = 7;
const uint8_t PIN_REED  = 2;
const uint16_t RELAY_PULSE_MS = 500;

bool lastReed = false;

void emitState(const char *event = nullptr) {
  StaticJsonDocument<128> doc;
  doc["id"] = "garage_door";
  if (event) doc["event"] = event;
  doc["state"] = (digitalRead(PIN_REED) == LOW) ? "opened" : "closed";
  serializeJson(doc, Serial);
  Serial.write('\n');
}

void pulseRelay() {
  digitalWrite(PIN_RELAY, HIGH);
  delay(RELAY_PULSE_MS);
  digitalWrite(PIN_RELAY, LOW);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_RELAY, OUTPUT);
  pinMode(PIN_REED, INPUT_PULLUP);
  digitalWrite(PIN_RELAY, LOW);
  lastReed = (digitalRead(PIN_REED) == LOW);
}

void loop() {
  // 1) Lire commandes depuis le PC
  static String buf;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      StaticJsonDocument<256> doc;
      DeserializationError err = deserializeJson(doc, buf);
      buf = "";
      if (err) continue;
      if (strcmp(doc["id"] | "", "garage_door") != 0) continue;
      const char *action = doc["action"] | "";
      if (!strcmp(action, "open") && digitalRead(PIN_REED) != LOW) {
        pulseRelay();
      } else if (!strcmp(action, "close") && digitalRead(PIN_REED) == LOW) {
        pulseRelay();
      }
      emitState();  // ack
    } else if (c != '\r') {
      buf += c;
      if (buf.length() > 200) buf = "";
    }
  }

  // 2) Détection changement capteur (porte qui bouge sans qu'on le demande)
  bool reed = (digitalRead(PIN_REED) == LOW);
  if (reed != lastReed) {
    lastReed = reed;
    delay(20);  // anti-rebond
    emitState("reed_changed");
  }
}
