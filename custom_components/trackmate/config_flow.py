"""Config flow for Trackmate GPS."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import TrackmateAuthError, TrackmateClient, TrackmateConnectionError
from .const import (
    CONF_FLARESOLVERR_URL, CONF_PASSWORD, CONF_SCAN_INTERVAL,
    CONF_SESSION_REFRESH, CONF_USERNAME, CONF_VEHICLE_IDS,
    DEFAULT_FS_URL, DEFAULT_SCAN_INTERVAL, DEFAULT_SESSION_REFRESH, DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class TrackmateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow: FlareSolverr URL + TrackmateGPS credentials."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            # Unique per username
            await self.async_set_unique_id(f"trackmate_{username}")
            self._abort_if_unique_id_configured()

            client = TrackmateClient(
                fs_url=user_input[CONF_FLARESOLVERR_URL],
                username=username,
                password=user_input[CONF_PASSWORD],
            )
            try:
                await client.validate()
                return self.async_create_entry(
                    title=f"Trackmate – {username}",
                    data=user_input,
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_SESSION_REFRESH: DEFAULT_SESSION_REFRESH,
                        CONF_VEHICLE_IDS: [],
                    },
                )
            except TrackmateConnectionError:
                errors["base"] = "cannot_connect"
            except TrackmateAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_FLARESOLVERR_URL,
                             default=DEFAULT_FS_URL): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any],
    ) -> FlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            client = TrackmateClient(
                fs_url=entry.data[CONF_FLARESOLVERR_URL],
                username=entry.data[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            try:
                await client.validate()
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
            except TrackmateConnectionError:
                errors["base"] = "cannot_connect"
            except TrackmateAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "unknown"
            finally:
                await client.close()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return TrackmateOptionsFlow(config_entry)


class TrackmateOptionsFlow(OptionsFlow):
    """Options: scan interval, session refresh, vehicle filter."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Try to get vehicle list for picker
        vehicle_opts: dict[str, str] = {}
        try:
            client = TrackmateClient(
                fs_url=self._entry.data[CONF_FLARESOLVERR_URL],
                username=self._entry.data[CONF_USERNAME],
                password=self._entry.data[CONF_PASSWORD],
            )
            vehicles = await client.get_vehicles()
            await client.close()
            for vid, vd in vehicles.items():
                vehicle_opts[vid] = vd.get("name", vid)
        except Exception:
            pass

        cur = self._entry.options
        schema: dict = {
            vol.Optional(CONF_SCAN_INTERVAL,
                         default=cur.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)):
                vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            vol.Optional(CONF_SESSION_REFRESH,
                         default=cur.get(CONF_SESSION_REFRESH, DEFAULT_SESSION_REFRESH)):
                vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
        }
        if vehicle_opts:
            schema[vol.Optional(CONF_VEHICLE_IDS,
                                default=cur.get(CONF_VEHICLE_IDS, []))] = \
                vol.All(vol.Coerce(list), [vol.In(vehicle_opts)])

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema))
