"""Config flow for Trackmate GPS integration - NO VALIDATION VERSION."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# This version SKIPS validation to avoid timeout issues
# The real validation happens after the entry is created

class TrackmateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trackmate GPS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Simple validation - just check format
            username = user_input[CONF_EMAIL]  # Can be email OR username
            password = user_input[CONF_PASSWORD]
            
            if not username or not password:
                errors["base"] = "invalid_auth"
            else:
                # Accept credentials without testing!
                # The actual test happens when the entry loads
                _LOGGER.info("Accepting credentials for %s (will validate on entry load)", username)
                
                # Create entry
                return self.async_create_entry(
                    title=user_input.get("name", username),
                    data=user_input,
                )

        # Show the form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional("name", default="Trackmate GPS"): str,
                    vol.Required(CONF_EMAIL): str,  # Can be email or username
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
