"""Device tracker platform for Trackmate GPS."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_USERNAME, DOMAIN
from .coordinator import TrackmateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TrackmateCoordinator = \
        hass.data[DOMAIN][entry.entry_id]["coordinator"]
    known: set[str] = set()

    @callback
    def _check_new() -> None:
        if not coordinator.data:
            return
        new = [TrackmateTracker(coordinator, entry, vid, vd)
               for vid, vd in coordinator.data.items() if vid not in known]
        if new:
            known.update(t._vid for t in new)
            async_add_entities(new)

    _check_new()
    entry.async_on_unload(coordinator.async_add_listener(_check_new))


class TrackmateTracker(CoordinatorEntity[TrackmateCoordinator], TrackerEntity):
    """A single TrackmateGPS vehicle."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TrackmateCoordinator,
                 entry: ConfigEntry, vid: str, vdata: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._vid = vid
        username = entry.data.get(CONF_USERNAME, "default")
        vname = vdata.get("name", vid)

        self._attr_unique_id = f"trackmate_{username}_{vid}"
        self._attr_name = vname
        self._attr_icon = "mdi:car-connected"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{username}_{vid}")},
            "name": vname,
            "manufacturer": "TrackmateGPS",
            "model": "GPS Tracker",
            "via_device": (DOMAIN, f"account_{username}"),
        }
        
        # ADDED: Cache last known position and attributes
        self._last_latitude: float | None = vdata.get("latitude")
        self._last_longitude: float | None = vdata.get("longitude")
        self._last_attributes: dict[str, Any] = {}

    @property
    def _vd(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(self._vid)

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        # CHANGED: Cache and return last known position
        if d := self._vd:
            if lat := d.get("latitude"):
                self._last_latitude = lat
                return lat
        # Return cached position if current data unavailable
        return self._last_latitude

    @property
    def longitude(self) -> float | None:
        # CHANGED: Cache and return last known position
        if d := self._vd:
            if lon := d.get("longitude"):
                self._last_longitude = lon
                return lon
        # Return cached position if current data unavailable
        return self._last_longitude

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if d := self._vd:
            # Update cache with current data
            for k in ("speed", "heading"):
                if d.get(k) is not None:
                    attrs[k] = d[k]
                    self._last_attributes[k] = d[k]
            if d.get("last_update"):
                attrs["trackmate_last_update"] = d["last_update"]
                self._last_attributes["trackmate_last_update"] = d["last_update"]
            source = d.get("source", "unknown")
            attrs["trackmate_source"] = source
            self._last_attributes["trackmate_source"] = source
        elif self._last_attributes:
            # ADDED: Return cached attributes if current data unavailable
            attrs = self._last_attributes.copy()
        
        return attrs

    @property
    def available(self) -> bool:
        # CHANGED: Available if we have current data OR cached position
        # This prevents going unavailable during transient failures
        
        # If we have current data for this vehicle, definitely available
        if self._vid in (self.coordinator.data or {}):
            return super().available
        
        # If coordinator is working (even if this vehicle not in current data),
        # stay available if we have cached position
        if super().available and self._last_latitude is not None and self._last_longitude is not None:
            return True
        
        # If we have cached position, stay available even if coordinator failed
        # (coordinator might be returning cached data that doesn't include this vehicle)
        if self._last_latitude is not None and self._last_longitude is not None:
            return True
        
        # No current data and no cached position - unavailable
        return False
