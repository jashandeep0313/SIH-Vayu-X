/*
 * Vayu-X last-mile siren tower — ESP32 firmware  v2.0
 * SIH PS 26070 · Team Vayu-X (152)
 *
 * A coastal warning that depends on the cellular network fails exactly where it
 * matters. This is the part that does not: a microcontroller driving a lamp
 * stack and a piezo siren, taking commands over whatever link is available.
 *
 * ------------------------------------------------------------- transports
 * The same command parser sits behind three transports, so the control-room
 * code is identical whichever one is carrying the bytes:
 *
 *   USB serial   always on. Used for provisioning and as the fallback.
 *   WiFi (STA)   joins a network; commands over HTTP. Credentials live in NVS,
 *                never in this file and never in git.
 *   WiFi (AP)    if it cannot join, it becomes its own access point. No router,
 *                no infrastructure — which is the deployment story, not a
 *                workaround.
 *
 * OTA is enabled, so this is the last flash that needs a cable.
 *
 * -------------------------------------------------------------- protocol
 * Line-based ASCII. Human-readable on purpose: you can drive the whole tower
 * from a serial monitor or a browser address bar when something is wrong at
 * 2 a.m.
 *
 *   PING                        -> PONG vayux-siren 2.0
 *   ALERT <SEV> <CAT> <SECS>    -> OK ALERT <SEV> <SECS>
 *   STOP                        -> OK STOP
 *   TEST                        -> OK TEST
 *   STATUS                      -> OK <state> <secs_remaining>
 *   NET                         -> OK <mode> <ip> <ssid> <rssi>
 *   SSID <network name>         -> OK SSID saved      (serial only)
 *   PASS <passphrase>           -> OK PASS saved      (serial only)
 *   REBOOT                      -> OK REBOOT          (serial only)
 *   WIFICLEAR                   -> OK WIFI cleared    (serial only)
 *
 * Over HTTP the same strings are reached as:
 *   GET /cmd?q=ALERT+RED+ESCS+15      the general form
 *   GET /ping  /status  /test  /stop  convenience aliases
 *
 * Credential commands are refused over HTTP on purpose — a network credential
 * should not be settable by anything already on the network. Each takes the
 * rest of the line, so names and passphrases containing spaces work.
 *
 * SEV is GREEN | YELLOW | ORANGE | RED.
 *
 * ------------------------------------------------------------ behaviour
 *   GREEN   green lamp, silent            all clear
 *   YELLOW  yellow lamp, chirp every 3 s  SCS  — stay alert
 *   ORANGE  yellow blink, pulsed siren    VSCS — prepare to evacuate
 *   RED     red lamp, continuous wail     ESCS/SuCS — evacuate now
 *
 * The wail is a frequency sweep, not a fixed tone. A steady beep reads as an
 * appliance; a rising-falling sweep reads as an emergency, and carries further
 * over wind and surf.
 *
 * Nothing here blocks. A delay() in the siren loop would mean the tower stops
 * listening for STOP, which is unacceptable for something this loud.
 */

#include <ArduinoOTA.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <WebServer.h>
#include <WiFi.h>

// Access-point fallback. Deliberately not a secret: it is the "no
// infrastructure exists" path, and anyone close enough to join is close enough
// to hear the siren anyway.
const char *AP_SSID = "Vayu-X-Siren";
const char *AP_PASS = "vayux2026";
const char *MDNS_NAME = "vayux-siren";   // reachable as vayux-siren.local
const unsigned long STA_TIMEOUT_MS = 25000;

// ---------------------------------------------------------------- wiring
// CHANGE THESE to match how you actually wired the board.
// Avoided: GPIO 0/2/12/15 (strapping pins — wrong level at boot stops the
// board starting), GPIO 6-11 (flash), GPIO 34-39 (input only, no output).
const int PIN_RED    = 25;   // traffic-light module, R
const int PIN_YELLOW = 26;   // traffic-light module, Y
const int PIN_GREEN  = 27;   // traffic-light module, G
const int PIN_BUZZER = 14;   // passive buzzer / MOSFET gate for a real siren
const int PIN_SENSOR = 33;   // vibration/shock module, DO  (input only is fine)

