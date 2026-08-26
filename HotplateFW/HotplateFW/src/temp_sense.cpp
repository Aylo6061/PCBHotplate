#include "temp_sense.h"

#include <Arduino.h>
#include <math.h>
#include <Wire.h>
#include <MCP3X21.h>

#include "pins.h"

namespace {

MCP3021 mcp3021(MCP3021_ADDR);

// PT1000 (p/n 30200145), IEC 60751 Callendar-Van Dusen coefficients (T >= 0C).
constexpr float PT1000_R0 = 1000.0f; // ohms at 0C
constexpr float PT1000_A = 3.9083e-3f;
constexpr float PT1000_B = -5.775e-7f;

constexpr float EXCITATION_CURRENT_A = 0.001f; // 1mA constant current source into the RTD

// Op-amp maps V_rtd linearly onto its output span; endpoints correspond to
// ~20C and ~250C on the PT1000 curve, so this is not a simple offset+gain.
constexpr float RTD_V_MIN = 1.078f;
constexpr float RTD_V_MAX = 1.941f;
constexpr float OPAMP_V_MIN = 0.3f;
constexpr float OPAMP_V_MAX = 3.0f;

constexpr uint16_t ADC_VREF_MV = 3300;

float resistanceToTempC(float resistanceOhms) {
  float z1 = -PT1000_A;
  float z2 = PT1000_A * PT1000_A - 4.0f * PT1000_B;
  float z3 = (4.0f * PT1000_B) / PT1000_R0;
  float z4 = 2.0f * PT1000_B;
  float temp = z2 + z3 * resistanceOhms;
  temp = (sqrtf(temp) + z1) / z4;
  return temp;
}

} // namespace

uint16_t lastAdcCode = 0;
float lastAdcVoltage = 0;

void tempSenseSetup() {
  mcp3021.init();
  Serial.println("mcp adc init...done");
}

float getTemp() {
  lastAdcCode = mcp3021.read();
  lastAdcVoltage = mcp3021.toVoltage(lastAdcCode, ADC_VREF_MV) / 1000.0f;
  float vRtd = RTD_V_MIN + (lastAdcVoltage - OPAMP_V_MIN) / (OPAMP_V_MAX - OPAMP_V_MIN) * (RTD_V_MAX - RTD_V_MIN);
  float resistanceOhms = vRtd / EXCITATION_CURRENT_A;
  return resistanceToTempC(resistanceOhms);
}
