"""DataUpdateCoordinator for Trackmate GPS."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TrackmateAuthError, TrackmateClient, TrackmateConnectionError, TrackmateError
from .const import CONF_SCAN_INTERVAL, CONF_SESSION_REFRESH, CONF_VEHICLE_IDS, DEFAULT_SCAN_INTERVAL, DEFAULT_SESSION_REFRESH, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TrackmateCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry,
                 client: TrackmateClient) -> None:
        self.client = client
        self.entry = entry
        self._last_login = time.monotonic()
        self._refresh_mins = entry.options.get(
            CONF_SESSION_REFRESH, DEFAULT_SESSION_REFRESH)
        super().__init__(
            hass, _LOGGER, name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        # Re-login if session refresh interval exceeded
        elapsed = (time.monotonic() - self._last_login) / 60
        if elapsed > self._refresh_mins or not self.client.logged_in:
            try:
                await self.client.login()
                self._last_login = time.monotonic()
            except TrackmateAuthError as e:
                raise ConfigEntryAuthFailed(str(e)) from e
            except TrackmateConnectionError as e:
                raise UpdateFailed(str(e)) from e

        try:
            vehicles = await self.client.get_vehicles()
        except TrackmateAuthError as e:
            raise ConfigEntryAuthFailed(str(e)) from e
        except TrackmateConnectionError as e:
            raise UpdateFailed(str(e)) from e
        except TrackmateError as e:
            raise UpdateFailed(str(e)) from e

        selected = self.entry.options.get(CONF_VEHICLE_IDS, [])
        if selected:
            vehicles = {k: v for k, v in vehicles.items() if k in selected}
        return vehicles
