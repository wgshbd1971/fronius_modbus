"""Platform for sensor integration."""
from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from homeassistant.components.sensor import (
    SensorEntity,
)
from homeassistant.const import CONF_NAME #, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
from homeassistant.util import slugify

from . import HubConfigEntry
from .const import (
    INVERTER_SENSOR_TYPES,
    METER_SENSOR_TYPES,
    STORAGE_SENSOR_TYPES,
    ENTITY_PREFIX,
)
from .hub import Hub
from .base import FroniusModbusBaseEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    hub:Hub = config_entry.runtime_data
    hub_name = config_entry.data[CONF_NAME]

    entities = []

    for sensor_info in INVERTER_SENSOR_TYPES.values():
        sensor = FroniusModbusSensor(
            platform_name = ENTITY_PREFIX,
            hub = hub,
            device_info = hub.device_info_inverter,
            name = sensor_info[0],
            key = sensor_info[1],
            device_class = sensor_info[2],
            state_class = sensor_info[3],
            unit = sensor_info[4],
            icon = sensor_info[5],
            entity_category = sensor_info[6],
        )
        entities.append(sensor)

    if hub.meter_configured:

        for sensor_info in METER_SENSOR_TYPES.values():
            sensor = FroniusModbusSensor(
                platform_name = ENTITY_PREFIX,
                hub = hub,
                device_info = hub.get_device_info_meter('1'),
                name = 'Meter 1 ' + sensor_info[0],
                key = 'm1_' + sensor_info[1],
                device_class = sensor_info[2],
                state_class = sensor_info[3],
                unit = sensor_info[4],
                icon = sensor_info[5],
                entity_category = sensor_info[6],
            )
            entities.append(sensor)        

    if hub.storage_configured:

        for sensor_info in STORAGE_SENSOR_TYPES.values():
            sensor = FroniusModbusSensor(
                platform_name = ENTITY_PREFIX,
                hub = hub,
                device_info = hub.device_info_storage,
                name = sensor_info[0],
                key = sensor_info[1],
                device_class = sensor_info[2],
                state_class = sensor_info[3],
                unit = sensor_info[4],
                icon = sensor_info[5],
                entity_category = sensor_info[6],
            )
            entities.append(sensor)

    async_add_entities(entities)
    return True

class FroniusModbusSensor(FroniusModbusBaseEntity, SensorEntity):
    """Representation of an Fronius Modbus Modbus sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._key in self._hub.data:
            return self._hub.data[self._key]

            # self._icon = icon_for_battery_level(
            #     battery_level=self.native_value, charging=False
            # )                

    @property
    def extra_state_attributes(self):
        return None





