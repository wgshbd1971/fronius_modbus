import logging

from .const import (
    STORAGE_SELECT_TYPES,
    ENTITY_PREFIX,
)

from homeassistant.components.select import SelectEntity

from .hub import Hub
from .base import FroniusModbusBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    hub: Hub = config_entry.runtime_data

    entities = []

    if hub.pv_control_configured:
        entities.append(
            FroniusModbusSolarOutputSelect(
                platform_name=ENTITY_PREFIX,
                hub=hub,
                device_info=hub.device_info_inverter,
                name="Solar output control",
                key="pv_output_control",
                options={0: "Auto", 1: "Limited"},
            )
        )

    if hub.storage_configured:
        for select_info in STORAGE_SELECT_TYPES:
            select = FroniusModbusSelect(
                platform_name=ENTITY_PREFIX,
                hub=hub,
                device_info=hub.device_info_storage,
                name=select_info[0],
                key=select_info[1],
                options=select_info[2],
            )
            entities.append(select)

    async_add_entities(entities)
    return True


def get_key(my_dict, search):
    for k, v in my_dict.items():
        if v == search:
            return k
    return None


class FroniusModbusSelect(FroniusModbusBaseEntity, SelectEntity):
    """Representation of an Battery Storage select."""

    @property
    def current_option(self) -> str:
        if self._key in self._hub.data:
            return self._hub.data[self._key]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        new_mode = get_key(self._options_dict, option)

        await self._hub.set_mode(new_mode)

        self._hub.data[self._key] = option
        # self._hub.storage_extended_control_mode = new_mode
        self.async_write_ha_state()


class FroniusModbusSolarOutputSelect(FroniusModbusBaseEntity, SelectEntity):
    """Manual active-power limiting mode."""

    @property
    def current_option(self) -> str:
        enabled = self._hub.data.get("WMaxLim_Ena")
        if enabled == "Enabled":
            return "Limited"
        if enabled == "Disabled":
            return "Auto"
        return None

    @property
    def available(self) -> bool:
        return self._hub.online and self._hub.pv_control_configured

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            raise ValueError(f"Unsupported solar output mode: {option}")
        await self._hub.set_pv_limit_enabled(option == "Limited")
        self.async_write_ha_state()

