"""Diagnostics support for Trackmate GPS."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, DATA_API, DATA_COORDINATOR, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data[DATA_COORDINATOR]
    api = data[DATA_API]
    
    # Get API diagnostics
    api_diagnostics = await api.get_diagnostics()
    
    # Get coordinator data (redacted)
    coordinator_data = {}
    if coordinator.data:
        motus = coordinator.data.get("MotusObject", {})
        points = motus.get("Points", [])
        
        coordinator_data = {
            "vehicle_count": len(points),
            "vehicles": [
                {
                    "description": p.get("VehicleDescription", "Unknown"),
                    "has_position": bool(p.get("Latitude") and p.get("Longitude")),
                    "has_speed": "Speed" in p,
                    "has_heading": "Heading" in p,
                }
                for p in points
            ],
        }
    
    # Build diagnostics
    diagnostics = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "username": _redact_email(entry.data.get(CONF_USERNAME, "")),
        },
        "options": {
            "scan_interval": entry.options.get("scan_interval", "default"),
            "selected_buses": entry.options.get("buses", []),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": coordinator.update_interval.total_seconds() if coordinator.update_interval else None,
            "data": coordinator_data,
        },
        "api": api_diagnostics,
    }
    
    return diagnostics


def _redact_email(email: str) -> str:
    """Redact email address for privacy."""
    if not email or "@" not in email:
        return "***"
    
    parts = email.split("@")
    username = parts[0]
    domain = parts[1]
    
    # Show first 2 chars and last 1 char of username
    if len(username) <= 3:
        redacted_username = username[0] + "*" * (len(username) - 1)
    else:
        redacted_username = username[:2] + "*" * (len(username) - 3) + username[-1]
    
    return f"{redacted_username}@{domain}"
