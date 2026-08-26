#pragma once

enum HeaterState { heatOff, heatOn };

extern HeaterState currentState;
extern float targTemp; // target temperature
extern int lastHeaterPower; // last power value passed to heaterPower()

void heaterSetup();
void heaterPower(int power);
void bangBang(float currentTemp, float hyst);
