"""Device tracker platform for Trackmate GPS."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DATA_COORDINATOR, CONF_BUSES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Trackmate device tracker from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    selected = entry.options.get(CONF_BUSES, [])
    
    # Get initial vehicles
    if not coordinator.data or "MotusObject" not in coordinator.data:
        _LOGGER.warning("No data available during device tracker setup")
        return
    
    vehicles = coordinator.data["MotusObject"]["Points"]
    
    # Filter by selected vehicles if specified
    if selected:
        vehicles = [v for v in vehicles if v.get("VehicleDescription") in selected]
        _LOGGER.debug("Filtered to %d selected vehicles", len(vehicles))
    
    # Create entities
    entities = [
        TrackmateVehicle(coordinator, v["VehicleDescription"])
        for v in vehicles
        if v.get("VehicleDescription")
    ]
    
    _LOGGER.info("Setting up %d Trackmate vehicle trackers", len(entities))
    async_add_entities(entities)


class TrackmateVehicle(CoordinatorEntity, TrackerEntity):
    """Representation of a Trackmate GPS tracked vehicle."""

    def __init__(self, coordinator, vehicle_id: str):
        """Initialize the tracker."""
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        self._attr_name = vehicle_id
        self._attr_unique_id = f"trackmate_{vehicle_id.lower().replace(' ', '_')}"

    @property
    def _vehicle_data(self) -> Optional[Dict[str, Any]]:
        """Get current vehicle data from coordinator."""
        if not self.coordinator.data:
            return None
        
        points = self.coordinator.data.get("MotusObject", {}).get("Points", [])
        for vehicle in points:
            if vehicle.get("VehicleDescription") == self._vehicle_id:
                return vehicle
        return None

    @property
    def latitude(self) -> Optional[float]:
        """Return latitude value of the device."""
        vehicle = self._vehicle_data
        if vehicle:
            return vehicle.get("Latitude")
        return None

    @property
    def longitude(self) -> Optional[float]:
        """Return longitude value of the device."""
        vehicle = self._vehicle_data
        if vehicle:
            return vehicle.get("Longitude")
        return None

    @property
    def source_type(self) -> str:
        """Return the source type of the device."""
        return "gps"

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:map-marker"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return device specific attributes."""
        vehicle = self._vehicle_data
        if not vehicle:
            return {}
        
        attrs = {}
        
        # Add speed if available
        if "Speed" in vehicle:
            attrs["speed"] = vehicle["Speed"]
        
        # Add heading if available
        if "Heading" in vehicle:
            attrs["heading"] = vehicle["Heading"]
        
        # Add any other useful attributes
        if "LastUpdate" in vehicle:
            attrs["last_update"] = vehicle["LastUpdate"]
        
        if "Status" in vehicle:
            attrs["status"] = vehicle["Status"]
        
        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self._vehicle_data is not None
            and self.latitude is not None
            and self.longitude is not None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this tracker."""
        return {
            "identifiers": {(DOMAIN, self._vehicle_id)},
            "name": self._vehicle_id,
            "manufacturer": "Trackmate GPS",
            "model": "GPS Tracker",
            "via_device": (DOMAIN, "trackmate_api"),
        }
