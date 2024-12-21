import logging
from typing import Optional, Dict, Any

from .const import (
    STORAGE_NUMBER_TYPES,
    ENTITY_PREFIX,
)

from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from homeassistant.components.number import (
    NumberEntity,
)

from .hub import Hub

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    hub_name = config_entry.data[CONF_NAME]
    hub:Hub = config_entry.runtime_data

    entities = []

    if hub.storage_configured:

        for number_info in STORAGE_NUMBER_TYPES:
            number = FroniusModbusNumber(
                ENTITY_PREFIX,
                hub,
                hub.device_info_storage,
                number_info[0],
                number_info[1],
                dict(min=number_info[2]['min'],
                        max=number_info[2]['max'],
                        unit=number_info[2]['unit']
                )
            )
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
                 attrs
    ) -> None:
        """Initialize the selector."""
        self._platform_name = platform_name
        self._hub:Hub = hub
        self._device_info = device_info
        self._name = name
        self._key = key

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

        if self._key == 'minimum_reserve':
            self._hub.set_minimum_reserve(value)
        elif self._key == 'charge_limit':
            if self._hub.storage_extended_control_mode in [1,3,6]:
                # only change when discharge limit is used
                self._hub.set_charge_rate(value)
            elif self._hub.storage_extended_control_mode in [4,5,7]:
                return
            elif self._hub.storage_extended_control_mode in [0,2]:
                return
        elif self._key == 'discharge_limit':
            if self._hub.storage_extended_control_mode in [2,3,7]:
                # only change when discharge limit is used
                self._hub.set_discharge_rate(value)
            elif self._hub.storage_extended_control_mode in [4,5,6]:
                return
            elif self._hub.storage_extended_control_mode in [0,1]:
                return
        elif self._key == 'grid_charge_power':
            if self._hub.storage_extended_control_mode == 4:
                self._hub.set_discharge_rate(value * -1)
            else:
                return
        elif self._key == 'grid_discharge_power':
            if self._hub.storage_extended_control_mode == 5:
                self._hub.set_charge_rate(value * -1)
            else:
                return

        self._hub.data[self._key] = value
        _LOGGER.warning(f"Number {self._key} set to {value} cm {self._hub.storage_extended_control_mode}")
        self.async_write_ha_state()

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        return self._device_info