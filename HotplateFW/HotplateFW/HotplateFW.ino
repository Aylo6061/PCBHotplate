#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_MCP23X17.h>
#include <Wire.h>
#include <MCP3X21.h>


#define SCREEN_WD 128
#define SCREEN_HT 32

#define OLED_RESET -1

Adafruit_SSD1306 display(SCREEN_WD, SCREEN_HT, &Wire, OLED_RESET);
Adafruit_MCP23X17 mcp;


#define SDA_PIN D4
#define SLC_PIN D5

#define SEL_A_PIN A3
#define SEL_B_PIN A2
#define INT_PIN D9
#define HEATER_PIN A0

#define DIV_MODE_1k 0
#define DIV_MODE_10k 1
#define DIV_MODE_100k 2

#define BUTTON_PIN_MODE 0   // MCP23XXX pin used for interrupt
#define BUTTON_PIN_DEC 1   // MCP23XXX pin used for interrupt
#define BUTTON_PIN_INC 2   // MCP23XXX pin used for interrupt
#define BUTTON_PIN_RUN 3   // MCP23XXX pin used for interrupt



#define ADC_CUTOFF_VAL_1k 254 //below this adc value, use 10k res div

#define L_1k       852.09
#define X_zero_1k  144.86
#define K_1k         0.0287
#define OFF_1k     -19.57

#define L_10k      1173.59
#define X_zero_10k 69.93
#define K_10k       0.0290
#define OFF_10k   -176.13

MCP3021 mcp3021(0x49);

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
  Serial.print("Heater set to: ");
  Serial.println(power);
}

void bangBang(float currentTemp, float hyst)
{
  if(currentState == heatOff)
  {
    heaterPower(0);
    return;
  }
  if(currentState == heatOn)
  {
  if((targTemp- hyst)> currentTemp){
    heaterPower(240);
  }
  else{
    heaterPower(0);
  }
  }
  return;
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

    if (!mcp.begin_I2C()) {
    Serial.println("Error.");
    while (1);
  }
  Serial.println("mcp exp init...done");

  mcp3021.init();
  Serial.println("mcp adc init...done");
  
//  pinMode(INT_PIN, INPUT_PULLUP);
  mcp.setupInterrupts(true, false, LOW);//mirror interrupts

  // configure button pin for input with pull up
  mcp.pinMode(BUTTON_PIN_MODE, INPUT_PULLUP);
  mcp.pinMode(BUTTON_PIN_DEC, INPUT_PULLUP);
  mcp.pinMode(BUTTON_PIN_INC, INPUT_PULLUP);
  mcp.pinMode(BUTTON_PIN_RUN, INPUT_PULLUP);

  // enable interrupt on button_pin
  mcp.setupInterruptPin(BUTTON_PIN_MODE, LOW);
  mcp.setupInterruptPin(BUTTON_PIN_DEC, LOW);
  mcp.setupInterruptPin(BUTTON_PIN_INC, LOW);
  mcp.setupInterruptPin(BUTTON_PIN_RUN, LOW);
//  attachInterrupt(INT_PIN, mcp_int, FALLING);
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

unsigned long timeWas;

void checkInputs(){
  unsigned long timeNow=millis();
  if(timeNow-timeWas >=200)
  {
    timeWas = timeNow;
  int button = mcp.getLastInterruptPin();
  mcp.clearInterrupts();
  Serial.print("button ");
  Serial.println(button);
  switch(button)
  {
    case 255:
      break;
    case 0: //toggle mode
      if (currentState == heatOff){
        currentState = heatOn;
        Serial.println("heatOn");
        break;
      }
      if (currentState == heatOn){
        currentState = heatOff;
        Serial.println("heatOff");
        break;
      }
      break;
      
    case 1: //dec temp
      if(targTemp>=5){
        targTemp-=5;
      }
      break;
    case 2: //inc temp
      if(targTemp<200){
        targTemp+=5;
      }
      break;
    case 3: //nothing!
      break;
  }
  }
}

float runConversion( int adcval, float L, float xnought, float k, float off)
{
  float ret;
  ret = (xnought*k-log((-1*(L+off-adcval))/(off-adcval)))/k;
  return ret;
}

float getTemp(){
  float ret;
  int result;
  //read 1k
  set_divider(DIV_MODE_1k);
  result = mcp3021.read();
  if(result>ADC_CUTOFF_VAL_1k)
  {
    ret = runConversion(result, L_1k,  X_zero_1k, K_1k, OFF_1k);
    return ret;
  }
  set_divider(DIV_MODE_10k);
  result = mcp3021.read();
  ret = runConversion(result, L_10k,  X_zero_10k, K_10k, OFF_10k);
  return ret;
}

void loop(void) {
  
  float tempNow;
  tempNow = getTemp();
  heaterPower(0);
  timeWas = millis();
  Serial.println("entering main loop...");
    
  while(1){
    checkInputs();
    tempNow = getTemp();
    displayTask(tempNow);
    bangBang(tempNow, 5);
  }
}