// Set false if you fitted an ACTIVE buzzer (one that makes its own tone).
// Active buzzers cannot change pitch, so the sweep is replaced by on/off.
const bool PASSIVE_BUZZER = true;

// Siren sweep range, Hz. 600-1600 sits where cheap piezos are loudest and
// where the human ear is most sensitive.
const int SWEEP_LOW  = 600;
const int SWEEP_HIGH = 1600;

const int BUZZER_CHANNEL = 0;   // ESP32 LEDC hardware PWM channel (core 2.x only)

// ESP32 core 3.x rewrote the LEDC API: channels are gone and the tone calls
// take a pin instead. Building against whichever core is installed is worth
// more than pinning to an old one, so both are supported here.
#ifndef ESP_ARDUINO_VERSION_MAJOR
  #define ESP_ARDUINO_VERSION_MAJOR 2
#endif

#if ESP_ARDUINO_VERSION_MAJOR >= 3
  #define BUZZER_BEGIN()   ledcAttach(PIN_BUZZER, 1000, 8)
  #define BUZZER_TONE(hz)  ledcWriteTone(PIN_BUZZER, (hz))
#else
  #define BUZZER_BEGIN()   do { ledcSetup(BUZZER_CHANNEL, 1000, 8); \
                               ledcAttachPin(PIN_BUZZER, BUZZER_CHANNEL); } while (0)
  #define BUZZER_TONE(hz)  ledcWriteTone(BUZZER_CHANNEL, (hz))
#endif

// If the laptop goes quiet mid-alert, keep sounding for the duration already
// granted, then fall back to GREEN. A tower must never latch on forever.
const unsigned long MAX_ALERT_MS = 120000UL;

// ----------------------------------------------------------------- state
enum Severity { SEV_GREEN, SEV_YELLOW, SEV_ORANGE, SEV_RED };
Severity state = SEV_GREEN;
unsigned long alertUntil = 0;
unsigned long lastBlink  = 0;
bool blinkOn = false;
String category = "";

WebServer server(80);
Preferences prefs;
bool apMode = false;

String handle(String line, bool fromSerial);   // forward declaration
void startNetwork();
String netSummary();

void setup() {
  Serial.begin(115200);
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_YELLOW, OUTPUT);
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_SENSOR, INPUT);

  if (PASSIVE_BUZZER) {
    BUZZER_BEGIN();
  } else {
    pinMode(PIN_BUZZER, OUTPUT);
  }

  goGreen();
  startNetwork();
  Serial.println("READY vayux-siren 2.0");
  Serial.println(netSummary());
}

// -------------------------------------------------------------- primitives
void lamps(bool r, bool y, bool g) {
  digitalWrite(PIN_RED, r);
  digitalWrite(PIN_YELLOW, y);
  digitalWrite(PIN_GREEN, g);
}

void tone_(int hz) {
  if (PASSIVE_BUZZER) {
    BUZZER_TONE(hz);
  } else {
    digitalWrite(PIN_BUZZER, hz > 0 ? HIGH : LOW);
  }
}

void silence() { tone_(0); }

void goGreen() {
  state = SEV_GREEN;
  alertUntil = 0;
  category = "";
  lamps(false, false, true);
  silence();
}

