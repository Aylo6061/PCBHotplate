#pragma once

#include <stdint.h>

void tempSenseSetup();
float getTemp();

// Raw ADC code and derived op-amp output voltage from the last getTemp() call.
extern uint16_t lastAdcCode;
extern float lastAdcVoltage;
