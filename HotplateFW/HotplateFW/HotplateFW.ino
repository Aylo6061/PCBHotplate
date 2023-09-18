#include <OneWire.h>
#include <DallasTemperature.h>
#include <AceButton.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WD 128
#define SCREEN_HT 32

#define OLED_RESET -1

Adafruit_SSD1306 display(SCREEN_WD, SCREEN_HT, &Wire, OLED_RESET);

using namespace ace_button;

#define OW_BUS_PIN D3
#define HEATER_PIN D0
#define LED_RUN D10
#define LED_HOT A1

#define INC_PIN  D7
#define DEC_PIN  D8
#define STOP_GO  D6
#define PROG_MAN D9

ButtonConfig buttonConfig_STOP_GO;
ButtonConfig buttonConfig_INC;
ButtonConfig buttonConfig_DEC;

AceButton button_STOP_GO(& buttonConfig_STOP_GO);
AceButton button_DEC(& buttonConfig_INC);
AceButton button_INC(& buttonConfig_DEC);

void handleEvent_STOP_GO(AceButton*, uint8_t, uint8_t);
void handleEvent_DEC(AceButton*, uint8_t, uint8_t);
void handleEvent_INC(AceButton*, uint8_t, uint8_t);

OneWire  TcBus(OW_BUS_PIN);  // on pin 0, AKA A3
DallasTemperature Tc(&TcBus);
DeviceAddress TcAddress;

// function to print a device address
void printAddress(DeviceAddress deviceAddress)
{
  for (uint8_t i = 0; i < 8; i++)
  {
    if (deviceAddress[i] < 16) Serial.print("0");
    Serial.print(deviceAddress[i], HEX);
  }
}

bool tempSensorStart()//startup code for temp sensor
{
  if(TcBus.search(TcAddress))
  {
    Serial.print("Address found: ");
    printAddress(TcAddress);
    Tc.setResolution(TcAddress, 9);
  return 1;
  }
  else{
    return 0;
  }
}

float getTemp()//get the temperature, return it in float degrees c.
{
  Tc.requestTemperatures();
  float tempC = Tc.getTempC(TcAddress);
  return tempC;
}

void terminalErrorBlink()
{
  pinMode(D1, OUTPUT);
  while(1){
      digitalWrite(D1, HIGH);   // turn the LED on 
      delay(200);               // wait for a second
      digitalWrite(D1, LOW);    // turn the LED off
      delay(500);               // wait for a second
      Serial.println("error");
  }
}

void happyBlink()
{
  pinMode(D10, OUTPUT);
  while(1){
      digitalWrite(D10, HIGH);   // turn the LED on 
      delay(200);               // wait for a second
      digitalWrite(D10, LOW);    // turn the LED off
      delay(200);               // wait for a second
      Serial.println(getTemp());
  }
  
}

void setupHeater()
{
  if(!ledcSetup(0, 25000, 8))// ch0: 25khz, 8 bit
  {
    Serial.println("Heater pin channel setup failed!");
    terminalErrorBlink();
  }
  else{
    ledcWrite(0, 0); // set initial ch0 output to 0
    ledcAttachPin(HEATER_PIN, 0);
    Serial.println("Heater setup");
  }
}

void heaterPower(int power)
{
  ledcWrite(0, power);
  Serial.print("Heater set to: ");
  Serial.println(power);
}

void bangBang(float target, float currentTemp, float hyst)
{
  if((target- hyst)> currentTemp){
    heaterPower(200);
  }
  else{
    heaterPower(0);
  }
}

void setup() {
  delay(1000);
  Serial.begin(115200);
  Serial.println("Hotplate Booted:");

  // SSD1306_SWITCHCAPVCC = generate display voltage from 3.3V internally
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { // Address 0x3C for 128x32
    Serial.println(F("SSD1306 allocation failed"));
    for(;;); // Don't proceed, loop forever
  }

  display.clearDisplay();
  display.setTextSize(3);             
  display.setTextColor(SSD1306_WHITE);
  display.setRotation(0);
  display.setCursor(0,0);
  display.print(" PDHP!");
  display.display();
  delay(1000);


  
  if(tempSensorStart()){
    Serial.print("Sensor found, temp is: ");
    Serial.println(getTemp());
  }
  else{
    Serial.print("Sensor NOT found, halting");
    while(1)
    {
      terminalErrorBlink();
    }
  }

  button_STOP_GO.init(STOP_GO);
  pinMode(STOP_GO, INPUT_PULLUP);
  buttonConfig_STOP_GO.setEventHandler(handleEvent_STOP_GO);
  buttonConfig_STOP_GO.setFeature(ButtonConfig::kFeatureClick);

  button_DEC.init(DEC_PIN);
  pinMode(DEC_PIN, INPUT_PULLUP);
  buttonConfig_DEC.setEventHandler(handleEvent_DEC);
  buttonConfig_DEC.setFeature(ButtonConfig::kFeatureClick);

  button_INC.init(INC_PIN);
  pinMode(INC_PIN, INPUT_PULLUP);
  buttonConfig_INC.setEventHandler(handleEvent_INC);
  buttonConfig_INC.setFeature(ButtonConfig::kFeatureClick);

  pinMode(LED_RUN, OUTPUT);
  pinMode(LED_HOT, OUTPUT);
  setupHeater();
}

float targTemp=0;       //target temperature
bool heatEnabled=0; //heatEnabled = 1 heat up
bool progMode;    //progMode = 1 program mode

void loop(void) {
  float tempNow;
  tempNow = getTemp();
  heaterPower(0);
    
  while(1){
    tempNow = getTemp();
    
    button_STOP_GO.check();
    button_INC.check();
    button_DEC.check();
    if(heatEnabled)
    {
    digitalWrite(LED_RUN, 1);
    bangBang(targTemp, tempNow, .5);
    Serial.print("Temp is: ");
    Serial.print(tempNow);
    Serial.print(" Target temp is: ");
    Serial.print(targTemp);
    }
    else
    {
      digitalWrite(LED_RUN,0);
      bangBang(0, tempNow, .5);
      Serial.print("Temp is: ");
      Serial.print(tempNow);
      Serial.print(" Target temp is: ");
      Serial.print(targTemp);
    }
    if(tempNow>50)
    {
      digitalWrite(LED_HOT, 1);
    }
    else
    {
      digitalWrite(LED_HOT,0);
    }
  display.clearDisplay();
  display.setTextSize(2);             
  display.setTextColor(SSD1306_WHITE);
  display.setRotation(0);
  display.setCursor(0,0);
  display.print("Targ ");
  display.printf("%3.0f\n",targTemp);
  display.print("Curr ");
  display.printf("%3.0f",tempNow);
  display.display();
  }
}

void handleEvent_STOP_GO(AceButton* button, uint8_t eventType, uint8_t buttonState)
{
  switch(eventType){
    case AceButton::kEventPressed:
      Serial.println("stopgo");
      heatEnabled = !heatEnabled;
      break;
  }
}

void handleEvent_DEC(AceButton* button, uint8_t eventType, uint8_t buttonState)
{
  switch(eventType){
    case AceButton::kEventPressed:
      Serial.println("dec!");
      if(targTemp-10>=0)
      {
        targTemp-=10;
      }
      break;
  }
}

void handleEvent_INC(AceButton* button, uint8_t eventType, uint8_t buttonState)
{
  switch(eventType){
    case AceButton::kEventPressed:
      Serial.println("inc!");
      if(targTemp+10<=240)
      {
        targTemp+=10;
      }
      break;
  }
}
