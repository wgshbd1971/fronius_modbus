"""The Fronius Modbus integration."""

from __future__ import annotations

import logging
import asyncio
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import Platform

from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (
    DOMAIN,
    CONF_INVERTER_UNIT_ID,
    CONF_METER_UNIT_ID,
)

from . import hub

_LOGGER = logging.getLogger(__name__)

# List of platforms to support. There should be a matching .py file for each,
# eg <cover.py> and <sensor.py>
PLATFORMS = [Platform.NUMBER, Platform.SELECT, Platform.SENSOR]

HubConfigEntry = ConfigEntry[hub.Hub]

async def async_setup_entry(hass: HomeAssistant, entry: HubConfigEntry) -> bool:
    """Set up Fronius Modbus from a config entry."""

    if not hass.services.has_service(DOMAIN, "set_generation_limit"):
        async def set_generation_limit(call: ServiceCall) -> None:
            target = hass.config_entries.async_get_entry(call.data["entry_id"])
            if target is None or target.domain != DOMAIN or target.state is not ConfigEntryState.LOADED:
                raise HomeAssistantError("Fronius integration is not loaded")
            client = target.runtime_data._rest_client
            if client is None:
                raise HomeAssistantError("Local Fronius REST credentials are not configured")
            await client.async_set_generation_limit(call.data["percent"])

        hass.services.async_register(
            DOMAIN, "set_generation_limit", set_generation_limit,
            schema=vol.Schema({vol.Required("entry_id"): str,
                               vol.Required("percent"): vol.All(vol.Coerce(float), vol.Range(min=0, max=100))}),
        )

    if not hass.services.has_service(DOMAIN, "set_export_limit"):
        async def set_export_limit(call: ServiceCall) -> None:
            target = hass.config_entries.async_get_entry(call.data["entry_id"])
            if target is None or target.domain != DOMAIN or target.state is not ConfigEntryState.LOADED:
                raise HomeAssistantError("Fronius integration is not loaded")
            controller = target.runtime_data
            watts = call.data["watts"]
            seconds = call.data.get("restore_after", 0)
            if not seconds:
                await controller.set_export_limit(watts)
                return
            if target.options.get("export_limit_restore") is not None:
                raise HomeAssistantError("An export-limit test is already pending")
            # Save restoration before writing, including across an HA restart.
            marker = {"watts": watts, "restore": 0}
            hass.config_entries.async_update_entry(target, options={**target.options, "export_limit_restore": marker})
            owns_setting = True
            try:
                if not await controller.set_export_limit(watts, expected_limit=0):
                    owns_setting = False
                    raise HomeAssistantError("A bounded export test must start from zero export")
                await asyncio.sleep(seconds)
            finally:
                # Restore only our own setting; preserve a newer external command.
                if owns_setting:
                    await controller.set_export_limit(0, expected_limit=watts)
                options = dict(target.options)
                options.pop("export_limit_restore", None)
                hass.config_entries.async_update_entry(target, options=options)

        hass.services.async_register(
            DOMAIN, "set_export_limit", set_export_limit,
            schema=vol.Schema({vol.Required("entry_id"): str,
                               vol.Required("watts"): vol.All(vol.Coerce(int), vol.Range(min=0)),
                               vol.Optional("restore_after", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=120))}),
        )

    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    inverter_unit_id = entry.data.get(CONF_INVERTER_UNIT_ID, 1)
    meter_unit_ids = [entry.data.get(CONF_METER_UNIT_ID, 1)]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]
    rest_username = entry.options.get(CONF_USERNAME)
    rest_password = entry.options.get(CONF_PASSWORD)

    _LOGGER.debug("Setup %s.%s", DOMAIN, name)

    # Store an instance of the "connecting" class that does the work of speaking
    # with your actual devices.
    entry.runtime_data = hub.Hub(
        hass=hass,
        name=name,
        host=host,
        port=port,
        inverter_unit_id=inverter_unit_id,
        meter_unit_ids=meter_unit_ids,
        scan_interval=scan_interval,
        rest_session=async_get_clientsession(hass),
        rest_username=rest_username,
        rest_password=rest_password,
    )
    
    # Preserve the real normal limit across temporary allowances and restarts.
    normal = entry.options.get("normal_export_limit_w")
    if isinstance(normal, int) and normal > 0:
        entry.runtime_data._normal_export_limit_w = normal
    await entry.runtime_data.init_data()
    if entry.runtime_data.rest_export_control_configured:
        options = dict(entry.options)
        options["normal_export_limit_w"] = entry.runtime_data._normal_export_limit_w
        marker = options.pop("export_limit_restore", None)
        if marker is not None:
            await entry.runtime_data.set_export_limit(marker["restore"], expected_limit=marker["watts"])
        if options != dict(entry.options):
            hass.config_entries.async_update_entry(entry, options=options)

    # This creates each HA object for each platform your device requires.
    # It's done by calling the `async_setup_entry` function in each platform module.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration after its REST credentials change."""
    client = entry.runtime_data._rest_client
    if client is not None and (entry.options.get(CONF_USERNAME), entry.options.get(CONF_PASSWORD)) == (client._username, client._password):
        return  # Internal export metadata does not require an integration reload.
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok

