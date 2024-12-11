"""Fronius Modbus Hub."""
from __future__ import annotations

import asyncio
import threading
import logging
import operator
import threading
from datetime import timedelta
from typing import Optional
#import sys
#sys.set_int_max_str_digits(0)

#import homeassistant.helpers.config_validation as cv
#from homeassistant.config_entries import ConfigEntry
#from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
#from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.core import HomeAssistant

from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

from .const import (
    DOMAIN,
    INVERTER_ADDRESS,
    MPPT_ADDRESS,
    BASE_INFO_ADDRESS,
    STORAGE_INFO_ADDRESS,
    STORAGE_CONTROL_MODE_ADDRESS,
    MINIMUM_RESERVE_ADDRESS,
    DISCHARGE_RATE_ADDRESS,
    CHARGE_RATE_ADDRESS,    
    STORAGE_CONTROL_MODE,
    CHARGE_STATUS,
    CHARGE_GRID_STATUS,
    ATTR_MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

class Hub:
    """Hub for Fronius Battery Storage Modbus Interface"""

    manufacturer = "Fronius"

    def __init__(self, hass: HomeAssistant, name: str, host: str, port: int, address: int, meter_addresses, storage_addresses, scan_interval: int) -> None:
        """Init hub."""
        self._host = host
        self._port = port
        self._hass = hass
        self._name = name
        self._inverter_address = address
        self._meter_addresses = meter_addresses
        self._storage_addresses = storage_addresses
        self._lock = threading.Lock()
        self._id = f'{name.lower()}_{host.lower().replace('.','')}'
        self.online = True        
        self._client = ModbusTcpClient(host=host, port=port, timeout=max(3, (scan_interval - 1)))
        self._scan_interval = timedelta(seconds=scan_interval)
        self._unsub_interval_method = None
        self._entities = []
        self.data = {}
        self.data['reserve_target'] = 30
        self.meter_configured = False
        self.storage_configured = False

        try: 
            result = self.read_device_info_data(prefix='i_', address=address)
        except Exception as e:
            _LOGGER.error(f"Error reading inverter info {host}:{port} {address}")
            raise Exception(f"Error reading inverter info {address}")
        if result == False:
            _LOGGER.error(f"Empty inverter info {host}:{port} {address}")
            raise Exception(f"Empty inverter info {address}")
    
        i = 1
        if len(meter_addresses)>5:
            _LOGGER.error(f"Too many meters configured, max 5")
            return
        elif len(meter_addresses)>0:
            self.meter_configured = True

        for meter_address in meter_addresses:
            try:
                self.read_device_info_data(prefix=f'm{i}_', address=meter_address)
            except Exception as e:
                _LOGGER.info(f"Error reading meter info {meter_address}")
            i += 1

        i = 1
        if len(storage_addresses)>2:
            _LOGGER.error(f"Too many storages configured, max 2")
            return
        elif len(storage_addresses)>0:
            self.storage_configured = True

        for storage_address in storage_addresses:
            try:
                prefix = f's{i}_'
                #self.read_device_info_data(prefix=f's{i}_', address=storage_address)
                self.data[prefix + 'address'] = storage_address
            except Exception as e:
                _LOGGER.info(f"Error reading storage info {storage_address}")

    @property 
    def device_info_storage(self) -> dict:
        return {
            "identifiers": {(DOMAIN, f'{self._name}_battery_storage')},
            "name": f'Battery Storage',
            "manufacturer": ATTR_MANUFACTURER,
            "hw_version": f'modbus id-{self.data.get('s1_address')}',
        }

    @property 
    def device_info_inverter(self) -> dict:
        return {
            "identifiers": {(DOMAIN, f'{self._name}_inverter')},
            "name": f'Inverter',
            "manufacturer": self.data.get('i_manufacturer'),
            "model": self.data.get('i_model'),
            "serial_number": self.data.get('i_serial'),
            "sw_version": self.data.get('i_sw_version'),
            "hw_version": f'modbus id-{self.data.get('i_address')}',
        }
    
    def get_device_info_meter(self, id) -> dict:
         return {
            "identifiers": {(DOMAIN, f'{self._name}_meter{id}')},
            "name": f'Meter {id}',
            "manufacturer": self.data.get(f'm{id}_manufacturer'),
            "model": self.data.get(f'm{id}_model'),
            "serial_number": self.data.get(f'm{id}_serial'),
            "sw_version": self.data.get(f'm{id}_sw_version'),
            "hw_version": f'modbus id-{self.data.get(f'm{id}_address')}',
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
            # self.connect()
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
        result : bool = await self._hass.async_add_executor_job(self._refresh_modbus_data)
        if result:
            #_LOGGER.info("modbus referesh")
            for update_callback in self._entities:
                update_callback()

    def validate(self, value, comparison, against):
        ops = {
            ">": operator.gt,
            "<": operator.lt,
            ">=": operator.ge,
            "<=": operator.le,
            "==": operator.eq,
            "!=": operator.ne,
        }
        if not ops[comparison](value, against):
            raise ValueError(f"Value {value} failed validation ({comparison}{against})")
        return value

    def _refresh_modbus_data(self, _now: Optional[int] = None) -> bool:
        """Time to update."""
        if not self._entities:
            return False

        if not self._check_and_reconnect():
            #if not connected, skip
            return False

        if self.meter_configured:
            for meter_address in self._meter_addresses:
                try:
                    update_result = self.read_meter_data(meter_prefix="m1_", device_address=meter_address)
                except Exception as e:
                    _LOGGER.error(f"Error reading meter data {meter_address}. {e}")
                    #update_result = False
        try:
            update_result = self.read_multiple_mptt_data()
        except Exception as e:
            _LOGGER.exception("Error reading mptt data", exc_info=True)
            update_result = False
            
        if self.storage_configured:
            try:
                update_result = self.read_inverter_storage_data()
            except Exception as e:
                _LOGGER.exception("Error reading storage data", exc_info=True)
                update_result = False
        try:
            update_result = self.read_inverter_data()
        except Exception as e:
            _LOGGER.exception("Error reading inverter data", exc_info=True)
            update_result = False
        return update_result

    async def test_connection(self) -> bool:
        """Test connectivity"""
        try:
            return self.connect()
        except Exception as e:
            _LOGGER.exception("Error connecting to inverter", exc_info=True)
            return False

    def close(self):
        """Disconnect client."""
        with self._lock:
            self._client.close()

    def _check_and_reconnect(self):
        if not self._client.connected:
            _LOGGER.info("modbus client is not connected, trying to reconnect")
            return self.connect()

        return self._client.connected

    def connect(self):
        """Connect client."""
        result = False
        with self._lock:
            result = self._client.connect()

        if result:
            _LOGGER.info("successfully connected to %s:%s",
                            self._client.comm_params.host, self._client.comm_params.port)
        else:
            _LOGGER.warning("not able to connect to %s:%s",
                            self._client.comm_params.host, self._client.comm_params.port)
        return result

    def read_holding_registers(self, device_address, address, count):
        """Read holding registers."""
        _LOGGER.info(f"read registers a: {address} s: {device_address} c {count}")
        with self._lock:
            return self._client.read_holding_registers(
                address=address, count=count, slave=device_address
            )

    def write_registers(self, unit, address, payload):
        """Write registers."""
        _LOGGER.info(f"write registers a: {address} p: {payload}")
        with self._lock:
            return self._client.write_registers(
                address=address, values=payload, slave=unit
            )

    def calculate_value(self, value, sf):
        return value * 10**sf

    def strip_escapes(self, value:str):
        if value is None:
            return
        filter = ''.join([chr(i) for i in range(0, 32)])
        return value.translate(str.maketrans('', '', filter)).strip()

    def read_device_info_data(self, prefix, address):
        data = self.read_holding_registers(
            device_address=address, address=BASE_INFO_ADDRESS, count=65
        )
        if data.isError():
            _LOGGER.error(f"error reading device info {prefix} {address} {BASE_INFO_ADDRESS} 65")
            return False

        decoder = BinaryPayloadDecoder.fromRegisters(
            data.registers, byteorder=Endian.BIG
        )

        manufacturer = self.strip_escapes(decoder.decode_string(32).decode('unicode_escape'))
        model = self.strip_escapes(decoder.decode_string(32).decode('unicode_escape'))
        if prefix == 'm1_':
             name = decoder.decode_string(16).decode('unicode_escape')
        else:
            decoder.skip_bytes(16)
            name = ''
        sw_version = self.strip_escapes(decoder.decode_string(16).decode('unicode_escape'))
        serial = self.strip_escapes(decoder.decode_string(32).decode('unicode_escape'))

        _LOGGER.info(f"manufacturer {manufacturer}")
        _LOGGER.info(f"model {model}")
        _LOGGER.info(f"name {name}")
        _LOGGER.info(f"sw_version {sw_version}")
        _LOGGER.info(f"serial {serial}")

        self.data[prefix + 'manufacturer'] = manufacturer
        self.data[prefix + 'model'] = model
        self.data[prefix + 'sw_version'] = sw_version
        self.data[prefix + 'serial'] = serial
        self.data[prefix + 'address'] = address

        return True

    def read_inverter_data(self):
        inverter_data = self.read_holding_registers(
            device_address=self._inverter_address, address=INVERTER_ADDRESS, count=38
        )
        if inverter_data.isError():
            return False

        decoder = BinaryPayloadDecoder.fromRegisters(
            inverter_data.registers, byteorder=Endian.BIG
        )
        # accurrent = decoder.decode_16bit_uint()
        # accurrenta = decoder.decode_16bit_uint()
        # accurrentb = decoder.decode_16bit_uint()
        # accurrentc = decoder.decode_16bit_uint()
        # accurrentsf = decoder.decode_16bit_int()

        # accurrent = self.calculate_value(accurrent, accurrentsf)
        # accurrenta = self.calculate_value(accurrenta, accurrentsf)
        # accurrentb = self.calculate_value(accurrentb, accurrentsf)
        # accurrentc = self.calculate_value(accurrentc, accurrentsf)

        # self.data["accurrent"] = round(accurrent, abs(accurrentsf))
        # self.data["accurrenta"] = round(accurrenta, abs(accurrentsf))
        # self.data["accurrentb"] = round(accurrentb, abs(accurrentsf))
        # self.data["accurrentc"] = round(accurrentc, abs(accurrentsf))

        # acvoltageab = decoder.decode_16bit_uint()
        # acvoltagebc = decoder.decode_16bit_uint()
        # acvoltageca = decoder.decode_16bit_uint()
        # acvoltagean = decoder.decode_16bit_uint()
        # acvoltagebn = decoder.decode_16bit_uint()
        # acvoltagecn = decoder.decode_16bit_uint()
        # acvoltagesf = decoder.decode_16bit_int()

        # acvoltageab = self.calculate_value(acvoltageab, acvoltagesf)
        # acvoltagebc = self.calculate_value(acvoltagebc, acvoltagesf)
        # acvoltageca = self.calculate_value(acvoltageca, acvoltagesf)
        # acvoltagean = self.calculate_value(acvoltagean, acvoltagesf)
        # acvoltagebn = self.calculate_value(acvoltagebn, acvoltagesf)
        # acvoltagecn = self.calculate_value(acvoltagecn, acvoltagesf)

        # self.data["acvoltageab"] = round(acvoltageab, abs(acvoltagesf))
        # self.data["acvoltagebc"] = round(acvoltagebc, abs(acvoltagesf))
        # self.data["acvoltageca"] = round(acvoltageca, abs(acvoltagesf))
        # self.data["acvoltagean"] = round(acvoltagean, abs(acvoltagesf))
        # self.data["acvoltagebn"] = round(acvoltagebn, abs(acvoltagesf))
        # self.data["acvoltagecn"] = round(acvoltagecn, abs(acvoltagesf))

        decoder.skip_bytes(24)
        acpower = decoder.decode_16bit_int()
        acpowersf = decoder.decode_16bit_int()
        acpower = self.calculate_value(acpower, acpowersf)
        self.data["acpower"] = round(acpower, abs(acpowersf))

        # acfreq = decoder.decode_16bit_uint()
        # acfreqsf = decoder.decode_16bit_int()
        # acfreq = self.calculate_value(acfreq, acfreqsf)
        # self.data["acfreq"] = round(acfreq, abs(acfreqsf))

        # acva = decoder.decode_16bit_int()
        # acvasf = decoder.decode_16bit_int()
        # acva = self.calculate_value(acva, acvasf)
        # self.data["acva"] = round(acva, abs(acvasf))

        # acvar = decoder.decode_16bit_int()
        # acvarsf = decoder.decode_16bit_int()
        # acvar = self.calculate_value(acvar, acvarsf)
        # self.data["acvar"] = round(acvar, abs(acvarsf))

        # acpf = decoder.decode_16bit_int()
        # acpfsf = decoder.decode_16bit_int()
        # acpf = self.calculate_value(acpf, acpfsf)
        # self.data["acpf"] = round(acpf, abs(acpfsf))

        decoder.skip_bytes(16)
        acenergy = decoder.decode_32bit_uint()
        acenergysf = decoder.decode_16bit_int()
        acenergy = self.calculate_value(acenergy, acenergysf)
        self.data["acenergy"] = acenergy 

        #dccurrent = decoder.decode_16bit_uint()
        #dccurrentsf = decoder.decode_16bit_int()
        #dccurrent = self.calculate_value(dccurrent, dccurrentsf)
        #self.data["dccurrent"] = round(dccurrent, abs(dccurrentsf))

        #dcvoltage = decoder.decode_16bit_uint()
        #dcvoltagesf = decoder.decode_16bit_int()
        #dcvoltage = self.calculate_value(dcvoltage, dcvoltagesf)
        #self.data["dcvoltage"] = round(dcvoltage, abs(dcvoltagesf))

        #dcpower = decoder.decode_16bit_int()
        #dcpowersf = decoder.decode_16bit_int()
        #dcpower = self.calculate_value(dcpower, dcpowersf)
        #self.data["dcpower"] = round(dcpower, abs(dcpowersf))

        decoder.skip_bytes(12)
        tempcab = decoder.decode_16bit_int()
        decoder.skip_bytes(6)
        tempsf = decoder.decode_16bit_int()
        tempcab = self.calculate_value(tempcab, tempsf)
        self.data['tempcab'] = tempcab
        #_LOGGER.info(f"tempcab {tempcab}")

        status = decoder.decode_16bit_int()
        self.data["status"] = status
        statusvendor = decoder.decode_16bit_int()
        self.data["statusvendor"] = statusvendor

        return True

    def read_multiple_mptt_data(self):

        data = self.read_holding_registers(
            device_address=self._inverter_address, address=MPPT_ADDRESS, count=88
        )
        if data.isError():
            _LOGGER.error(f"modbus mppt error {data}")
            return False

        decoder = BinaryPayloadDecoder.fromRegisters(
            data.registers, byteorder=Endian.BIG
        )

        #_LOGGER.info(f"registers {data.registers}")

        #dca_sf - 1
        #dcv_sf - 1
        decoder.skip_bytes(4)    
        dcw_sf = decoder.decode_16bit_int()
        dcwh_sf = decoder.decode_16bit_int()
        #Evt - 2
        decoder.skip_bytes(4)    
        modules = decoder.decode_16bit_int()
        #_LOGGER.info(f"modules {modules}")
        if modules != 4:
            _LOGGER.error(f"Integration only supports 4 mppt modules. Found only: {modules}")
            return

        #TmsPer - 1
        #module/1/ID - 1
        #module/1/IDStr - 8
        #module/1/DCA - 1
        #module/1/DCV - 1
        decoder.skip_bytes(24)    
        mppt1_power = decoder.decode_16bit_uint()
        mppt1_lfte = decoder.decode_32bit_uint()
        #module/1/Tms - 2
        #module/1/Tmp not supported - 1
        #module/1/DCSt not supported - 1
        #module/1/DCEvt not supported - 2

        #module/2/ID - 1
        #module/2/IDStr - 8
        #module/2/DCA - 1
        #module/2/DCV - 1
        decoder.skip_bytes(34)
        mppt2_power = decoder.decode_16bit_uint()
        mppt2_lfte = decoder.decode_32bit_uint()

        decoder.skip_bytes(34)
        mppt3_power = decoder.decode_16bit_uint()
        mppt3_lfte = decoder.decode_32bit_uint()

        decoder.skip_bytes(34)
        mppt4_power = decoder.decode_16bit_uint()
        mppt4_lfte = decoder.decode_32bit_uint()

        mppt1_power = self.calculate_value(mppt1_power, dcw_sf)
        mppt2_power = self.calculate_value(mppt2_power, dcw_sf)
        mppt3_power = self.calculate_value(mppt3_power, dcw_sf)
        mppt4_power = self.calculate_value(mppt4_power, dcw_sf)

        mppt1_lfte = self.calculate_value(mppt1_lfte, dcwh_sf)
        mppt2_lfte = self.calculate_value(mppt2_lfte, dcwh_sf)
        mppt3_lfte = self.calculate_value(mppt3_lfte, dcwh_sf)
        mppt4_lfte = self.calculate_value(mppt4_lfte, dcwh_sf)

        self.data['mppt1_power'] = mppt1_power
        self.data['mppt2_power'] = mppt2_power
        self.data['mppt3_power'] = mppt3_power
        self.data['mppt4_power'] = mppt4_power
        self.data['pv_power'] = mppt1_power + mppt2_power
        self.data['storage_power'] = mppt4_power - mppt3_power

        self.data['mppt1_lfte'] = mppt1_lfte
        self.data['mppt2_lfte'] = mppt2_lfte
        self.data['mppt3_lfte'] = mppt3_lfte
        self.data['mppt4_lfte'] = mppt4_lfte

        #_LOGGER.info(f"mppt {mppt1_power} {mppt2_power} {mppt3_power} {mppt4_power}")

        return True

    def read_inverter_storage_data(self):
        """start reading storage data"""
        address = STORAGE_INFO_ADDRESS
        data = self.read_holding_registers(
            device_address=self._inverter_address, address=address, count=24
        )
        if data.isError():
            _LOGGER.error(f"modbus storage error {data}")
            return False

        decoder = BinaryPayloadDecoder.fromRegisters(
            data.registers, byteorder=Endian.BIG
        )

        # WChaMax
        max_charge = decoder.decode_16bit_int()
        # WChaGra
        power = decoder.decode_16bit_int()
        # WDisChaGra
        dummy3 = decoder.decode_16bit_int()
        # StorCtl_Mod
        storage_control_mode = decoder.decode_16bit_int()
        # VAChaMax
        decoder.skip_bytes(2) # not supported 
        # MinRsvPct
        minimum_reserve = decoder.decode_16bit_int()
        # ChaState
        charge_state = decoder.decode_16bit_int()
        # StorAval
        decoder.skip_bytes(2) # not supported 
        # InBatV
        decoder.skip_bytes(2) # not supported 
        # ChaSt
        charge_status = decoder.decode_16bit_int()
        # OutWRte
        discharge_power = decoder.decode_16bit_int()
        # InWRte
        charge_power = decoder.decode_16bit_int()
        # InOutWRte_WinTms
        decoder.skip_bytes(2) # not supported 
        # InOutWRte_RvrtTms
        dummy10 = decoder.decode_16bit_int()
        # InOutWRte_RmpTms
        decoder.skip_bytes(2) # not supported 
        # ChaGriSet
        charge_grid_set = decoder.decode_16bit_int()
        # WChaMax_SF
        max_charge_sf = decoder.decode_16bit_int()
        # WChaDisChaGra_SF
        dummy10 = decoder.decode_16bit_int()
        # VAChaMax_SF
        decoder.skip_bytes(2) # not supported 
        # MinRsvPct_SF
        dummy10 = decoder.decode_16bit_int()
        # ChaState_SF
        charge_state_sf = decoder.decode_16bit_int()
        # StorAval_SF
        #decoder.skip_bytes(2) # not supported 
        # InBatV_SF
        #decoder.skip_bytes(2) # not supported 
        # InOutWRte_SF

        self.data['grid_charging'] = CHARGE_GRID_STATUS.get(charge_grid_set)
        self.data['power'] = power
        self.data['charge_status'] = CHARGE_STATUS.get(charge_status)
        self.data['minimum_reserve'] = minimum_reserve / 100.0
        self.data['discharging_power'] = discharge_power / 100.0
        self.data['charging_power'] = charge_power / 100.0
        self.data['soc'] = self.calculate_value(charge_state, charge_state_sf)
        self.data['max_charge'] = self.calculate_value(max_charge, max_charge_sf)

        control_mode = self.data.get('control_mode')
        if control_mode is None or control_mode != STORAGE_CONTROL_MODE.get(storage_control_mode):
            if discharge_power >= 0:
                self.data['discharge_limit'] = discharge_power / 100.0
                self.data['grid_charge_power'] = 0
            else: 
                self.data['grid_charge_power'] = (discharge_power * -1) / 100.0
                self.data['discharge_limit'] = 0
            self.data['charge_limit'] = charge_power / 100

            self.data['control_mode'] = STORAGE_CONTROL_MODE.get(storage_control_mode)

        if self.meter_configured:
            if not self.data.get('m1_power') is None and not self.data.get('acpower') is None:
                self.data['load'] = self.data['m1_power'] +  self.data['acpower']
        return True

    def read_meter1_data(self):
        if self.meter_configured:
            return self.read_meter_data(meter_prefix="m1_", device_address=200)
        return True

    def read_meter_data(self, meter_prefix, device_address):
        """start reading meter  data"""
        meter_data = self.read_holding_registers(
            device_address=device_address, address=INVERTER_ADDRESS, count=103
        )
        if meter_data.isError():
            return False

        decoder = BinaryPayloadDecoder.fromRegisters(
            meter_data.registers, byteorder=Endian.BIG
        )
        # accurrent = decoder.decode_16bit_int()
        # accurrenta = decoder.decode_16bit_int()
        # accurrentb = decoder.decode_16bit_int()
        # accurrentc = decoder.decode_16bit_int()
        # accurrentsf = decoder.decode_16bit_int()

        # accurrent = self.calculate_value(accurrent, accurrentsf)
        # accurrenta = self.calculate_value(accurrenta, accurrentsf)
        # accurrentb = self.calculate_value(accurrentb, accurrentsf)
        # accurrentc = self.calculate_value(accurrentc, accurrentsf)

        # self.data[meter_prefix + "accurrent"] = round(accurrent, abs(accurrentsf))
        # self.data[meter_prefix + "accurrenta"] = round(accurrenta, abs(accurrentsf))
        # self.data[meter_prefix + "accurrentb"] = round(accurrentb, abs(accurrentsf))
        # self.data[meter_prefix + "accurrentc"] = round(accurrentc, abs(accurrentsf))

        # acvoltageln = decoder.decode_16bit_int()
        # acvoltagean = decoder.decode_16bit_int()
        # acvoltagebn = decoder.decode_16bit_int()
        # acvoltagecn = decoder.decode_16bit_int()
        # acvoltagell = decoder.decode_16bit_int()
        # acvoltageab = decoder.decode_16bit_int()
        # acvoltagebc = decoder.decode_16bit_int()
        # acvoltageca = decoder.decode_16bit_int()
        # acvoltagesf = decoder.decode_16bit_int()

        # acvoltageln = self.calculate_value(acvoltageln, acvoltagesf)
        # acvoltagean = self.calculate_value(acvoltagean, acvoltagesf)
        # acvoltagebn = self.calculate_value(acvoltagebn, acvoltagesf)
        # acvoltagecn = self.calculate_value(acvoltagecn, acvoltagesf)
        # acvoltagell = self.calculate_value(acvoltagell, acvoltagesf)
        # acvoltageab = self.calculate_value(acvoltageab, acvoltagesf)
        # acvoltagebc = self.calculate_value(acvoltagebc, acvoltagesf)
        # acvoltageca = self.calculate_value(acvoltageca, acvoltagesf)

        # self.data[meter_prefix + "acvoltageln"] = round(acvoltageln, abs(acvoltagesf))
        # self.data[meter_prefix + "acvoltagean"] = round(acvoltagean, abs(acvoltagesf))
        # self.data[meter_prefix + "acvoltagebn"] = round(acvoltagebn, abs(acvoltagesf))
        # self.data[meter_prefix + "acvoltagecn"] = round(acvoltagecn, abs(acvoltagesf))
        # self.data[meter_prefix + "acvoltagell"] = round(acvoltagell, abs(acvoltagesf))
        # self.data[meter_prefix + "acvoltageab"] = round(acvoltageab, abs(acvoltagesf))
        # self.data[meter_prefix + "acvoltagebc"] = round(acvoltagebc, abs(acvoltagesf))
        # self.data[meter_prefix + "acvoltageca"] = round(acvoltageca, abs(acvoltagesf))

        # acfreq = decoder.decode_16bit_int()
        # acfreqsf = decoder.decode_16bit_int()
        # acfreq = self.calculate_value(acfreq, acfreqsf)
        # self.data[meter_prefix + "acfreq"] = round(acfreq, abs(acfreqsf))

        decoder.skip_bytes(32)
        acpower = decoder.decode_16bit_int()
        # acpowera = decoder.decode_16bit_int()
        # acpowerb = decoder.decode_16bit_int()
        # acpowerc = decoder.decode_16bit_int()
        decoder.skip_bytes(6)
        acpowersf = decoder.decode_16bit_int()

        acpower = self.calculate_value(acpower, acpowersf)
        # acpowera = self.calculate_value(acpowera, acpowersf)
        # acpowerb = self.calculate_value(acpowerb, acpowersf)
        # acpowerc = self.calculate_value(acpowerc, acpowersf)

        #_LOGGER.info(f"m1 {acpower}")
        self.data[meter_prefix + "power"] = round(acpower, abs(acpowersf))
        # self.data[meter_prefix + "acpowera"] = round(acpowera, abs(acpowersf))
        # self.data[meter_prefix + "acpowerb"] = round(acpowerb, abs(acpowersf))
        # self.data[meter_prefix + "acpowerc"] = round(acpowerc, abs(acpowersf))

        # acva = decoder.decode_16bit_int()
        # acvaa = decoder.decode_16bit_int()
        # acvab = decoder.decode_16bit_int()
        # acvac = decoder.decode_16bit_int()
        # acvasf = decoder.decode_16bit_int()

        # acva = self.calculate_value(acva, acvasf)
        # acvaa = self.calculate_value(acvaa, acvasf)
        # acvab = self.calculate_value(acvab, acvasf)
        # acvac = self.calculate_value(acvac, acvasf)

        # self.data[meter_prefix + "acva"] = round(acva, abs(acvasf))
        # self.data[meter_prefix + "acvaa"] = round(acvaa, abs(acvasf))
        # self.data[meter_prefix + "acvab"] = round(acvab, abs(acvasf))
        # self.data[meter_prefix + "acvac"] = round(acvac, abs(acvasf))

        # acvar = decoder.decode_16bit_int()
        # acvara = decoder.decode_16bit_int()
        # acvarb = decoder.decode_16bit_int()
        # acvarc = decoder.decode_16bit_int()
        # acvarsf = decoder.decode_16bit_int()

        # acvar = self.calculate_value(acvar, acvarsf)
        # acvara = self.calculate_value(acvara, acvarsf)
        # acvarb = self.calculate_value(acvarb, acvarsf)
        # acvarc = self.calculate_value(acvarc, acvarsf)

        # self.data[meter_prefix + "acvar"] = round(acvar, abs(acvarsf))
        # self.data[meter_prefix + "acvara"] = round(acvara, abs(acvarsf))
        # self.data[meter_prefix + "acvarb"] = round(acvarb, abs(acvarsf))
        # self.data[meter_prefix + "acvarc"] = round(acvarc, abs(acvarsf))

        # acpf = decoder.decode_16bit_int()
        # acpfa = decoder.decode_16bit_int()
        # acpfb = decoder.decode_16bit_int()
        # acpfc = decoder.decode_16bit_int()
        # acpfsf = decoder.decode_16bit_int()

        # acpf = self.calculate_value(acpf, acpfsf)
        # acpfa = self.calculate_value(acpfa, acpfsf)
        # acpfb = self.calculate_value(acpfb, acpfsf)
        # acpfc = self.calculate_value(acpfc, acpfsf)

        # self.data[meter_prefix + "acpf"] = round(acpf, abs(acpfsf))
        # self.data[meter_prefix + "acpfa"] = round(acpfa, abs(acpfsf))
        # self.data[meter_prefix + "acpfb"] = round(acpfb, abs(acpfsf))
        # self.data[meter_prefix + "acpfc"] = round(acpfc, abs(acpfsf))

        decoder.skip_bytes(30)
        exported = decoder.decode_32bit_uint()
        # exporteda = decoder.decode_32bit_uint()
        # exportedb = decoder.decode_32bit_uint()
        # exportedc = decoder.decode_32bit_uint()
        decoder.skip_bytes(12)
        imported = decoder.decode_32bit_uint()
        # importeda = decoder.decode_32bit_uint()
        # importedb = decoder.decode_32bit_uint()
        # importedc = decoder.decode_32bit_uint()
        decoder.skip_bytes(12)
        energywsf = decoder.decode_16bit_int()

        exported = self.calculate_value(exported, energywsf) #self.validate(self.calculate_value(exported, energywsf), ">", 0)
        # exporteda = self.calculate_value(exporteda, energywsf)
        # exportedb = self.calculate_value(exportedb, energywsf)
        # exportedc = self.calculate_value(exportedc, energywsf)
        imported = self.calculate_value(imported, energywsf) #self.validate(self.calculate_value(imported, energywsf), ">", 0)
        # importeda = self.calculate_value(importeda, energywsf)
        # importedb = self.calculate_value(importedb, energywsf)
        # importedc = self.calculate_value(importedc, energywsf)

        # _LOGGER.info(f"m1 exp {exported}")
        # _LOGGER.info(f"m1 imp {imported}")

        self.data[meter_prefix + "exported"] = exported #round(exported * 0.001, 3)
        # self.data[meter_prefix + "exporteda"] = round(exporteda * 0.001, 3)
        # self.data[meter_prefix + "exportedb"] = round(exportedb * 0.001, 3)
        # self.data[meter_prefix + "exportedc"] = round(exportedc * 0.001, 3)
        self.data[meter_prefix + "imported"] = imported #round(imported * 0.001, 3)
        # self.data[meter_prefix + "importeda"] = round(importeda * 0.001, 3)
        # self.data[meter_prefix + "importedb"] = round(importedb * 0.001, 3)
        # self.data[meter_prefix + "importedc"] = round(importedc * 0.001, 3)

        # exportedva = decoder.decode_32bit_uint()
        # exportedvaa = decoder.decode_32bit_uint()
        # exportedvab = decoder.decode_32bit_uint()
        # exportedvac = decoder.decode_32bit_uint()
        # importedva = decoder.decode_32bit_uint()
        # importedvaa = decoder.decode_32bit_uint()
        # importedvab = decoder.decode_32bit_uint()
        # importedvac = decoder.decode_32bit_uint()
        # energyvasf = decoder.decode_16bit_int()

        # exportedva = self.calculate_value(exportedva, energyvasf)
        # exportedvaa = self.calculate_value(exportedvaa, energyvasf)
        # exportedvab = self.calculate_value(exportedvab, energyvasf)
        # exportedvac = self.calculate_value(exportedvac, energyvasf)
        # importedva = self.calculate_value(importedva, energyvasf)
        # importedvaa = self.calculate_value(importedvaa, energyvasf)
        # importedvab = self.calculate_value(importedvab, energyvasf)
        # importedvac = self.calculate_value(importedvac, energyvasf)

        # self.data[meter_prefix + "exportedva"] = round(exportedva, abs(energyvasf))
        # self.data[meter_prefix + "exportedvaa"] = round(exportedvaa, abs(energyvasf))
        # self.data[meter_prefix + "exportedvab"] = round(exportedvab, abs(energyvasf))
        # self.data[meter_prefix + "exportedvac"] = round(exportedvac, abs(energyvasf))
        # self.data[meter_prefix + "importedva"] = round(importedva, abs(energyvasf))
        # self.data[meter_prefix + "importedvaa"] = round(importedvaa, abs(energyvasf))
        # self.data[meter_prefix + "importedvab"] = round(importedvab, abs(energyvasf))
        # self.data[meter_prefix + "importedvac"] = round(importedvac, abs(energyvasf))

        # importvarhq1 = decoder.decode_32bit_uint()
        # importvarhq1a = decoder.decode_32bit_uint()
        # importvarhq1b = decoder.decode_32bit_uint()
        # importvarhq1c = decoder.decode_32bit_uint()
        # importvarhq2 = decoder.decode_32bit_uint()
        # importvarhq2a = decoder.decode_32bit_uint()
        # importvarhq2b = decoder.decode_32bit_uint()
        # importvarhq2c = decoder.decode_32bit_uint()
        # importvarhq3 = decoder.decode_32bit_uint()
        # importvarhq3a = decoder.decode_32bit_uint()
        # importvarhq3b = decoder.decode_32bit_uint()
        # importvarhq3c = decoder.decode_32bit_uint()
        # importvarhq4 = decoder.decode_32bit_uint()
        # importvarhq4a = decoder.decode_32bit_uint()
        # importvarhq4b = decoder.decode_32bit_uint()
        # importvarhq4c = decoder.decode_32bit_uint()
        # energyvarsf = decoder.decode_16bit_int()

        # importvarhq1 = self.calculate_value(importvarhq1, energyvarsf)
        # importvarhq1a = self.calculate_value(importvarhq1a, energyvarsf)
        # importvarhq1b = self.calculate_value(importvarhq1b, energyvarsf)
        # importvarhq1c = self.calculate_value(importvarhq1c, energyvarsf)
        # importvarhq2 = self.calculate_value(importvarhq2, energyvarsf)
        # importvarhq2a = self.calculate_value(importvarhq2a, energyvarsf)
        # importvarhq2b = self.calculate_value(importvarhq2b, energyvarsf)
        # importvarhq2c = self.calculate_value(importvarhq2c, energyvarsf)
        # importvarhq3 = self.calculate_value(importvarhq3, energyvarsf)
        # importvarhq3a = self.calculate_value(importvarhq3a, energyvarsf)
        # importvarhq3b = self.calculate_value(importvarhq3b, energyvarsf)
        # importvarhq3c = self.calculate_value(importvarhq3c, energyvarsf)
        # importvarhq4 = self.calculate_value(importvarhq4, energyvarsf)
        # importvarhq4a = self.calculate_value(importvarhq4a, energyvarsf)
        # importvarhq4b = self.calculate_value(importvarhq4b, energyvarsf)
        # importvarhq4c = self.calculate_value(importvarhq4c, energyvarsf)

        # self.data[meter_prefix + "importvarhq1"] = round(importvarhq1, abs(energyvarsf))
        # self.data[meter_prefix + "importvarhq1a"] = round(
        #     importvarhq1a, abs(energyvarsf)
        # )
        # self.data[meter_prefix + "importvarhq1b"] = round(
        #     importvarhq1b, abs(energyvarsf)
        # )
        # self.data[meter_prefix + "importvarhq1c"] = round(
        #     importvarhq1c, abs(energyvarsf)
        # )
        # self.data[meter_prefix + "importvarhq2"] = round(importvarhq2, abs(energyvarsf))
        # self.data[meter_prefix + "importvarhq2a"] = round(
        #     importvarhq2a, abs(energyvarsf)
        # )
        # self.data[meter_prefix + "importvarhq2b"] = round(
        #     importvarhq2b, abs(energyvarsf)
        # )
        # self.data[meter_prefix + "importvarhq2c"] = round(
        #     importvarhq2c, abs(energyvarsf)
        # )
        # self.data[meter_prefix + "importvarhq3"] = round(importvarhq3, abs(energyvarsf))
        # self.data[meter_prefix + "importvarhq3a"] = round(
        #     importvarhq3a, abs(energyvarsf)
        # )
        # self.data[meter_prefix + "importvarhq3b"] = round(
        #     importvarhq3b, abs(energyvarsf)
        # )
        # self.data[meter_prefix + "importvarhq3c"] = round(
        #     importvarhq3c, abs(energyvarsf)
        # )
        # self.data[meter_prefix + "importvarhq4"] = round(importvarhq4, abs(energyvarsf))
        # self.data[meter_prefix + "importvarhq4a"] = round(
        #     importvarhq4a, abs(energyvarsf)
        # )
        # self.data[meter_prefix + "importvarhq4b"] = round(
        #     importvarhq4b, abs(energyvarsf)
        # )
        # self.data[meter_prefix + "importvarhq4c"] = round(
        #     importvarhq4c, abs(energyvarsf)
        # )

        return True

    def set_storage_control_mode(self, mode):
        self.write_registers(unit=self._device_address, address=STORAGE_CONTROL_MODE_ADDRESS, payload=mode)

    def set_minimum_reserve(self, minimum_reserve):
        minimum_reserve = round(minimum_reserve * 100)
        self.write_registers(unit=self._device_address, address=MINIMUM_RESERVE_ADDRESS, payload=minimum_reserve)

    def set_discharge_rate(self, discharge_rate):
        if discharge_rate < 0:
            discharge_rate =  int(65536 + (discharge_rate * 100))
        else:
            discharge_rate = int(round(discharge_rate * 100))
        self.write_registers(unit=self._device_address, address=DISCHARGE_RATE_ADDRESS, payload=discharge_rate)

    def set_charge_rate(self, charge_rate):
        charge_rate = int(round(charge_rate * 100))
        self.write_registers(unit=self._device_address, address=CHARGE_RATE_ADDRESS, payload=charge_rate)

    def restore_defaults(self):
        self.set_storage_control_mode(0)
        self.set_minimum_reserve(7)
        self.set_discharge_rate(100)
        self.set_charge_rate(100)
        _LOGGER.info(f"restored defaults")

    def block_discharging(self):
        self.set_storage_control_mode(2)
        self.set_discharge_rate(0)
        self.set_charge_rate(100)
        self.set_minimum_reserve(30)
        _LOGGER.info(f"blocked discharging")

    def force_charging(self):
        grid_charge_power = self.data.get('grid_charge_power')
        _LOGGER.info(f"{grid_charge_power}")
        if grid_charge_power is None:
            _LOGGER.error(f'Grid Charge Power not set')
            return
        self.set_storage_control_mode(2)        
        self.set_discharge_rate(grid_charge_power * -1) # charge = negative discharge
        self.set_minimum_reserve(99)
        _LOGGER.info(f"Forced charging at {grid_charge_power}")

    def limit_discharging(self):
        discharge_rate = self.data.get('discharge_limit')
        _LOGGER.info(f"{discharge_rate}")
        if discharge_rate is None:
            _LOGGER.error(f'Discharge Rate not set')
            return
        self.set_storage_control_mode(2)
        self.set_discharge_rate(discharge_rate)
        self.set_minimum_reserve(30)
        _LOGGER.info(f"Discharging limited to {discharge_rate}")

    def discharging_only(self):
        discharge_rate = 100 
        _LOGGER.info(f"{discharge_rate}")
        if discharge_rate is None:
            _LOGGER.error(f'Discharge Rate not set')
            return
        self.set_storage_control_mode(1)
        self.set_discharge_rate(discharge_rate) # not relevant ?
        self.set_charge_rate(0)
        self.set_minimum_reserve(30)
        _LOGGER.info(f"Allow only discharging at {discharge_rate}")

    def auto_30(self):
        self.set_storage_control_mode(0)
        self.set_minimum_reserve(30)
        self.set_discharge_rate(100)
        self.set_charge_rate(100)
        _LOGGER.info(f"Auto mode with 30% min")
