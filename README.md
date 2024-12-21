[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

# fronius_modbus
Home assistant Custom Component for reading data from Fronius Gen24 Inverter and connected smart meters and battery storage. This integration uses a local modbus connection. 

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

# Usage

### Battery Storage

### Controls
| Entity  | Description |
| --- | --- |
| PV Charge Limit  | This is maximum percentage relative to maxium PV charging power of which the battery can be charged by.  |
| Discharge Limit | This is maximum percentage relative to maxium discharging power of which the battery can be discharged by.  |
| Grid Charge Power | The relative charging power when the storage is being charged from the grid. Note that grid charging is seems to be limited to an effictive 50% by the hardware. |
| Grid Discharge Power | The relative discharging power when the storage is being discharged to the grid. |
| Minimum Reserve | The minimum reserve for storage when discharging. Note that the storage will charge from the grid with 0.5kW if SOC falls below this level. |

### Storage Control Modes
| Mode  | Description |
| --- | --- |
| Auto  | The storage will allow charging and discharging up to the minimum reserve. |
| PV Charge Limit | The storage can be charged with PV power at a limited rate. |
| Discharge Limit | The storage can be charged with PV power and discharged at a limited rate. |
| PV Charge and Discharge Limit | Allows setting both PV charge and discharge limits. |
| Charge from Grid | The storage will be charged from the grid using the charge rate from 'Grid Charge Power'.  |
| Discharge to Grid | The storage will discharge to the gird using the discharge rate from 'Gird Discharge Power'. |
| Block discharging | The storage can only be charged with PV power. |
| Block charging | The can only be discharged and won't be charged with PV power. |

### Controls used by Modes
| Mode | Charge Limit | Discharge Limit | Grid Charge Power |  Grid Discharge Power | Minimum Reserve | 
| --- | --- | --- | --- | --- | --- |
| Auto | Ignored (100%) | Ignored (100%) | Ignored (0%) | Ignored (0%) | Used | 
| PV Charge Limit | Used | Ignored (100%) | Ignored (0%) | Ignored (0%) | Used |
| Discharge Limit  | Ignored (100%) | Used | Ignored (0%) | Ignored (0%) | Used |
| PV Charge and Discharge Limit  | Used | Used | Ignored (0%) | Ignored (0%) | Used |
| Charge from Grid | Ignored | Ignored | Used | Ignored (0%) | Used |
| Charge from Grid | Ignored | Ignored | Ignored (0%) | Used | Used |
| Block discharging | Used | Ignored (0%) | Ignored (0%) | Ignored (0%) | Used |
| Block charging | Ignored (0%) | Used | Ignored (0%) | Ignored (0%) | Used |

### Sensors
| Entity  | Description |
| --- | --- |
| Charge Status | Holding / Charging / Discharging |
| Minimum Reserve | This is minium level to which the battery can be discharged and will be charged from the grid if falls below |
| State of Charge | The current battery level |

### Diagnostic
| Entity  | Description |
| --- | --- |
To come!

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
