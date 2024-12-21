from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.entity import EntityCategory

DOMAIN = "fronius_modbus"
CONNECTION_MODBUS = "modbus"
DEFAULT_NAME = "Fronius"
ENTITY_PREFIX = "fm"
DEFAULT_SCAN_INTERVAL = 10
DEFAULT_PORT = 502
DEFAULT_INVERTER_UNIT_ID = 1
DEFAULT_METER_UNIT_ID = 200
CONF_INVERTER_UNIT_ID = "inverter_modbus_unit_id"
CONF_METER_UNIT_ID = "meter_modbus_unit_id"
ATTR_MANUFACTURER = "Fronius"
SUPPORTED_MANUFACTURERS = ['Fronius']
SUPPORTED_MODELS = ['Primo GEN24', 'Symo GEN24']

BASE_INFO_ADDRESS = 40004
INVERTER_ADDRESS = 40071
MPPT_ADDRESS = 40255
STORAGE_INFO_ADDRESS = 40345
STORAGE_CONTROL_MODE_ADDRESS = 40348
MINIMUM_RESERVE_ADDRESS = 40350
DISCHARGE_RATE_ADDRESS = 40355
CHARGE_RATE_ADDRESS = 40356

    # Manufacturer
    # Type
    # Firmware
    # Serial

INVERTER_SENSOR_TYPES = {
    "acpower": ["AC Power", "acpower", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:lightning-bolt", None],
    "acenergy": ["AC Energy", "acenergy", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:lightning-bolt", None],
    "tempcab": ["Temperature", "tempcab", SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, "°C", "mdi:thermometer", None],
    "mppt1_power": ["MPPT1 Power", "mppt1_power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:solar-power", None],
    "mppt2_power": ["MPPT2 Power", "mppt2_power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:solar-power", None],
    "mppt3_power": ["Storage Charging Power", "mppt3_power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:home-battery", None],
    "mppt4_power": ["Storage Discharging Power", "mppt4_power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:home-battery", None],
    "pv_power": ["PV Power", "pv_power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:solar-power", None],
    "storage_power": ["Storage Power", "storage_power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:home-battery", None],
    "mppt1_lfte": ["MPPT1 Lifetime Energy", "mppt1_lfte", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:solar-panel", None],
    "mppt2_lfte": ["MPPT2 Lifetime Energy", "mppt2_lfte", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:solar-panel", None],
    "mppt3_lfte": ["Storage Charging Lifetime Energy", "mppt3_lfte", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:home-battery", None],
    "mppt4_lfte": ["Storage Discharging Lifetime Energy", "mppt4_lfte", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:home-battery", None],
    "load": ["Load", "load", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:lightning-bolt", None],
    "unit_id": ["Modbus ID", "i_unit_id", None, None, None, None, EntityCategory.DIAGNOSTIC],
}

METER_SENSOR_TYPES = {
    "power": ["Power", "power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:lightning-bolt", None],
    "exported": ["Exported", "exported", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:lightning-bolt", None],
    "imported": ["Imported", "imported", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:lightning-bolt", None],
    "unit_id": ["Modbus ID", "unit_id", None, None, None, None, EntityCategory.DIAGNOSTIC],
}

STORAGE_SENSOR_TYPES = {
    "control_mode": ["Core Storage Control Mode", "control_mode", None, None, None, None, EntityCategory.DIAGNOSTIC],
    "charge_status": ["Charge Status", "charge_status", None, None, None, None, None, None],
    "max_charge": ["Max Charging Power", "max_charge", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:gauge", EntityCategory.DIAGNOSTIC],
    "soc": ["State of Charge", "soc", None, SensorStateClass.MEASUREMENT, "%", "mdi:battery", None],
    "charging_power": ["Charging Power", "charging_power",  None, None, "%", "mdi:gauge", EntityCategory.DIAGNOSTIC],
    "discharging_power": ["Discharging Power", "discharging_power",  None, None, "%", "mdi:gauge", EntityCategory.DIAGNOSTIC],
    "minimum_reserve": ["Minimum Reserve", "minimum_reserve",  None, None, "%", "mdi:gauge", None],
    "grid_charging": ["Grid Charging", "grid_charging",  None, None, None, None, EntityCategory.DIAGNOSTIC],
}

STORAGE_CONTROL_MODE = {
    0: "Auto",
    1: "Charge",
    2: "Discharge",
    3: "Change and Discharge",
}

CHARGE_STATUS = {
    1: "Off",
    2: "Empty",
    3: "Discharging",
    4: "Charging",
    5: "Full",
    6: "Holding",
    7: "Testing",
}

CHARGE_GRID_STATUS = {
    1: "Disabled",
    2: "Enabled",
}

STORAGE_EXT_CONTROL_MODE = {
    0: "Auto",
    1: "PV Charge Limit",
    2: "Discharge Limit",
    3: "PV Charge and Discharge Limit",
    4: "Charge from Grid",
    5: "Discharge to Grid",
    6: "Block Discharging",
    7: "Block Charging",
#    8: "Calibrate",
}

STORAGE_SELECT_TYPES = [
    ["Storage Control Mode", "ext_control_mode", STORAGE_EXT_CONTROL_MODE],
]

STORAGE_NUMBER_TYPES = [
    ["Grid Discharge Power", "grid_discharge_power", {"min": 0, "max": 100, "unit": "%"}],
    ["Grid Charge Power", "grid_charge_power", {"min": 0, "max": 100, "unit": "%"}],
    ["Discharge Limit", "discharge_limit",  {"min": 0, "max": 100, "unit": "%"}],
    ["PV Charge Limit", "charge_limit", {"min": 0, "max": 100, "unit": "%"}],
    ["Minimum Reserve", "minimum_reserve", {"min": 5, "max": 100, "unit": "%"}],
#    ["Reserve Target", "reserve_target", {"min": 0, "max": 100, "unit": "%"}],
]