// ------------------------------------------------------------ siren shapes
// Called every loop. Each shape derives its output from millis() alone, so the
// serial port stays responsive throughout.
void updateSiren() {
  unsigned long now = millis();

  switch (state) {
    case SEV_GREEN:
      lamps(false, false, true);
      silence();
      break;

    case SEV_YELLOW: {
      lamps(false, true, false);
      // Short chirp at the top of every 3 s — present, not alarming.
      bool chirp = (now % 3000UL) < 120UL;
      tone_(chirp ? 1200 : 0);
      break;
    }

    case SEV_ORANGE: {
      if (now - lastBlink > 400) { blinkOn = !blinkOn; lastBlink = now; }
      lamps(false, blinkOn, false);
      // 1 s on, 1 s off, sweeping while on.
      unsigned long phase = now % 2000UL;
      if (phase < 1000UL) {
        int hz = SWEEP_LOW + (int)((SWEEP_HIGH - SWEEP_LOW) * (phase / 1000.0));
        tone_(hz);
      } else {
        silence();
      }
      break;
    }

    case SEV_RED: {
      if (now - lastBlink > 200) { blinkOn = !blinkOn; lastBlink = now; }
      lamps(true, false, false);
      // Continuous 1.4 s rise-and-fall wail.
      unsigned long phase = now % 1400UL;
      float t = phase / 1400.0;
      float shape = (t < 0.5) ? (t * 2.0) : (2.0 - t * 2.0);
      tone_(SWEEP_LOW + (int)((SWEEP_HIGH - SWEEP_LOW) * shape));
      break;
    }
  }
}

// ---------------------------------------------------------------- commands
Severity parseSeverity(const String &s) {
  if (s == "RED") return SEV_RED;
  if (s == "ORANGE") return SEV_ORANGE;
  if (s == "YELLOW") return SEV_YELLOW;
  return SEV_GREEN;
}

const char *severityName(Severity s) {
  switch (s) {
    case SEV_RED: return "RED";
    case SEV_ORANGE: return "ORANGE";
    case SEV_YELLOW: return "YELLOW";
    default: return "GREEN";
  }
}

void selfTest() {
  // Each lamp in turn, then a short sweep. If a lamp stays dark here it is
  // wiring, not software.
  lamps(true, false, false);  delay(300);
  lamps(false, true, false);  delay(300);
  lamps(false, false, true);  delay(300);
  for (int hz = SWEEP_LOW; hz <= SWEEP_HIGH; hz += 40) { tone_(hz); delay(8); }
  silence();
  goGreen();
}

String netSummary() {
  if (apMode) {
    return String("OK AP ") + WiFi.softAPIP().toString() + " " + AP_SSID + " -";
  }
  if (WiFi.status() == WL_CONNECTED) {
    return String("OK STA ") + WiFi.localIP().toString() + " " + WiFi.SSID() + " " +
           String(WiFi.RSSI());
  }
  return "OK OFFLINE - - -";
}

/* One parser, every transport.
 *
 * Returns the reply instead of printing it, so the HTTP handler and the serial
 * loop cannot drift apart into two subtly different command sets. `fromSerial`
 * gates the one command that must not be reachable over the network.
 */
