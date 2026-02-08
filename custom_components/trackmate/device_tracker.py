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

    @property
    def _vd(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(self._vid)

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        return (d := self._vd) and d.get("latitude")

    @property
    def longitude(self) -> float | None:
        return (d := self._vd) and d.get("longitude")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if d := self._vd:
            for k in ("speed", "heading"):
                if d.get(k) is not None:
                    attrs[k] = d[k]
            if d.get("last_update"):
                attrs["trackmate_last_update"] = d["last_update"]
            attrs["trackmate_source"] = d.get("source", "unknown")
        return attrs

    @property
    def available(self) -> bool:
        return super().available and self._vid in (self.coordinator.data or {})
