import logging
from typing import Optional, Dict, Any

from .const import (
    DOMAIN,
    ATTR_MANUFACTURER,
    NUMBER_TYPES,
    ENTITY_PREFIX,
)

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder

from homeassistant.const import CONF_NAME
from homeassistant.components.number import (
    PLATFORM_SCHEMA,
    NumberEntity,
)

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    hub_name = config_entry.data[CONF_NAME]
    hub = config_entry.runtime_data

    device_info = {
        "identifiers": {(DOMAIN, f'{hub_name}_battery_storage')},
        "name": f'Battery Storage',
        "manufacturer": ATTR_MANUFACTURER,
    }

    entities = []

    for number_info in NUMBER_TYPES:
        number = FroniusModbusNumber(
            ENTITY_PREFIX,
            hub,
            device_info,
            number_info[0],
            number_info[1],
            number_info[2],
            number_info[3],
            dict(min=number_info[4]['min'],
                    max=number_info[4]['max'],
                    unit=number_info[4]['unit']
            )
        )
        #_LOGGER.info(f"Adding number {ENTITY_PREFIX} {number_info[0]} {hub_name}")
        entities.append(number)

    async_add_entities(entities)
    return True

class FroniusModbusNumber(NumberEntity):
    """Representation of an Battery Storage Modbus number."""

    def __init__(self,
                 platform_name,
                 hub,
                 device_info,
                 name,
                 key,
                 register,
                 fmt,
                 attrs
    ) -> None:
        """Initialize the selector."""
        self._platform_name = platform_name
        self._hub = hub
        self._device_info = device_info
        self._name = name
        self._key = key
        self._register = register
        self._fmt = fmt

        self._attr_native_min_value = attrs["min"]
        self._attr_native_max_value = attrs["max"]
        if "unit" in attrs.keys():
            self._attr_native_unit_of_measurement = attrs["unit"]

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hub.async_add_hub_entity(self._modbus_data_updated)

    async def async_will_remove_from_hass(self) -> None:
        self._hub.async_remove_hub_entity(self._modbus_data_updated)

    @callback
    def _modbus_data_updated(self) -> None:
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._name}"

    @property
    def unique_id(self) -> Optional[str]:
        return f"{self._platform_name}_{self._key}"

    @property
    def should_poll(self) -> bool:
        """Data is delivered by the hub"""
        return False

    @property
    def native_value(self) -> float:
        if self._key in self._hub.data:
            return self._hub.data[self._key]

    async def async_set_native_value(self, value: float) -> None:
        """Change the selected value."""
        builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)

        #if self._fmt == "u32":
        #    builder.add_32bit_uint(int(value))
        #elif self._fmt =="u16":
        #    builder.add_16bit_uint(int(value))
        #elif self._fmt == "f":
        #    builder.add_32bit_float(float(value))
        #else:
        #    _LOGGER.error(f"Invalid encoding format {self._fmt} for {self._key}")
        #    return

        #response = self._hub.write_registers(unit=1, address=self._register, payload=builder.to_registers())
        #if response.isError():
        #    _LOGGER.error(f"Could not write value {value} to {self._key}")
        #    return
        if self._key == 'minimum_reserve':
            self._hub.set_minimum_reserve(value)

        if self._key == 'discharge_limit':
            if self._hub.data.get('control_mode') == 2:
                self._hub.set_discharge_rate(value)

        if self._key == 'charge_limit':
            if self._hub.data.get('control_mode') == 2 and self._hub.data.get('soc') == 99:
                self._hub.set_discharge_rate(value * -1)

        self._hub.data[self._key] = value
        _LOGGER.info(f"Number {self._key} set to {value}")
        self.async_write_ha_state()

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        return self._device_info