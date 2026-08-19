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
from .base import FroniusModbusBaseEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    hub:Hub = config_entry.runtime_data

    entities = []

    if hub.pv_control_configured:
        entities.append(
            FroniusModbusNumber(
                ENTITY_PREFIX,
                hub,
                hub.device_info_inverter,
                "Solar output limit",
                "pv_output_limit_w",
                min=0,
                max=hub.data["max_power"],
                unit="W",
                mode="box",
                native_step=10,
            )
        )
    else:
        _LOGGER.warning(
            "Solar output controls are unavailable because the inverter did not "
            "expose a valid SunSpec immediate-control block"
        )

    if hub.storage_configured:

        for number_info in STORAGE_NUMBER_TYPES:

            max = None
            max_key = number_info[2].get('max_key')
            if not max_key is None:
                max = hub.data.get(max_key)
            if max is None:
                max = number_info[2]['max']

            number = FroniusModbusNumber(
                ENTITY_PREFIX,
                hub,
                hub.device_info_storage,
                number_info[0],
                number_info[1],
                min = number_info[2]['min'],
                max = max,
                unit = number_info[2]['unit'],
                mode = number_info[2]['mode'],
                native_step = number_info[2]['step'],
            )
            entities.append(number)

    async_add_entities(entities)
    return True

class FroniusModbusNumber(FroniusModbusBaseEntity, NumberEntity):
    """Representation of a Battery Storage Modbus number."""

    @property
    def native_value(self) -> float | None:
        """Return the current value in watts."""

        if self._key == "discharge_limit":
            value = self._hub.data.get(self._key)
            if value is None:
                return None
            max_rate = self._hub.max_discharge_rate_w or 10000
            # Only convert when value is percent (Fronius reports 0–100)
            return round(value / 100.0 * max_rate, 0) if value <= 100 else value

        if self._key == "charge_limit":
            value = self._hub.data.get(self._key)
            if value is None:
                return None
            max_rate = self._hub.max_charge_rate_w or 10000
            # Only convert when value is percent (Fronius reports 0–100)
            return round(value / 100.0 * max_rate, 0) if value <= 100 else value

        # Storage data can be briefly absent while the integration starts.
        # Returning None keeps the entity unavailable until the first good read
        # instead of aborting entity setup with a KeyError.
        return self._hub.data.get(self._key)

    async def async_set_native_value(self, value: float) -> None:
        """Change the selected value."""

        if self._key == 'minimum_reserve':
            await self._hub.set_minimum_reserve(value)
        elif self._key == 'charge_limit':
            await self._hub.set_charge_limit(value)
        elif self._key == 'discharge_limit':
            await self._hub.set_discharge_limit(value)
        elif self._key == 'grid_charge_power':
            await self._hub.set_grid_charge_power(value)
        elif self._key == 'grid_discharge_power':
            await self._hub.set_grid_discharge_power(value)
        elif self._key == 'pv_output_limit_w':
            await self._hub.set_pv_output_limit_w(value)

        #_LOGGER.debug(f"Number {self._key} set to {value}")
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return depending on mode."""
        if not self._hub.online:
            return False
        if self._key == 'minimum_reserve':
            return True
        if self._key == 'pv_output_limit_w':
            return self._hub.pv_control_configured
        if self._key == 'charge_limit' and self._hub.storage_extended_control_mode in [1,3,6]:
            return True
        if self._key == 'discharge_limit' and self._hub.storage_extended_control_mode in [2,3,7]:
            return True
        if self._key == 'grid_charge_power' and self._hub.storage_extended_control_mode in [4]:
            return True
        if self._key == 'grid_discharge_power' and self._hub.storage_extended_control_mode in [5]:
            return True
        return False
