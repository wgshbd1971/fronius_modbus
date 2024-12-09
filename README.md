[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

# fronius_modbus
Home assistant Custom Component for reading data from Fronius Gen24 Inverter and connected smart meters and battery storage. This integration uses a local modbus connection instead of the cloud based SolarWeb integration. 

> [!CAUTION]
> This is a work in progress project - it is still in early development stage, so there are still breaking changes possible.
>
> This is an unofficial implementation and not supported by Fronius. It might stop working at any point in time.
> You are using this module (and it's prerequisites/dependencies) at your own risk. Not me neither any of contributors to this or any prerequired/dependency project are responsible for damage in any kind caused by this project or any of its prerequsites/dependencies.

# Installation
Copy contents of custom_components folder to your home-assistant config/custom_components folder or install through HACS.
After reboot of Home-Assistant, this integration can be configured through the integration setup UI.

Make sure modbus is enabled on the inverter. You can check by going into the web interface of the inverter and go to:
"Communication" -> "Modbus"

And turn on:
- "Con­trol sec­ond­ary in­ver­t­er via Mod­bus TCP"
- "Allow control"
- Make sure that under 'SunSpec Model Type' has 'int + SF' selected. 

![modbus settings](images/modbus_settings.png?raw=true "modbus")


# Example Devices

Battery Storage
![battery storage](images/example_batterystorage0.png?raw=true "storage")

Battery Storage Actions
![battery storage actions](images/example_batterystorage.png?raw=true "storage actions")

Smart Meter
![smart meter](images/example_meter.png?raw=true "meter")

Inverter 
![smart meter](images/example_inverter.png?raw=true "inverter")


# References
- https://www.fronius.com/~/downloads/Solar%20Energy/Operating%20Instructions/42,0410,2649.pdf
- https://github.com/binsentsu/home-assistant-solaredge-modbus/
- https://github.com/bigramonk/byd_charging
