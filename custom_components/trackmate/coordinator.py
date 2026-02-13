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
        
        # ADDED: Track consecutive failures to tolerate transient issues
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        
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
                # CHANGED: Don't immediately fail on login connection error
                self._consecutive_failures += 1
                _LOGGER.warning(
                    "Login connection error (attempt %d/%d): %s",
                    self._consecutive_failures,
                    self._max_consecutive_failures,
                    e,
                )
                
                # Only fail after multiple consecutive failures
                if self._consecutive_failures >= self._max_consecutive_failures:
                    raise UpdateFailed(f"Login failed after {self._consecutive_failures} attempts: {e}") from e
                
                # Return cached data if available
                if self.data:
                    _LOGGER.debug("Login failed, returning cached vehicle data")
                    return self.data
                
                raise UpdateFailed(str(e)) from e

        try:
            t0 = time.monotonic()
            vehicles = await self.client.get_vehicles()
            elapsed_s = time.monotonic() - t0
            _LOGGER.debug(
                "Finished fetching trackmate data in "
                "%.1f seconds (vehicles: %d)",
                elapsed_s, len(vehicles))
            
            # ADDED: Reset failure counter on success
            self._consecutive_failures = 0
            
        except TrackmateAuthError as e:
            raise ConfigEntryAuthFailed(str(e)) from e
        except TrackmateConnectionError as e:
            # CHANGED: Don't immediately fail on connection error
            self._consecutive_failures += 1
            _LOGGER.warning(
                "Connection error fetching vehicles (attempt %d/%d): %s",
                self._consecutive_failures,
                self._max_consecutive_failures,
                e,
            )
            
            # Only fail after multiple consecutive failures
            if self._consecutive_failures >= self._max_consecutive_failures:
                raise UpdateFailed(f"Failed to fetch vehicles after {self._consecutive_failures} attempts: {e}") from e
            
            # Return cached data if available
            if self.data:
                _LOGGER.debug("Fetch failed, returning cached vehicle data")
                return self.data
            
            raise UpdateFailed(str(e)) from e
        except TrackmateError as e:
            # CHANGED: Don't immediately fail on other errors
            self._consecutive_failures += 1
            _LOGGER.warning(
                "Error fetching vehicles (attempt %d/%d): %s",
                self._consecutive_failures,
                self._max_consecutive_failures,
                e,
            )
            
            # Only fail after multiple consecutive failures
            if self._consecutive_failures >= self._max_consecutive_failures:
                raise UpdateFailed(f"Failed to fetch vehicles after {self._consecutive_failures} attempts: {e}") from e
            
            # Return cached data if available
            if self.data:
                _LOGGER.debug("Error occurred, returning cached vehicle data")
                return self.data
            
            raise UpdateFailed(str(e)) from e

        selected = self.entry.options.get(CONF_VEHICLE_IDS, [])
        if selected:
            vehicles = {k: v for k, v in vehicles.items() if k in selected}
        return vehicles
