#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_MCP23X17.h>
#include <Wire.h>
#include <MCP3X21.h>
#include <OneWire.h>
#include <DallasTemperature.h>


#define SCREEN_WD 128
#define SCREEN_HT 32

#define OLED_RESET -1

Adafruit_SSD1306 display(SCREEN_WD, SCREEN_HT, &Wire, OLED_RESET);
Adafruit_MCP23X17 mcp;
MCP3021 mcp3021(0x49);


#define SDA_PIN D4
#define SLC_PIN D5

#define SEL_A_PIN A3
#define SEL_B_PIN A2
#define INT_PIN D9
#define HEATER_PIN A0
#define OW_BUS_PIN A1

#define DIV_MODE_1k 0
#define DIV_MODE_10k 1
#define DIV_MODE_100k 2


OneWire  TcBus(OW_BUS_PIN);  // on pin A1
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

void getTemp()//get the temperature, return it in float degrees c.
{
  int result;
  delay(10);
  Tc.requestTemperatures();
  float tempC = Tc.getTempC(TcAddress);
  Serial.print("temp tc, ");
  Serial.print(tempC);
  set_divider(DIV_MODE_1k);
  Serial.print(",1k , ");
  result = mcp3021.read();
  Serial.print(result);
  delay(10);
  set_divider(DIV_MODE_10k);
  Serial.print(",10k, ");
  result = mcp3021.read();
  Serial.print(result);
  delay(10);
  set_divider(DIV_MODE_100k);
  Serial.print(",100k, ");
  result = mcp3021.read();
  Serial.println(result);
  delay(10);
}

const uint16_t ref_voltage = 3300;  // in mV



float targTemp=0;       //target temperature
enum state {heatOff, heatOn};
state currentState = heatOff;


void setupHeater()
{
  if(!ledcSetup(0, 25000, 8))// ch0: 25khz, 8 bit
  {
    Serial.println("Heater pin channel setup failed!");
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
//  Serial.print("Heater set to: ");
//  Serial.println(power);
}

void set_divider(int mode){
  if(mode == DIV_MODE_1k)
  {
    digitalWrite(SEL_A_PIN,1);
    digitalWrite(SEL_B_PIN,1);
  }
  if(mode == DIV_MODE_10k)
  {
    digitalWrite(SEL_A_PIN,0);
    digitalWrite(SEL_B_PIN,1);
  }
  if(mode == DIV_MODE_100k)
  {
    digitalWrite(SEL_A_PIN,1);
    digitalWrite(SEL_B_PIN,0);
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("Hotplate Booted:");

  pinMode(SEL_A_PIN, OUTPUT);
  pinMode(SEL_B_PIN, OUTPUT);
  set_divider(DIV_MODE_1k);
  Serial.println("set div mode 1k");
  

  // SSD1306_SWITCHCAPVCC = generate display voltage from 3.3V internally
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { // Address 0x3C for 128x32
    Serial.println(F("SSD1306 allocation failed"));
    for(;;); // Don't proceed, loop forever
  }
  Serial.println("screen begin");

  display.clearDisplay();
  display.setTextSize(3);             
  display.setTextColor(SSD1306_WHITE);
  display.setRotation(2);
  display.setCursor(0,0);
  display.print(" PDHP!");
  display.display();
  display.setTextSize(1);           
  delay(1000);

  mcp3021.init();
  Serial.println("mcp adc init...done");

  if(tempSensorStart()){
    Serial.print("Sensor found, temp is: ");

  }
  else{
    Serial.print("Sensor NOT found, halting");
    while(1)
    {
    }
  }

  setupHeater();
}

void displayTask(float temp){
  display.clearDisplay();
  display.setCursor(0,0);
  display.print("Targ ");
  display.printf("%3.0f\n",targTemp);
  display.print("Curr ");
  display.printf("%3.0f\n",temp);
  display.print("mode ");
  if(currentState == heatOff)
  {
    display.printf("OFF");  
  }
  if(currentState == heatOn)
  {
    display.printf("HEAT");  
  }
  display.display();
}

void loop(void) {
  heaterPower(220);
  while(1){
  getTemp();
  delay(1000);
  }
}
