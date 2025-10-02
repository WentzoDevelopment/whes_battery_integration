from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower, UnitOfEnergy, UnitOfFrequency, PERCENTAGE
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_NAME_PREFIX
from .coordinator import WhesCoordinator

SENSOR_MAP = {
    "ems_soc": ("EMS State of Charge", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),
    "ems_soh": ("EMS State of Health", PERCENTAGE, None, SensorStateClass.MEASUREMENT),
    "ems_state": ("EMS Operating State", None, SensorDeviceClass.ENUM, None),
    "ems_dc_power_neg": ("Battery Charge (DC -)", UnitOfPower.KILO_WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "ems_dc_power_pos": ("Battery Discharge (DC +)", UnitOfPower.KILO_WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "ems_ac_active_power": ("EMS AC Active Power", UnitOfPower.KILO_WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "ems_ac_frequency": ("EMS AC Frequency", UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT),
    "ems_history_input_energy": ("EMS Energy In (hist)", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
    "ems_history_output_energy": ("EMS Energy Out (hist)", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
    "ems_ac_active_power_A": ("EMS Phase A Power", UnitOfPower.KILO_WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "ems_ac_active_power_B": ("EMS Phase B Power", UnitOfPower.KILO_WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "ems_ac_active_power_C": ("EMS Phase C Power", UnitOfPower.KILO_WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "ac_active_power": ("Grid Active Power (sum)", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "ac_active_powers_0": ("Grid Phase L1 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "ac_active_powers_1": ("Grid Phase L2 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "ac_active_powers_2": ("Grid Phase L3 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coordinator: WhesCoordinator = hass.data[DOMAIN][entry.entry_id]
    name_prefix = entry.data.get(CONF_NAME_PREFIX, "WHES")

    entities=[]
    for section, keys in (("ems",[k for k in SENSOR_MAP if k.startswith("ems_")]),
                          ("ammeter",[k for k in SENSOR_MAP if not k.startswith("ems_")])):
        for key in keys:
            suffix, unit, devcls, statecls = SENSOR_MAP[key]
            entities.append(WhesMetricSensor(coordinator, name_prefix, section, key, suffix, unit, devcls, statecls))

    async_add_entities(entities)

class WhesMetricSensor(SensorEntity):
    _attr_should_poll = False

    def __init__(self, coordinator: WhesCoordinator, name_prefix: str, section: str, key: str, suffix: str, unit, devcls, statecls):
        self.coordinator = coordinator
        self._section = section
        self._key = key

        self._attr_has_entity_name = True
        self._attr_name = f"{name_prefix} {suffix}"
        self._attr_unique_id = f"whes_{section}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = devcls
        self._attr_state_class = statecls
        self._attr_device_info = {
            "identifiers": {("whes","battery")},
            "name": f"{name_prefix} Battery",
            "manufacturer": "WHES / Weiheng",
            "model": "Battery + Ammeter",
        }

    async def async_added_to_hass(self):
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    @property
    def available(self) -> bool:
        return isinstance(self.coordinator.data, dict) and self._section in self.coordinator.data

    @property
    def native_value(self):
        data = (self.coordinator.data or {}).get(self._section) or {}
        val = data.get(self._key)
        try:
            if isinstance(val, float):
                return round(val, 2 if self._attr_device_class == SensorDeviceClass.FREQUENCY else 1)
        except Exception:
            pass
        return val
