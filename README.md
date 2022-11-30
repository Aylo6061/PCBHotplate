# PCBHotplate
A USB C powered PCB-based hotplate, with separable heater elements.

There are several PCB-project directories, HPcontroller contains the controller, while HPheater contains the heater.

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
-add mode switch
-add increment/decrement buttons
-add power on/off switch
-add RUNning indicator