DOMAIN = "whes_battery"
DEFAULT_UPDATE_SECONDS = 60

CONF_API_KEY = "api_key"
CONF_API_SECRET = "api_secret"
CONF_PROJECT_ID = "project_id"
CONF_DEVICE_ID = "device_id"
CONF_AMMETER_ID = "ammeter_id"
CONF_BASE_URL = "base_url"

DEFAULT_BASE_URL = "https://open-api-eu.weiheng-tech.com/open-api"
PLATFORMS = ["sensor"]

SENSOR_MAP = {
    # EMS
    "ems_soc": {
        "name": "Battery State of Charge",
        "unit": "%",
        "device_class": "battery",
        "state_class": "measurement",
        "value": lambda d: _first(d, "ems", {}).get("ems_soc"),
    },
    "ems_soh": {
        "name": "Battery State of Health",
        "unit": "%",
        "device_class": None,
        "state_class": "measurement",
        "value": lambda d: _first(d, "ems", {}).get("ems_soh"),
    },
    "ems_ac_frequency": {
        "name": "AC Frequency",
        "unit": "Hz",
        "device_class": None,
        "state_class": "measurement",
        "value": lambda d: _first(d, "ems", {}).get("ems_ac_frequency"),
    },
    "ems_ac_active_power": {
        "name": "Battery AC Active Power",
        "unit": "kW",
        "device_class": "power",
        "state_class": "measurement",
        "value": lambda d: _first(d, "ems", {}).get("ems_ac_active_power"),
    },
    "ems_dc_power_neg": {
        "name": "Battery DC Power -",
        "unit": "kW",
        "device_class": "power",
        "state_class": "measurement",
        "value": lambda d: _first(d, "ems", {}).get("ems_dc_power_neg"),
    },
    "ems_dc_power_pos": {
        "name": "Battery DC Power +",
        "unit": "kW",
        "device_class": "power",
        "state_class": "measurement",
        "value": lambda d: _first(d, "ems", {}).get("ems_dc_power_pos"),
    },
    "ems_ac_active_power_A": {
        "name": "Battery AC Active Power A",
        "unit": "kW",
        "device_class": "power",
        "state_class": "measurement",
        "value": lambda d: _first(d, "ems", {}).get("ems_ac_active_power_A"),
    },
    "ems_ac_active_power_B": {
        "name": "Battery AC Active Power B",
        "unit": "kW",
        "device_class": "power",
        "state_class": "measurement",
        "value": lambda d: _first(d, "ems", {}).get("ems_ac_active_power_B"),
    },
    "ems_ac_active_power_C": {
        "name": "Battery AC Active Power C",
        "unit": "kW",
        "device_class": "power",
        "state_class": "measurement",
        "value": lambda d: _first(d, "ems", {}).get("ems_ac_active_power_C"),
    },

    # Ammeter (grid/site)
    "ac_active_power": {
        "name": "Site Active Power",
        "unit": "W",
        "device_class": "power",
        "state_class": "measurement",
        "value": lambda d: _first(d, "ammeter", {}).get("ac_active_power"),
    },
    "ac_active_powers_0": {
        "name": "Site Active Power L1",
        "unit": "W",
        "device_class": "power",
        "state_class": "measurement",
        "value": lambda d: _first(d, "ammeter", {}).get("ac_active_powers_0"),
    },
    "ac_active_powers_1": {
        "name": "Site Active Power L2",
        "unit": "W",
        "device_class": "power",
        "state_class": "measurement",
        "value": lambda d: _first(d, "ammeter", {}).get("ac_active_powers_1"),
    },
    "ac_active_powers_2": {
        "name": "Site Active Power L3",
        "unit": "W",
        "device_class": "power",
        "state_class": "measurement",
        "value": lambda d: _first(d, "ammeter", {}).get("ac_active_powers_2"),
    },
}


def _first(obj: dict, key: str, default):
    arr = obj.get(key) or []
    return arr[0] if arr else default