String handle(String raw, bool fromSerial) {
  // Strip only the line ending, never spaces. Real network names have leading
  // and trailing spaces — "ARTHA 4F 2.4 GHZ " ends with one — and trimming the
  // line silently stored the wrong SSID and failed to associate with a
  // status=6 that looked like a bad password. `cmd` is the trimmed copy used
  // for matching fixed keywords; `line` keeps the payload byte-exact.
  String line = raw;
  while (line.length() && (line[line.length() - 1] == '\r' || line[line.length() - 1] == '\n')) {
    line.remove(line.length() - 1);
  }
  String cmd = line;
  cmd.trim();
  if (cmd.length() == 0) return "";
  line = cmd == line ? cmd : line;   // keep raw when it differs

  if (cmd == "PING")   return "PONG vayux-siren 2.0";
  if (cmd == "NET")    return netSummary();

  if (cmd == "STOP") {
    goGreen();
    return "OK STOP";
  }

  if (cmd == "TEST") {
    selfTest();
    return "OK TEST";
  }

  if (cmd == "STATUS") {
    long remaining = alertUntil > millis() ? (alertUntil - millis()) / 1000 : 0;
    return String("OK ") + severityName(state) + " " + String(remaining);
  }

  // Credentials are settable over the cable only. Anything already on the
  // network must not be able to move the tower to a different one.
  //
  // SSID and password are set by separate commands, each taking everything to
  // the end of the line. A single "WIFI <ssid> <pass>" cannot work: real network
  // names contain spaces ("ARTHA 4F 2.4 GHZ") and so do passphrases, so there is
  // no delimiter that splits them safely.
  if (line.startsWith("SSID ")) {
    if (!fromSerial) return "ERR SSID is serial-only";
    prefs.begin("vayux", false);
    prefs.putString("ssid", line.substring(5));
    prefs.end();
    return "OK SSID saved";
  }

  if (line.startsWith("PASS ")) {
    if (!fromSerial) return "ERR PASS is serial-only";
    prefs.begin("vayux", false);
    prefs.putString("pass", line.substring(5));
    prefs.end();
    // Deliberately does not echo the value back.
    return "OK PASS saved - send REBOOT to join";
  }

  // What the tower's own radio can see. The laptop's view is not a substitute:
  // it may be on 5 GHz, further away, or a different floor.
  if (cmd == "SCAN") {
    int n = WiFi.scanNetworks();
    String out = "OK SCAN " + String(n);
    for (int i = 0; i < n && i < 20; i++) {
      out += "\n  [" + WiFi.SSID(i) + "] rssi=" + String(WiFi.RSSI(i)) +
             " ch=" + String(WiFi.channel(i)) +
             " enc=" + String((int)WiFi.encryptionType(i));
    }
    return out;   // results kept so PICK can use them
  }

  // Take the SSID straight from the scan by index. Nothing is retyped, so an
  // invisible trailing space cannot be lost in transcription.
  if (cmd.startsWith("PICK ")) {
    if (!fromSerial) return "ERR PICK is serial-only";
    int idx = cmd.substring(5).toInt();
    String found = WiFi.SSID(idx);
    if (found.length() == 0) return "ERR no such scan index - run SCAN first";
    prefs.begin("vayux", false);
    prefs.putString("ssid", found);
    prefs.end();
    return "OK SSID saved [" + found + "] len=" + String(found.length());
  }

  if (cmd == "WHY") {
    return String("OK status=") + String((int)WiFi.status()) +
           " (3=connected 1=no-ssid 4=auth-fail 6=disconnected)";
  }

  if (cmd == "RETRY") {
    if (!fromSerial) return "ERR RETRY is serial-only";
    startNetwork();
    return netSummary();
  }

  if (cmd == "REBOOT") {
    if (!fromSerial) return "ERR REBOOT is serial-only";
    Serial.println("OK REBOOT");
    Serial.flush();
    delay(120);
    ESP.restart();
  }

  if (cmd == "WIFICLEAR") {
    if (!fromSerial) return "ERR WIFICLEAR is serial-only";
    prefs.begin("vayux", false);
    prefs.clear();
    prefs.end();
    return "OK WIFI cleared";
  }

  if (cmd.startsWith("ALERT")) {
    // ALERT <SEV> <CAT> <SECS>
    int s1 = cmd.indexOf(' ');
    int s2 = cmd.indexOf(' ', s1 + 1);
    int s3 = cmd.indexOf(' ', s2 + 1);
    if (s1 < 0 || s2 < 0 || s3 < 0) return "ERR malformed ALERT";

    String sev = cmd.substring(s1 + 1, s2);
    category   = cmd.substring(s2 + 1, s3);
    long secs  = cmd.substring(s3 + 1).toInt();
    if (secs <= 0) return "ERR bad duration";

    unsigned long ms = (unsigned long)secs * 1000UL;
    if (ms > MAX_ALERT_MS) ms = MAX_ALERT_MS;

    state = parseSeverity(sev);
    alertUntil = millis() + ms;
    lastBlink = millis();
    return String("OK ALERT ") + severityName(state) + " " + String((long)(ms / 1000));
  }

  return "ERR unknown command";
}

