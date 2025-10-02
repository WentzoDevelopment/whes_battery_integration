from __future__ import annotations
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (
    DOMAIN, DEFAULT_UPDATE_SECONDS,
    CONF_API_KEY, CONF_API_SECRET, CONF_PROJECT_ID, CONF_DEVICE_ID,
    CONF_AMMETER_ID, CONF_BASE_URL,
)
from .api import WhesClient


class WhesCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, cfg: dict) -> None:
        super().__init__(
            hass,
            hass.helpers.logger.logger,
            name=f"{DOMAIN} coordinator",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_SECONDS),
        )

        session = async_get_clientsession(hass)
        self.client = WhesClient(
            session,
            cfg[CONF_BASE_URL],
            cfg[CONF_API_KEY],
            cfg[CONF_API_SECRET],
            cfg[CONF_PROJECT_ID],
            cfg[CONF_DEVICE_ID],
            cfg[CONF_AMMETER_ID],
        )

    async def _async_update_data(self):
        return await self.client.fetch_bundle()
