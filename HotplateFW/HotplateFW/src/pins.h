#pragma once

// Seeed XIAO ESP32-C3 default Wire() pins (SDA=D4/GPIO6, SCL=D5/GPIO7) are
// used as-is for the shared bus: OLED, MCP23017 button expander, MCP3021 ADC.

#define HEAT_DRIVE_PIN A0

#define BUTTON_PIN_MODE 0 // MCP23X17 pin
#define BUTTON_PIN_DEC  1 // MCP23X17 pin
#define BUTTON_PIN_INC  2 // MCP23X17 pin
#define BUTTON_PIN_RUN  3 // MCP23X17 pin

#define SCREEN_WD 128
#define SCREEN_HT 32
#define OLED_RESET -1

#define MCP3021_ADDR 0x49