// ----------------------------------------------------------------- network
void startHttp() {
  auto run = [](const String &cmd) {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "text/plain", handle(cmd, false) + "\n");
  };

  server.on("/cmd", [run]() { run(server.arg("q")); });
  server.on("/ping", [run]() { run("PING"); });
  server.on("/status", [run]() { run("STATUS"); });
  server.on("/test", [run]() { run("TEST"); });
  server.on("/stop", [run]() { run("STOP"); });
  server.on("/net", [run]() { run("NET"); });
  server.on("/alert", [run]() {
    run("ALERT " + server.arg("sev") + " " +
        (server.arg("cat").length() ? server.arg("cat") : String("MANUAL")) + " " +
        (server.arg("secs").length() ? server.arg("secs") : String("10")));
  });
  // A human landing on the bare address should get something useful, not a 404.
  server.onNotFound([]() {
    server.send(200, "text/plain",
                "Vayu-X siren tower 2.0\n"
                "  /ping  /status  /test  /stop  /net\n"
                "  /alert?sev=RED&cat=ESCS&secs=15\n"
                "  /cmd?q=<command>\n");
  });
  server.begin();
}

void startNetwork() {
  prefs.begin("vayux", true);
  String ssid = prefs.getString("ssid", "");
  String pass = prefs.getString("pass", "");
  prefs.end();

  if (ssid.length()) {
    Serial.printf("WIFI joining %s\n", ssid.c_str());
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid.c_str(), pass.c_str());
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < STA_TIMEOUT_MS) {
      delay(250);
    }
  }

  if (WiFi.status() == WL_CONNECTED) {
    apMode = false;
    Serial.printf("WIFI ok ip=%s rssi=%d\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
  } else {
    if (ssid.length()) {
      Serial.printf("WIFI join failed status=%d (1=no-ssid 4=auth-fail 6=disconnected)\n",
                    (int)WiFi.status());
    }
    // No credentials, or the network is not there. Become the network instead:
    // a tower that only works where somebody else's infrastructure survives is
    // not much of a last-mile tower.
    apMode = true;
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASS);
    Serial.printf("WIFI ap ssid=%s ip=%s\n", AP_SSID, WiFi.softAPIP().toString().c_str());
  }

  if (MDNS.begin(MDNS_NAME)) {
    MDNS.addService("http", "tcp", 80);
    Serial.printf("MDNS %s.local\n", MDNS_NAME);
  }

  ArduinoOTA.setHostname(MDNS_NAME);
  ArduinoOTA.onStart([]() {
    // Never leave a siren sounding through a firmware update.
    goGreen();
    Serial.println("OTA start");
  });
  ArduinoOTA.begin();

  startHttp();
}

// -------------------------------------------------------------------- loop
void loop() {
  server.handleClient();
  ArduinoOTA.handle();

  while (Serial.available()) {
    String reply = handle(Serial.readStringUntil('\n'), true);
    if (reply.length()) Serial.println(reply);
  }

  // Autonomous fallback. If the tower is shaken hard while no alert is active,
  // raise a local YELLOW without being told to. This is what makes it a tower
  // and not a lamp on a wire: it still does something useful when the link to
  // the control room is gone, which during a cyclone is the likely case.
  if (state == SEV_GREEN && digitalRead(PIN_SENSOR) == HIGH) {
    state = SEV_YELLOW;
    category = "LOCAL";
    alertUntil = millis() + 5000UL;
    Serial.println("EVENT local-sensor YELLOW");
  }

  if (alertUntil > 0 && millis() > alertUntil) {
    goGreen();
    Serial.println("EVENT all-clear");
  }

  updateSiren();
}

/*
 * ------------------------------------------------------------------ LORA
 * To make this a real no-coverage tower, add an SX1278 (RA-02, 433 MHz) and
 * replace the Serial reads in loop() with LoRa.parsePacket(). The command
 * strings do not change, which is the point of keeping them plain text — the
 * laptop-side code in alert-system/src/siren_device.py works either way, with
 * the gateway radio on the laptop's USB instead of the tower.
 *
 * Realistic range on flat coast: 5-10 km line of sight with a half-wave whip,
 * more from a mast. That covers the gap between a district control room and
 * the villages that lose cell service first.
 */
