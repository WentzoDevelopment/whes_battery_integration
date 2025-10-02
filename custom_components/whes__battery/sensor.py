from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, SENSOR_MAP


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [WhesSensor(coordinator, key, cfg) for key, cfg in
                SENSOR_MAP.items()]
    async_add_entities(entities)


class WhesSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key: str, cfg: dict):
        super().__init__(coordinator)
        self._key = key
        self._cfg = cfg
        self._attr_unique_id = f"whes_{key}"
        self._attr_name = cfg["name"]
        self._attr_native_unit_of_measurement = cfg.get("unit")
        self._attr_device_class = cfg.get("device_class")
        self._attr_state_class = cfg.get("state_class")

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        try:
            return self._cfg["value"](data)
        except Exception:
            return None

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.native_value is not None

    @property
    def extra_state_attributes(self):
        # Tijdstempels of andere nuttige velden (indien beschikbaar in rows)
        d = {}
        ems = (self.coordinator.data or {}).get("ems") or []
        am = (self.coordinator.data or {}).get("ammeter") or []
        if ems:
            d["ems_time"] = ems[0].get("time")
        if am:
            d["ammeter_time"] = am[0].get("time")
        return d
