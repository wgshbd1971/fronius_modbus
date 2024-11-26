"""Platform for sensor integration."""
from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from homeassistant.components.sensor import (
#    PLATFORM_SCHEMA,
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass
)

from homeassistant.const import UnitOfTemperature
from homeassistant.const import CONF_NAME #, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.entity_platform import AddEntitiesCallback
#from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
#from homeassistant.util import dt as dt_util

from . import HubConfigEntry
from .const import (
    DOMAIN,
    ATTR_MANUFACTURER,
    INVERTER_SENSOR_TYPES,
    METER_SENSOR_TYPES,
    STORAGE_SENSOR_TYPES,
    ENTITY_PREFIX,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    hub = config_entry.runtime_data
    hub_name = config_entry.data[CONF_NAME]

    entities = []

    device_info = {
        "identifiers": {(DOMAIN, f'{hub_name}_inverter')},
        "name": f'Inverter',
        "manufacturer": hub.data['i_manufacturer'],
        "model": hub.data['i_model'],
        "serial_number": hub.data['i_serial'],
        "sw_version": hub.data['i_sw_version'],
    }

    for sensor_info in INVERTER_SENSOR_TYPES.values():
        sensor = FroniusModbusSensor(
            platform_name = ENTITY_PREFIX,
            hub = hub,
            device_info = device_info,
            name = sensor_info[0],
            key = sensor_info[1],
            device_class = sensor_info[2],
            state_class = sensor_info[3],
            unit = sensor_info[4],
            icon = sensor_info[5],
        )
        entities.append(sensor)

    if hub.read_meter1:
        device_info = {
            "identifiers": {(DOMAIN, f'{hub_name}_meter1')},
            "name": f'Meter 1',
            "manufacturer": hub.data['m1_manufacturer'],
            "model": hub.data['m1_model'],
            "serial_number": hub.data['m1_serial'],
            "sw_version": hub.data['m1_sw_version'],
        }

        for sensor_info in METER_SENSOR_TYPES.values():
            sensor = FroniusModbusSensor(
                platform_name = ENTITY_PREFIX,
                hub = hub,
                device_info = device_info,
                name = 'Meter 1 ' + sensor_info[0],
                key = 'm1_' + sensor_info[1],
                device_class = sensor_info[2],
                state_class = sensor_info[3],
                unit = sensor_info[4],
                icon = sensor_info[5],
            )
            entities.append(sensor)        

    device_info = {
        "identifiers": {(DOMAIN, f'{hub_name}_battery_storage')},
        "name": f'Battery Storage',
        "manufacturer": ATTR_MANUFACTURER,
    }

    for sensor_info in STORAGE_SENSOR_TYPES.values():
        sensor = FroniusModbusSensor(
            platform_name = ENTITY_PREFIX,
            hub = hub,
            device_info = device_info,
            name = sensor_info[0],
            key = sensor_info[1],
            device_class = sensor_info[2],
            state_class = sensor_info[3],
            unit = sensor_info[4],
            icon = sensor_info[5],
        )
        entities.append(sensor)

    async_add_entities(entities)
    return True

class FroniusModbusSensor(SensorEntity):
    """Representation of an Fronius Modbus Modbus sensor."""

    def __init__(self, platform_name, hub, device_info, name, key, device_class, state_class, unit, icon):
        """Initialize the sensor."""
        self._platform_name = platform_name
        self._hub = hub
        self._key = key
        self._name = name
        self._unit_of_measurement = unit
        self._icon = icon
        self._device_info = device_info
        if not device_class is None:
            self._attr_device_class = device_class
        if not state_class is None:
            self._attr_state_class = state_class

#        self._attr_state_class = SensorStateClass.MEASUREMENT
#        if self._unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR :
#            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
#            self._attr_device_class = SensorDeviceClass.ENERGY
#        if self._unit_of_measurement == UnitOfPower.WATT :
#            self._attr_device_class = SensorDeviceClass.POWER

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._hub.async_add_hub_entity(self._modbus_data_updated)

    async def async_will_remove_from_hass(self) -> None:
        self._hub.async_remove_hub_entity(self._modbus_data_updated)

    @callback
    def _modbus_data_updated(self):
        self.async_write_ha_state()

    @callback
    def _update_state(self):
        if self._key in self._hub.data:
            #_LOGGER.info(f"modbus referesh sensor {self._key} {self._state}")
            self._state = self._hub.data[self._key]

            self._icon = icon_for_battery_level(
                battery_level=self.native_value, charging=charging
            )

    @property
    def name(self):
        """Return the name."""
        return f"{self._name}"

    @property
    def unique_id(self) -> Optional[str]:
        #return f"{self._key}"
        #_LOGGER.info(f'unique_id {self._platform_name}_{self._key} {self.device_info} {self._name}')
        return f"{self._platform_name}_{self._key}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the sensor icon."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._key in self._hub.data:
            return self._hub.data[self._key]

    @property
    def extra_state_attributes(self):
        #if self._key in ["status", "statusvendor"] and self.state in DEVICE_STATUSSES:
        #    return {ATTR_STATUS_DESCRIPTION: DEVICE_STATUSSES[self.state]}
        #elif "battery1" in self._key and "battery1_attrs" in self._hub.data:
        #    return self._hub.data["battery1_attrs"]
        #elif "battery2" in self._key and "battery2_attrs" in self._hub.data:
        #    return self._hub.data["battery2_attrs"]
        #elif "battery3" in self._key and "battery3_attrs" in self._hub.data:
        #    return self._hub.data["battery3_attrs"]
        return None

    @property
    def should_poll(self) -> bool:
        """Data is delivered by the hub"""
        return False

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        return self._device_info




