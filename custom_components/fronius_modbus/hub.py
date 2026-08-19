"""Fronius Modbus Hub."""
from __future__ import annotations

import logging
import asyncio
from functools import wraps
from datetime import timedelta
from typing import Optional
from importlib.metadata import version, PackageNotFoundError
from packaging.version import Version

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.core import HomeAssistant

from .froniusmodbusclient import FroniusModbusClient

from .const import (
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

class Hub:
    """Hub for Fronius Battery Storage Modbus Interface"""

    PYMODBUS_VERSION = '3.9.2'

    def __init__(self, hass: HomeAssistant, name: str, host: str, port: int, inverter_unit_id: int, meter_unit_ids, scan_interval: int) -> None:
        """Init hub."""
        self._hass = hass
        self._name = name

        self._id = f"{name.lower()}_{host.lower().replace('.', '')}"
        self.online = True        

        self._client = FroniusModbusClient(host=host, port=port, inverter_unit_id=inverter_unit_id, meter_unit_ids=meter_unit_ids, timeout=max(3, (scan_interval - 1)))
        self._scan_interval = timedelta(seconds=scan_interval)
        self._unsub_interval_method = None
        self._entities = []
        self._entities_dict = {}
        self._operation_lock = asyncio.Lock()

    def toggle_busy(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # A control command must wait for an in-progress poll instead of
            # being silently discarded. asyncio.Lock also releases safely if
            # the operation raises or is cancelled.
            async with self._operation_lock:
                return await func(self, *args, **kwargs)
        return wrapper

    @toggle_busy
    async def init_data(self, close = False, read_status_data = False):
        await self._hass.async_add_executor_job(self.check_pymodbus_version)  
        result = await self._client.init_data()

        if self.storage_configured:
            result : bool = await self._hass.async_add_executor_job(self._client.get_json_storage_info)                

        return

    def check_pymodbus_version(self):
        try:
            installed = Version(version("pymodbus"))
        except PackageNotFoundError:
            _LOGGER.warning("pymodbus not found")
            return

        required = Version(self.PYMODBUS_VERSION)
        if installed < required:
            raise Exception(
                f"pymodbus {installed} found, please update to {self.PYMODBUS_VERSION} or higher"
            )
        _LOGGER.debug("pymodbus %s", installed)

    @property 
    def device_info_storage(self) -> dict:
        return {
            "identifiers": {(DOMAIN, f"{self._name}_battery_storage")},
            "name": f"{self._client.data.get('s_model')}",
            "manufacturer": self._client.data.get('s_manufacturer'),
            "model": self._client.data.get('s_model'),
            "serial_number": self._client.data.get('s_serial'),
        }

    @property 
    def device_info_inverter(self) -> dict:
        return {
            "identifiers": {(DOMAIN, f"{self._name}_inverter")},
            "name": f"Fronius {self._client.data.get('i_model')}",
            "manufacturer": self._client.data.get('i_manufacturer'),
            "model": self._client.data.get('i_model'),
            "serial_number": self._client.data.get('i_serial'),
            "sw_version": self._client.data.get('i_sw_version'),
            #"hw_version": f"modbus id-{self._client.data.get('i_unit_id')}",
        }
    
    def get_device_info_meter(self, id) -> dict:
        return {
            "identifiers": {(DOMAIN, f"{self._name}_meter{id}")},
            "name": f"Fronius {self._client.data.get(f'm{id}_model')} {self._client.data.get(f'm{id}_options')}",
            "manufacturer": self._client.data.get(f'm{id}_manufacturer'),
            "model": self._client.data.get(f'm{id}_model'),
            "serial_number": self._client.data.get(f'm{id}_serial'),
            "sw_version": self._client.data.get(f'm{id}_sw_version'),
            #"hw_version": f"modbus id-{self._client.data.get(f'm{id}_unit_id')}",
        }

    @property
    def hub_id(self) -> str:
        """ID for hub."""
        return self._id

    @callback
    def async_add_hub_entity(self, update_callback):
        """Listen for data updates."""
        # This is the first entity, set up interval.
        if not self._entities:
            self._unsub_interval_method = async_track_time_interval(
                self._hass, self.async_refresh_modbus_data, self._scan_interval
            )
        self._entities.append(update_callback)

    @callback
    def async_remove_hub_entity(self, update_callback):
        """Remove data update."""
        self._entities.remove(update_callback)

        if not self._entities:
            """stop the interval timer upon removal of last entity"""
            self._unsub_interval_method()
            self._unsub_interval_method = None
            self.close()

    async def async_refresh_modbus_data(self, _now: Optional[int] = None) -> dict:
        """Time to update."""

        # Timer callbacks should not build a backlog while a control write or a
        # previous slow poll owns the Modbus connection. User-initiated control
        # writes still wait on the lock and are never silently discarded.
        if self._operation_lock.locked():
            _LOGGER.debug("Skipping scheduled refresh while Modbus is busy")
            return False

        async with self._operation_lock:
            return await self._async_refresh_modbus_data()

    async def _async_refresh_modbus_data(self) -> bool:
        """Read all configured models while holding the operation lock."""

        if not self._entities:
            return False

        update_results = []

        try:
            inverter_result = await self._client.read_inverter_data()
            update_results.append(inverter_result)
            self.online = bool(inverter_result)
        except Exception as e:
            _LOGGER.exception("Error reading inverter data", exc_info=True)
            update_results.append(False)
            self.online = False

        try:
            update_results.append(await self._client.read_inverter_status_data())
        except Exception as e:
            _LOGGER.exception("Error reading inverter status data", exc_info=True)
            update_results.append(False)

        try:
            update_results.append(await self._client.read_inverter_model_settings_data())
        except Exception as e:
            _LOGGER.exception("Error reading inverter model settings data", exc_info=True)
            update_results.append(False)

        try:
            update_results.append(await self._client.read_inverter_controls_data())
        except Exception as e:
            _LOGGER.exception("Error reading inverter model settings data", exc_info=True)
            update_results.append(False)

        if self._client.meter_configured:
            for meter_index, meter_address in enumerate(self._client._meter_unit_ids, start=1):
                try:
                    update_results.append(
                        await self._client.read_meter_data(
                            meter_prefix=f"m{meter_index}_", unit_id=meter_address
                        )
                    )
                except Exception as e:
                    _LOGGER.error(f"Error reading meter data {meter_address}.", exc_info=True)
                    update_results.append(False)

        if self._client.mppt_configured:
            try:
                update_results.append(await self._client.read_mppt_data())
            except Exception as e:
                _LOGGER.exception("Error reading mptt data", exc_info=True)
                update_results.append(False)
        
        if self._client.storage_configured:
            try:
                update_results.append(await self._client.read_inverter_storage_data())
            except Exception as e:
                _LOGGER.exception("Error reading inverter storage data", exc_info=True)
                update_results.append(False)


        # Always notify entities so availability and successful partial reads
        # are reflected even if one optional model failed.
        for update_callback in self._entities:
            update_callback()

        return any(update_results)

    @toggle_busy
    async def test_connection(self) -> bool:
        """Test connectivity"""
        try:
            return await self._client.connect()
        except Exception as e:
            _LOGGER.exception("Error connecting to inverter", exc_info=True)
            return False

    def close(self):
        """Disconnect client."""
        #with self._lock:
        self._client.close()

    @property
    def data(self):
        return self._client.data

    @property
    def meter_configured(self):
        return self._client.meter_configured

    @property
    def storage_configured(self):
        return self._client.storage_configured

    @property
    def max_discharge_rate_w(self):
        return self._client.max_discharge_rate_w

    @property
    def max_charge_rate_w(self):
        return self._client.max_charge_rate_w

    @property
    def storage_extended_control_mode(self):
        return self._client.storage_extended_control_mode

    @property
    def pv_control_configured(self) -> bool:
        """Return whether the inverter exposed a usable power-limit block."""
        max_power = self.data.get("max_power")
        return (
            isinstance(max_power, (int, float))
            and not isinstance(max_power, bool)
            and max_power > 0
            and isinstance(self.data.get("WMaxLimPct"), (int, float))
            and self.data.get("WMaxLim_Ena") in ("Disabled", "Enabled")
        )

    @toggle_busy
    async def set_mode(self, mode):
        if mode == 0:
            await self._client.set_auto_mode()
        elif mode == 1:
            await self._client.set_charge_mode()
        elif mode == 2:
            await self._client.set_discharge_mode()
        elif mode == 3:
            await self._client.set_charge_discharge_mode()
        elif mode == 4:
            await self._client.set_grid_charge_mode()
        elif mode == 5:
            await self._client.set_grid_discharge_mode()
        elif mode == 6:
            await self._client.set_block_discharge_mode()
        elif mode == 7:
            await self._client.set_block_charge_mode()
        elif mode == 8:
            await self._client.set_calibrate_mode()

    @toggle_busy
    async def set_minimum_reserve(self, value):
        await self._client.set_minimum_reserve(value)

    @toggle_busy
    async def set_charge_limit(self, value):
        await self._client.set_charge_limit(value)

    @toggle_busy
    async def set_discharge_limit(self, value):
        await self._client.set_discharge_limit(value)

    @toggle_busy
    async def set_grid_charge_power(self, value):
        await self._client.set_grid_charge_power(value)
           
    @toggle_busy
    async def set_grid_discharge_power(self, value):
        await self._client.set_grid_discharge_power(value)

    @toggle_busy
    async def set_pv_output_limit_w(self, value):
        """Set the inverter output ceiling in watts."""
        await self._client.set_pv_output_limit_w(value)
        self._notify_entities()

    @toggle_busy
    async def set_pv_limit_enabled(self, enabled: bool):
        """Enable a configured output ceiling or return to automatic output."""
        await self._client.set_pv_limit_enabled(enabled)
        self._notify_entities()

    def _notify_entities(self):
        """Push locally verified control state to all entities."""
        for update_callback in self._entities:
            update_callback()
