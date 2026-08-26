#include "heater.h"

#include <Arduino.h>

#include "pins.h"

HeaterState currentState = heatOff;
float targTemp = 0;
int lastHeaterPower = 0;

void heaterSetup() {
  if (!ledcSetup(0, 25000, 8)) { // ch0: 25khz, 8 bit
    Serial.println("Heater pin channel setup failed!");
  } else {
    ledcWrite(0, 0); // set initial ch0 output to 0
    ledcAttachPin(HEAT_DRIVE_PIN, 0);
    Serial.println("Heater setup");
  }
}

void heaterPower(int power) {
  ledcWrite(0, power);
  lastHeaterPower = power;
}

void bangBang(float currentTemp, float hyst) {
  if (currentState == heatOff) {
    heaterPower(0);
    return;
  }
  if (currentState == heatOn) {
    if ((targTemp - hyst) > currentTemp) {
      heaterPower(240);
    } else {
      heaterPower(0);
    }
  }
}
