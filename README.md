# Fronius Modbus for Home Assistant

Unofficial Home Assistant custom integration for reading Fronius GEN24 inverter, smart meter, MPPT, and battery-storage data over a local Modbus TCP connection. The integration can also expose battery-storage controls for reserve, charge/discharge limits, grid charging, grid discharging, and storage control mode.

> [!CAUTION]
> This project is unofficial, experimental, and not supported by Fronius or Home Assistant.
>
> Use it at your own risk. Modbus control can change inverter and battery behaviour, so make sure you understand each setting before changing values.

## Current state

- Integration domain: `fronius_modbus`.
- Current manifest version: `0.2.0`.
- Home Assistant platforms: `sensor`, `number`, and `select`.
- Connection type: local Modbus TCP polling.
- Default port: `502`.
- Default scan interval: `10` seconds.
- Minimum setup scan interval: `5` seconds.
- Required Python package: `pymodbus>=3.9.2`.
- Config flow setup is supported through the Home Assistant UI.
- One inverter Modbus unit/slave ID and one meter Modbus unit/slave ID are configurable in the UI.
- The integration validates that inverter and meter Modbus IDs are unique.
- The integration checks for Fronius as the inverter manufacturer during setup.
- `Primo GEN24` and `Symo GEN24` are the explicitly recognised model prefixes. Other Fronius models may log a warning because they are untested.

## Important notes

> [!IMPORTANT]
> Before using control features, turn off scheduled battery charging/discharging in the Fronius web UI to avoid conflicting commands.

> [!IMPORTANT]
> Update your GEN24 inverter firmware to `1.34.6-1` or newer if battery charging appears limited.

> [!IMPORTANT]
> This integration requires `pymodbus` `3.9.2` or newer. If another Home Assistant integration also uses `pymodbus`, all integrations share the same installed package version, which can cause conflicts. If that happens, remove all custom integrations and YAML Modbus configuration that depend on `pymodbus`, restart Home Assistant, and reinstall/reconfigure them.

## Installation

