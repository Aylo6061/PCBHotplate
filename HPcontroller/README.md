# README

some future stuff will go here

# BUGS

pin 1 and 3 are swapped on U3, which makes the thermisor protection circuit not work.  I cut R9 jumper to fix "fix" this, at some point I'll verify that it works by bodge wiring.

GPIO 9 is routed to the MODE switch, however GPIO 9 is also the boot strapping pin to force the bootloader to turn on- therefore it must be switched to PROG when the code is programmed/when the micro boots.