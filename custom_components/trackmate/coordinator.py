"""Trackmate GPS coordinator with configurable polling."""
import logging
from datetime import timedelta
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class TrackmateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Trackmate GPS data updates."""

    def __init__(self, hass: HomeAssistant, api, scan_interval: int = DEFAULT_SCAN_INTERVAL):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Trackmate GPS",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self._scan_interval = scan_interval

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from Trackmate API."""
        try:
            _LOGGER.debug("Updating Trackmate GPS data")
            data = await self.api.get_positions()
            
            if not data or "MotusObject" not in data:
                _LOGGER.warning("Received invalid data from API")
                raise UpdateFailed("Invalid data received from API")
            
            points = data.get("MotusObject", {}).get("Points", [])
            _LOGGER.debug("Successfully updated data for %d vehicles", len(points))
            
            return data
            
        except ConfigEntryAuthFailed as err:
            # This will trigger a reauth flow
            _LOGGER.error("Authentication failed: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("Error fetching Trackmate data: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}")

    def update_scan_interval(self, scan_interval: int):
        """Update the scan interval."""
        self._scan_interval = scan_interval
        self.update_interval = timedelta(seconds=scan_interval)
        _LOGGER.info("Updated scan interval to %d seconds", scan_interval)
