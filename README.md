# PCBHotplate
A USB C powered PCB-based hotplate, with separable heater elements.

There are several PCB-project directories, HPcontroller contains the controller, while HPheater contains the heater.

# Inputs and Indicators
D_PD_POW indicates PD power is on
D_3v3_POW indicated 3v3 power is on
D_HOT indicates the plate is hot! dont touch!
D_HB is dicates that data is being sent or received on the serial port
D_MODE indicates the program mode is ON
D_RUN indicates the program or heater is running
D_HEAT indicates the heater is on
D_RTD indicates the RTD protection is tripped

# Bom (rough)

flyback diode - at least 25V Vr, capable of ~5A average current (overkill).  STR8100LBF would work.
capacitor- at least 25-30V probably like 100uF?  depends on switching frequency.
fet driver NCP81071B
Fet AOSD32334C dual nfet
non inverting buffer SN74HCS125PWR

# TODO

-add power supply (use whatever is in lamp?)
-add i2c temp sensor breakout
-add display (use some old i2c oled I have)