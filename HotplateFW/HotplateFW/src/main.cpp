#include <Arduino.h>

#include "heater.h"
#include "temp_sense.h"
#include "ui.h"

namespace {

unsigned long lastDebugPrint = 0;

void debugPrintStatus(float temp) {
  unsigned long now = millis();
  if (now - lastDebugPrint < 1000) {
    return;
  }
  lastDebugPrint = now;

  Serial.print("temp=");
  Serial.print(temp);
  Serial.print("C state=");
  Serial.print(currentState == heatOn ? "HEAT" : "OFF");
  Serial.print(" heater=");
  Serial.print(heaterIsOn ? "ON" : "OFF");
  Serial.print(" adcVoltage=");
  Serial.print(lastAdcVoltage);
  Serial.print("V adcTicks=");
  Serial.println(lastAdcCode);
}

} // namespace

void setup() {
  Serial.begin(115200);
  Serial.println("Hotplate Booted:");

  uiSetup();
  tempSenseSetup();
  heaterSetup();
}

void loop() {
  float tempNow = getTemp();
  setHeater(false);
  Serial.println("entering main loop...");

  while (1) {
    checkInputs();
    tempNow = getTemp();
    displayTask(tempNow);
    bangBang(tempNow, 5);
    debugPrintStatus(tempNow);
  }
}
