# Scripts

heaterPlugin.py is a kicad plugin.  It needs to be copied to your kicad plugin directory. This direcory can be found in pcbnew via tools>external plugins>open plugin directory. Once the plugin is copied, go to tools>external plugins>refresh plugins, and then it should be possible to use tools>external plugins>heater plugin to generate a heater trace.

This trace is continuous (closed), and should be "snipped" on an edge to connect it to whatever is supplying power to the heater.

plot design may be manually edited to give you the desired design plot for a heater trace.  see [this](https://aylo6061.com/2022/12/15/pcb-hot-plate-state-of-the-art/) blog post for more information.