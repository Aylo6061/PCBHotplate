#include <OneWire.h>
#include <DallasTemperature.h>

#define OW_BUS_PIN D3

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

void setup() {
  delay(1000);
  Serial.begin(9600);
  Serial.println("Hotplate Booted:");
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

}

void loop(void) {
  happyBlink();
}
