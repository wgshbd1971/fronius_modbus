"""Common Home Assistant entity behaviour."""

from __future__ import annotations

from homeassistant.core import callback

from .hub import Hub


class FroniusModbusBaseEntity:
    """Common entity behaviour for values delivered by the hub."""
    _key = None
    _options_dict = None

    def __init__(
        self,
        platform_name,
        hub,
        device_info,
        name,
        key,
        device_class=None,
        state_class=None,
        unit=None,
        icon=None,
        entity_category=None,
        options=None,
        min=None,
        max=None,
        native_step=None,
        mode=None,
    ):
        self._platform_name = platform_name
        self._hub: Hub = hub
        self._key = key
        if device_class is not None:
            self._attr_device_class = device_class
        if state_class is not None:
            self._attr_state_class = state_class
        if entity_category is not None:
            self._attr_entity_category = entity_category
        if options is not None:
            self._options_dict = options
            self._attr_options = list(options.values())
        if min is not None:
            self._attr_native_min_value = min
        if max is not None:
            self._attr_native_max_value = max
        if native_step is not None:
            self._attr_native_step = native_step
        if mode is not None:
            self._attr_mode = mode

        self._attr_has_entity_name = True
        self._attr_name = name
        self._attr_unique_id = f"{self._platform_name}_{self._key}"
        self._attr_device_info = device_info
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()
        self._hub.async_add_hub_entity(self._modbus_data_updated)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks."""
        self._hub.async_remove_hub_entity(self._modbus_data_updated)
        await super().async_will_remove_from_hass()

    @callback
    def _modbus_data_updated(self):
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Data is delivered by the hub."""
        return False

    @property
    def available(self) -> bool:
        """Return whether the Modbus hub is online."""
        return self._hub.online


