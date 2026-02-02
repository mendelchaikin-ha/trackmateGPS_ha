"""Config flow for Trackmate GPS integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_LABEL,
)
from .api import TrackmateAPI

_LOGGER = logging.getLogger(__name__)


class TrackmateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trackmate GPS."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.reauth_entry: Optional[config_entries.ConfigEntry] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate credentials
                await self._validate_credentials(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD]
                )
                
                # Check for existing entry with same username
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()
                
                # Create entry
                return self.async_create_entry(
                    title=user_input[CONF_LABEL],
                    data=user_input,
                )
                
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during setup")
                errors["base"] = "unknown"

        schema = vol.Schema({
            vol.Required(CONF_LABEL, default="School Account"): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        })
        
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Dict[str, Any]) -> FlowResult:
        """Handle reauth flow."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle reauth confirmation."""
        errors = {}

        if user_input is not None:
            try:
                # Validate new credentials
                await self._validate_credentials(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD]
                )
                
                # Update existing entry
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry,
                    data={
                        **self.reauth_entry.data,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
                
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"

        schema = vol.Schema({
            vol.Required(
                CONF_USERNAME,
                default=self.reauth_entry.data.get(CONF_USERNAME, "")
            ): str,
            vol.Required(CONF_PASSWORD): str,
        })
        
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "account": self.reauth_entry.title,
            },
        )

    async def _validate_credentials(self, username: str, password: str) -> None:
        """Validate credentials."""
        api = TrackmateAPI(self.hass, username, password)
        
        try:
            await api.async_setup()
            success = await api.test_connection()
            
            if not success:
                raise InvalidAuth
                
        except Exception as err:
            _LOGGER.error("Error validating credentials: %s", err)
            raise CannotConnect from err
        finally:
            await api.async_close()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return TrackmateOptionsFlowHandler(config_entry)


class TrackmateOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Trackmate GPS."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        # This will be implemented in options_flow.py
        from .options_flow import TrackmateOptionsFlow
        return await TrackmateOptionsFlow.async_step_init(self, user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
