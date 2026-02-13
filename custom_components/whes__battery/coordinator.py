from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import *
from .api import WhesClient

_LOGGER = logging.getLogger(__name__)


class WhesCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.entry = entry
        d = entry.data
        interval = max(MIN_SCAN_INTERVAL, int(d.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)))

        self._client = WhesClient(
            session=async_get_clientsession(hass),
            base_url=d.get(CONF_BASE_URL, DEFAULT_BASE_URL),
            api_key=d[CONF_API_KEY],
            api_secret=d[CONF_API_SECRET],
            project_id=d[CONF_PROJECT_ID],
            device_id=d[CONF_DEVICE_ID],
            ammeter_id=d[CONF_AMMETER_ID],
        )
        self._sample_by = d.get(CONF_SAMPLE_BY, DEFAULT_SAMPLE_BY)
        self._poll_seconds = interval

        super().__init__(hass, logger=_LOGGER, name="whes_coordinator", update_interval=timedelta(seconds=interval))

    async def _async_update_data(self) -> dict:
        try:
            return await self._client.fetch_bundle(
                poll_seconds=self._poll_seconds,
                sample_by=self._sample_by,
            )
        except Exception as e:
            raise UpdateFailed(str(e)) from e
