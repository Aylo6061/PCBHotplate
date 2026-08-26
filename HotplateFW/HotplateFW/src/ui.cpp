#include "ui.h"

#include <Adafruit_GFX.h>
#include <Adafruit_MCP23X17.h>
#include <Adafruit_SSD1306.h>
#include <Arduino.h>
#include <Wire.h>

#include "heater.h"
#include "pins.h"

namespace {

Adafruit_SSD1306 display(SCREEN_WD, SCREEN_HT, &Wire, OLED_RESET);
Adafruit_MCP23X17 mcp;

unsigned long timeWas = 0;

// Lists every address that acks on the I2C bus, to make a missing/misaddressed
// device (OLED, MCP23X17, MCP3021) obvious over serial instead of a silent hang.
void scanI2CBus() {
  Serial.println("Scanning I2C bus...");
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.print("  found device at 0x");
      Serial.println(addr, HEX);
    }
  }
}

} // namespace

void uiSetup() {
  Wire.begin();

  // SSD1306_SWITCHCAPVCC = generate display voltage from 3.3V internally
  while (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { // Address 0x3C for 128x32
    Serial.println(F("SSD1306 not found at 0x3C, retrying..."));
    scanI2CBus();
    delay(1000);
  }
  Serial.println("screen begin");

  display.clearDisplay();
  display.setTextSize(3);
  display.setTextColor(SSD1306_WHITE);
  display.setRotation(2);
  display.setCursor(0, 0);
  display.print(" PDHP!");
  display.display();
  display.setTextSize(1);
  delay(1000);

  while (!mcp.begin_I2C()) {
    Serial.println("MCP23X17 not found, retrying...");
    scanI2CBus();
    delay(1000);
  }
  Serial.println("mcp exp init...done");

  mcp.setupInterrupts(true, false, LOW); // mirror interrupts

  // configure button pins for input with pull up
  mcp.pinMode(BUTTON_PIN_MODE, INPUT_PULLUP);
  mcp.pinMode(BUTTON_PIN_DEC, INPUT_PULLUP);
  mcp.pinMode(BUTTON_PIN_INC, INPUT_PULLUP);
  mcp.pinMode(BUTTON_PIN_RUN, INPUT_PULLUP);

  // enable interrupt on each button pin
  mcp.setupInterruptPin(BUTTON_PIN_MODE, LOW);
  mcp.setupInterruptPin(BUTTON_PIN_DEC, LOW);
  mcp.setupInterruptPin(BUTTON_PIN_INC, LOW);
  mcp.setupInterruptPin(BUTTON_PIN_RUN, LOW);
}

void checkInputs() {
  unsigned long timeNow = millis();
  if (timeNow - timeWas < 200) {
    return;
  }
  timeWas = timeNow;

  int button = mcp.getLastInterruptPin();
  mcp.clearInterrupts();

  switch (button) {
    case 255:
      break;
    case BUTTON_PIN_MODE: // toggle mode, but only once the button is released
      // The MCP23X17 interrupt condition is level-based (button held == pin
      // still LOW, diverging from DEFVAL), so it keeps re-firing on every
      // poll for as long as the button is held. Only act once the pin has
      // actually returned HIGH (released), so a hold produces one toggle.
      if (mcp.digitalRead(BUTTON_PIN_MODE) != HIGH) {
        break;
      }
      if (currentState == heatOff) {
        currentState = heatOn;
      } else if (currentState == heatOn) {
        currentState = heatOff;
      }
      Serial.print("event=MODE state=");
      Serial.println(currentState == heatOn ? "HEAT" : "OFF");
      break;
    case BUTTON_PIN_DEC: // dec temp
      if (targTemp >= 5) {
        targTemp -= 5;
      }
      Serial.print("event=DEC targTemp=");
      Serial.println(targTemp);
      break;
    case BUTTON_PIN_INC: // inc temp
      if (targTemp < 200) {
        targTemp += 5;
      }
      Serial.print("event=INC targTemp=");
      Serial.println(targTemp);
      break;
    case BUTTON_PIN_RUN: // nothing!
      Serial.println("event=RUN");
      break;
  }
}

void displayTask(float temp) {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.print("Targ ");
  display.printf("%3.0f\n", targTemp);
  display.print("Curr ");
  display.printf("%3.0f\n", temp);
  display.print("mode ");
  if (currentState == heatOff) {
    display.printf("OFF");
  }
  if (currentState == heatOn) {
    display.printf("HEAT");
  }
  display.display();
}
