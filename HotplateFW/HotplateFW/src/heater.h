#pragma once

enum HeaterState { heatOff, heatOn };

extern HeaterState currentState;
extern float targTemp; // target temperature
extern bool heaterIsOn; // current state of the heater drive pin

void heaterSetup();
void setHeater(bool on);
void bangBang(float currentTemp, float hyst);
