#include "heater.h"

#include <Arduino.h>

#include "pins.h"

HeaterState currentState = heatOff;
float targTemp = 0;
bool heaterIsOn = false;

namespace {

constexpr unsigned long MIN_OFF_TIME_MS = 100; // heater must stay off this long before turning back on

unsigned long lastOffTime = 0; // millis() when the heater last went from on to off

} // namespace

void heaterSetup() {
  // Plain on/off enable into the constant-current buck's EN pin; the buck
  // regulates heater current, so no PWM is needed (or wanted on EN/SYNC).
  digitalWrite(HEAT_DRIVE_PIN, LOW);
  pinMode(HEAT_DRIVE_PIN, OUTPUT);
  Serial.println("Heater setup");
}

void setHeater(bool on) {
  if (!on && heaterIsOn) {
    lastOffTime = millis();
  }
  digitalWrite(HEAT_DRIVE_PIN, on ? HIGH : LOW);
  heaterIsOn = on;
}

void bangBang(float currentTemp, float hyst) {
  if (currentState == heatOff) {
    setHeater(false);
    return;
  }
  if (currentState == heatOn) {
    if ((targTemp - hyst) > currentTemp) {
      // Only gates turning on; once on, the heater stays on as long as needed.
      if (!heaterIsOn && millis() - lastOffTime < MIN_OFF_TIME_MS) {
        return;
      }
      setHeater(true);
    } else {
      setHeater(false);
    }
  }
}
