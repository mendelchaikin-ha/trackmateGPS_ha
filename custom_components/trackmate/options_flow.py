"""Options flow for Trackmate GPS integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_BUSES,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    DATA_API,
)

_LOGGER = logging.getLogger(__name__)


class TrackmateOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Trackmate GPS."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}
        
        if user_input is not None:
            # Validate scan interval
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            if scan_interval < MIN_SCAN_INTERVAL:
                errors["base"] = "scan_interval_too_low"
            elif scan_interval > MAX_SCAN_INTERVAL:
                errors["base"] = "scan_interval_too_high"
            else:
                return self.async_create_entry(title="", data=user_input)
        
        # Get available buses
        buses = []
        try:
            api = self.hass.data[DOMAIN][self.config_entry.entry_id][DATA_API]
            data = await api.get_positions()
            
            if data and "MotusObject" in data and "Points" in data["MotusObject"]:
                buses = [
                    v["VehicleDescription"] 
                    for v in data["MotusObject"]["Points"]
                    if v.get("VehicleDescription")
                ]
                buses = sorted(list(set(buses)))  # Remove duplicates and sort
                _LOGGER.debug("Found %d unique vehicles", len(buses))
        except Exception as err:
            _LOGGER.error("Failed to fetch vehicle list: %s", err)
            errors["base"] = "cannot_fetch_vehicles"
        
        current_buses = self.config_entry.options.get(CONF_BUSES, [])
        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        
        schema = vol.Schema({
            vol.Optional(
                CONF_BUSES,
                default=current_buses,
            ): vol.All(vol.Unique(), [vol.In(buses)]) if buses else vol.All(vol.Unique(), [str]),
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=current_scan_interval,
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
            ),
        })
        
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "min_interval": str(MIN_SCAN_INTERVAL),
                "max_interval": str(MAX_SCAN_INTERVAL),
                "default_interval": str(DEFAULT_SCAN_INTERVAL),
            },
        )