1. Copy the `custom_components/fronius_modbus` directory into your Home Assistant `config/custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings** → **Devices & services**.
4. Add the **Fronius Modbus** integration.
5. Enter the inverter host/IP address, port, inverter Modbus unit ID, meter Modbus unit ID, and scan interval.

## Fronius inverter Modbus settings

Enable Modbus TCP in the Fronius inverter web interface:

1. Open the inverter web interface.
2. Go to **Communication** → **Modbus**.
3. Enable **Control secondary inverter via Modbus TCP**.
4. Enable **Allow control** if you want Home Assistant to change battery-control values.
5. Set **SunSpec Model Type** to **int + SF**.

![Fronius Modbus settings](images/modbus_settings.png?raw=true "Fronius Modbus settings")

## Configuration options

| Option | Default | Notes |
| --- | ---: | --- |
| Name | `Fronius` | Used for Home Assistant device/entity naming. |
| Host | Required | Inverter hostname or IP address. |
| Port | `502` | Modbus TCP port. |
| Inverter Modbus Unit/Slave ID | `1` | Must be different from the meter unit ID. |
| Meter Modbus Unit/Slave ID | `200` | Must be different from the inverter unit ID. |
| Scan interval | `10` seconds | Setup rejects intervals below `5` seconds. |

## Devices and entities

The integration creates Home Assistant devices for the inverter, configured smart meter, and battery storage when the relevant data is detected.

### Inverter sensors

| Entity | Unit/category | Description |
| --- | --- | --- |
| AC power | W | Current inverter AC power. |
| AC energy | Wh | Inverter lifetime AC energy. |
| Temperature | °C | Cabinet temperature. |
| MPPT1 power | W | MPPT 1 power. |
| MPPT2 power | W | MPPT 2 power. |
| PV power | W | Combined PV power. |
| MPPT1 lifetime energy | Wh | MPPT 1 lifetime energy. |
| MPPT2 lifetime energy | Wh | MPPT 2 lifetime energy. |
| Load | W | Calculated load based on meter AC power and inverter AC power. |
| Line frequency | Hz | Inverter line frequency. |
| Maximum power | W | Inverter maximum power. |
| AC voltage L1-N | V | Inverter L1 to neutral voltage. |
| AC voltage L2-N | V | Symo three-phase voltage sensor. |
| AC voltage L3-N | V | Symo three-phase voltage sensor. |
| AC voltage L1-L2 | V | Symo line-to-line voltage sensor. |
| AC voltage L2-L3 | V | Symo line-to-line voltage sensor. |
| AC voltage L3-L1 | V | Symo line-to-line voltage sensor. |

### Inverter diagnostic sensors

| Entity | Description |
| --- | --- |
| PV connection | PV connection/status diagnostic. |
| Electrical connection | Electrical connection/status diagnostic. |
| Status | Vendor inverter status. |
| Control mode | Inverter control mode diagnostic. |
| Events | Vendor event bitmask as text. |
| Grid status | Grid status based on inverter and/or meter frequency. |
| Connection control | SunSpec connection-control state. |
| Throttle control | Active power limit enable state. |
| Fixed power factor | Fixed power factor enable state. |
| Limit VAr control | Reactive-power limit enable state. |
| Modbus ID | Inverter Modbus unit ID. |

## Solar-output controls

Three manual controls are created on the inverter device:

| Entity | Options/range | Description |
| --- | --- | --- |
| Solar output control | `Auto`, `Limited` | `Auto` disables the SunSpec active-power ceiling. `Limited` applies the configured ceiling. |
| Solar output limit percentage | `0`% to `100`%, step `0.01`% | Direct control of SunSpec Model 123 `WMaxLimPct`. The percentage is relative to the inverter's nominal power. |
| Solar output limit | `0` W to detected inverter maximum, step `10` W | Convenience wrapper for the same active-power ceiling. The integration converts watts to `WMaxLimPct`. |

Set either output-limit entity before selecting **Limited**. Both entities control the same register and therefore remain synchronized. For a 10 kW inverter, `10`% is 1000 W, `1`% is 100 W, and `0`% is 0 W. Select **Auto** to remove the ceiling and return output control to the inverter. The limit applies to inverter AC output; it is not a closed-loop grid-export limit. Battery charging and site load can therefore affect the grid-meter reading.

GEN24 output changes are ramped rather than instantaneous. Allow roughly 90–100 seconds before deciding that a new ceiling has not taken effect. Another active controller, such as Solar.web/Amber cloud control or a higher-priority local rule, can override the Modbus command; Modbus must be allowed in the inverter settings and placed at the intended control priority.

> A value of `0` W is supported, but test a nonzero limit first on each inverter/firmware combination. The integration keeps the inverter grid-connected and uses the power-reduction control; it does not write the standby/disconnect command.

### Smart meter sensors

Smart meter entities are created when a meter is configured and detected.

| Entity | Unit/category | Description |
| --- | --- | --- |
| Meter 1 Power | W | Current meter power. |
| Meter 1 Exported | Wh | Exported energy. |
| Meter 1 Imported | Wh | Imported energy. |
| Meter 1 Line frequency | Hz | Meter line frequency. |
| Meter 1 AC voltage L1-N | V | L1 to neutral voltage. |
| Meter 1 AC voltage L2-N | V | L2 to neutral voltage. |
| Meter 1 AC voltage L3-N | V | L3 to neutral voltage. |
| Meter 1 AC voltage Line to Line | V | Line-to-line voltage. |
| Meter 1 Modbus ID | Diagnostic | Meter Modbus unit ID. |

### Battery-storage sensors

Battery-storage entities are created when storage is configured and detected.

| Entity | Unit/category | Description |
| --- | --- | --- |
| Storage charging power | W | Inverter-side storage charging power. |
| Storage discharging power | W | Inverter-side storage discharging power. |
| Storage connection | Diagnostic | Storage connection/status diagnostic. |
| Storage power | W | Storage power. |
| Storage charging lifetime energy | Wh | Lifetime storage charging energy. |
| Storage discharging lifetime energy | Wh | Lifetime storage discharging energy. |
| Core storage control mode | Diagnostic | Core storage control mode. |
| Charge status | Diagnostic | Holding, charging, or discharging state. |
| Max charging power | W / diagnostic | Current maximum charging power. |
| State of charge | % | Battery state of charge. |
| Charging power | % / diagnostic | Charging-power percentage value. |
| Discharging power | % / diagnostic | Discharging-power percentage value. |
| Minimum reserve | % | Reserve capacity. The battery may charge from the grid if SOC falls below this value. |
| Grid charging | Diagnostic | Grid-charging diagnostic state. |
| Capacity | Wh / diagnostic | Storage capacity rating. |
| Maximum charge rate | W / diagnostic | Storage maximum charge rate. |
| Maximum discharge rate | W / diagnostic | Storage maximum discharge rate. |

## Battery-storage controls

Battery-storage controls are only created when storage is configured and detected.

### Number controls

| Entity | Range/step | Description |
| --- | --- | --- |
| Grid discharge power | `0` W to detected maximum discharge rate, step `10` W | Discharging power when exporting battery energy to the grid. |
| Grid charge power | `0` W to detected maximum charge rate, step `10` W | Charging power when charging the battery from the grid. Grid charging may be effectively limited by the hardware. |
| Discharge limit | `0` W to detected maximum discharge rate, step `10` W | Maximum battery discharging power. |
| PV charge limit | `0` W to detected maximum charge rate, step `10` W | Maximum PV charging power into the battery. |
| Minimum reserve | `5`% to `100`%, step `1`% | Reserve capacity / minimum battery level. |

`PV charge limit` and `Discharge limit` are displayed in watts. When Fronius reports the underlying values as percentages, the integration converts them using the detected maximum charge/discharge rate.

### Storage control mode select

| Mode | Description |
| --- | --- |
| Auto | Normal automatic storage operation down to the configured minimum reserve. |
| PV Charge Limit | Allows PV charging with a configurable charge limit. |
| Discharge Limit | Allows discharging with a configurable discharge limit. |
| PV Charge and Discharge Limit | Allows both PV charge and discharge limits. |
| Charge from Grid | Charges the battery from the grid using **Grid charge power**. |
| Discharge to Grid | Discharges the battery to the grid using **Grid discharge power**. |
| Block Discharging | Allows charging but blocks discharging. |
| Block Charging | Allows discharging but blocks charging. |

Change the storage control mode first, then set the number control that is active for that mode.

### Controls active by mode

| Mode | PV charge limit | Discharge limit | Grid charge power | Grid discharge power | Minimum reserve |
| --- | --- | --- | --- | --- | --- |
| Auto | Ignored | Ignored | Ignored | Ignored | Used |
| PV Charge Limit | Used | Ignored | Ignored | Ignored | Used |
| Discharge Limit | Ignored | Used | Ignored | Ignored | Used |
| PV Charge and Discharge Limit | Used | Used | Ignored | Ignored | Used |
| Charge from Grid | Ignored | Ignored | Used | Ignored | Used |
| Discharge to Grid | Ignored | Ignored | Ignored | Used | Used |
| Block Discharging | Used | Ignored | Ignored | Ignored | Used |
| Block Charging | Ignored | Used | Ignored | Ignored | Used |

### Fronius web UI mapping

| Fronius web UI name | Integration control | Integration mode |
| --- | --- | --- |
| Max. charging power | PV charge limit | PV Charge Limit / PV Charge and Discharge Limit / Block Discharging |
| Min. charging power | Grid charge power | Charge from Grid |
| Max. discharging power | Discharge limit | Discharge Limit / PV Charge and Discharge Limit / Block Charging |
| Min. discharging power | Grid discharge power | Discharge to Grid |
| Reserve Capacity | Minimum reserve | Any storage control mode |

## Example screenshots

The screenshots below are examples and may not match the current entity set exactly.

Battery Storage

![Battery storage example](images/example_batterystorage0.png?raw=true "Battery storage")

Battery Storage Actions

![Battery storage actions example](images/example_batterystorage.png?raw=true "Battery storage actions")

Smart Meter

![Smart meter example](images/example_meter.png?raw=true "Smart meter")

Inverter

![Inverter example](images/example_inverter.png?raw=true "Inverter")

## Troubleshooting

- Confirm the inverter is reachable from Home Assistant on TCP port `502`.
- Confirm Modbus TCP is enabled in the Fronius web UI.
- Confirm **SunSpec Model Type** is set to **int + SF**.
- Confirm inverter and meter Modbus unit IDs are unique.
- Use a scan interval of at least `5` seconds.
- If setup fails with unsupported hardware, check the Home Assistant log for the manufacturer/model returned by the inverter.
- If entities do not appear, check whether the integration detected the relevant meter, MPPT, or storage data during setup.

## References

- [Fronius operating instructions PDF](https://www.fronius.com/~/downloads/Solar%20Energy/Operating%20Instructions/42,0410,2649.pdf)
- [home-assistant-solaredge-modbus](https://github.com/binsentsu/home-assistant-solaredge-modbus/)
- [byd_charging](https://github.com/bigramonk/byd_charging)
