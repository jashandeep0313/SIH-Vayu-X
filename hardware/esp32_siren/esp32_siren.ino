/*
 * Vayu-X last-mile siren tower — ESP32 firmware
 * SIH PS 26070 · Team Vayu-X (152)
 *
 * A coastal warning that depends on the cellular network fails exactly where it
 * matters. This is the part that does not: a microcontroller driving a lamp
 * stack and a piezo siren, taking commands over a serial link.
 *
 * In the demo that link is USB to the analyst's laptop. In a deployment it is
 * LoRa at 433 MHz — same protocol, different transport (see LORA note below).
 *
 * -------------------------------------------------------------- protocol
 * Line-based ASCII, 115200 baud. Human-readable on purpose: you can drive the
 * whole tower from a serial monitor when something is wrong at 2 a.m.
 *
 *   PING                        -> PONG vayux-siren 1.0
 *   ALERT <SEV> <CAT> <SECS>    -> OK ALERT <SEV> <SECS>
 *   STOP                        -> OK STOP
 *   TEST                        -> OK TEST
 *   STATUS                      -> OK <state> <secs_remaining>
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
  Serial.println("READY vayux-siren 1.0");
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

void handle(String line) {
  line.trim();
  if (line.length() == 0) return;

  if (line == "PING") {
    Serial.println("PONG vayux-siren 1.0");
    return;
  }

  if (line == "STOP") {
    goGreen();
    Serial.println("OK STOP");
    return;
  }

  if (line == "TEST") {
    selfTest();
    Serial.println("OK TEST");
    return;
  }

  if (line == "STATUS") {
    long remaining = alertUntil > millis() ? (alertUntil - millis()) / 1000 : 0;
    Serial.printf("OK %s %ld\n", severityName(state), remaining);
    return;
  }

  if (line.startsWith("ALERT")) {
    // ALERT <SEV> <CAT> <SECS>
    int s1 = line.indexOf(' ');
    int s2 = line.indexOf(' ', s1 + 1);
    int s3 = line.indexOf(' ', s2 + 1);
    if (s1 < 0 || s2 < 0 || s3 < 0) { Serial.println("ERR malformed ALERT"); return; }

    String sev = line.substring(s1 + 1, s2);
    category   = line.substring(s2 + 1, s3);
    long secs  = line.substring(s3 + 1).toInt();
    if (secs <= 0) { Serial.println("ERR bad duration"); return; }

    unsigned long ms = (unsigned long)secs * 1000UL;
    if (ms > MAX_ALERT_MS) ms = MAX_ALERT_MS;

    state = parseSeverity(sev);
    alertUntil = millis() + ms;
    lastBlink = millis();
    Serial.printf("OK ALERT %s %ld\n", severityName(state), (long)(ms / 1000));
    return;
  }

  Serial.println("ERR unknown command");
}

// -------------------------------------------------------------------- loop
void loop() {
  while (Serial.available()) {
    handle(Serial.readStringUntil('\n'));
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
