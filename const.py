from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass
)

# This is the internal name of the integration, it should also match the directory
# name for the integration.
DOMAIN = "fronius_modbus"
DEFAULT_NAME = "Fronius"
ENTITY_PREFIX = "fm"
DEFAULT_SCAN_INTERVAL = 10
DEFAULT_PORT = 502
DEFAULT_MODBUS_ADDRESS = 1
CONF_MODBUS_ADDRESS = "modbus_address"
ATTR_MANUFACTURER = "Fronius"

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
    "acpower": ["AC Power", "acpower", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:lightning-bolt"],
    "acenergy": ["AC Energy", "acenergy", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:lightning-bolt"],
    "tempcab": ["Temperature", "tempcab", SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, "°C", "mdi:thermometer"],
    "mppt1_power": ["MPPT1 Power", "mppt1_power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:solar-power"],
    "mppt2_power": ["MPPT2 Power", "mppt2_power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:solar-power"],
    "mppt3_power": ["Storage Charging Power", "mppt3_power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:home-battery"],
    "mppt4_power": ["Storage Discharging Power", "mppt4_power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:home-battery"],
    "pv_power": ["PV Power", "pv_power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:solar-power"],
    "storage_power": ["Storage Power", "storage_power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:home-battery"],
    "mppt1_lfte": ["MPPT1 Lifetime Energy", "mppt1_lfte", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:solar-panel"],
    "mppt2_lfte": ["MPPT2 Lifetime Energy", "mppt2_lfte", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:solar-panel"],
    "mppt3_lfte": ["Storage Charging Lifetime Energy", "mppt3_lfte", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:home-battery"],
    "mppt4_lfte": ["Storage Discharging Lifetime Energy", "mppt4_lfte", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:home-battery"],
    "load": ["Load", "load", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:lightning-bolt"],
}

METER_SENSOR_TYPES = {
    "power": ["Power", "power", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:lightning-bolt"],
    "exported": ["Exported", "exported", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:lightning-bolt"],
    "imported": ["Imported", "imported", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "Wh", "mdi:lightning-bolt"],
}

STORAGE_SENSOR_TYPES = {
    "control_mode": ["Storage Control Mode", "control_mode", None, None, None, None],
    "charge_status": ["Charge Status", "charge_status", None, None, None, None],
    "max_charge": ["Max Charging Power", "max_charge", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "W", "mdi:gauge"],
    "soc": ["State of Charge", "soc", None, SensorStateClass.MEASUREMENT, "%", "mdi:battery"],
    "charging_power": ["Charging Power", "charging_power",  None, None, "%", "mdi:gauge"],
    "discharging_power": ["Discharging Power", "discharging_power",  None, None, "%", "mdi:gauge"],
    "minimum_reserve": ["Minimum Reserve", "minimum_reserve",  None, None, "%", "mdi:gauge"],
    "grid_charging": ["Grid Charging", "grid_charging",  None, None, None, None],
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

STORAGE_CONTROL_ACTIONS = {
    0: "Restore defaults",
    1: "Limit discharging",
    2: "Block discharging",
    3: "Discharging only",
    4: "Charge from Grid",
    5: "Automatic",
}

SELECT_TYPES = [
    ["Storage Control Actions", "control_actions", 0xE000, STORAGE_CONTROL_ACTIONS],
]

NUMBER_TYPES = [
    ["Grid Charge Power", "grid_charge_power", 0xE006, "f", {"min": 0, "max": 100, "unit": "%"}],
    ["Discharge Limit", "discharge_limit", 0xE008, "f", {"min": 0, "max": 100, "unit": "%"}],
    ["Charge Limit", "charge_limit", 0xE00B, "u32", {"min": 0, "max": 100, "unit": "%"}],
    ["Minimum Reserve", "minimum_reserve", 0xE00B, "u32", {"min": 0, "max": 100, "unit": "%"}],
    ["Reserve Target", "reserve_target", 0xE00B, "u32", {"min": 0, "max": 100, "unit": "%"}],
]