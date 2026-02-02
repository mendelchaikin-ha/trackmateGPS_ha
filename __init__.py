"""The Trackmate GPS integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    DOMAIN,
    DATA_COORDINATOR,
    DATA_API,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)
from .coordinator import TrackmateCoordinator
from .api import TrackmateAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Trackmate GPS from a config entry."""
    _LOGGER.debug("Setting up Trackmate GPS integration")
    
    # Get configuration
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    
    # Create API client
    api = TrackmateAPI(hass, username, password)
    
    try:
        await api.async_setup()
        
        # Test connection
        _LOGGER.debug("Testing API connection")
        if not await api.test_connection():
            raise ConfigEntryAuthFailed("Failed to authenticate with Trackmate GPS")
        
    except ConfigEntryAuthFailed:
        await api.async_close()
        raise
    except Exception as err:
        await api.async_close()
        _LOGGER.error("Failed to set up Trackmate GPS: %s", err)
        raise ConfigEntryNotReady from err
    
    # Create coordinator
    coordinator = TrackmateCoordinator(hass, api, scan_interval)
    
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        await api.async_close()
        raise
    except Exception as err:
        await api.async_close()
        _LOGGER.error("Failed initial data refresh: %s", err)
        raise ConfigEntryNotReady from err
    
    # Store data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_API: api,
    }
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register update listener for options
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    _LOGGER.info("Trackmate GPS integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Trackmate GPS integration")
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Clean up
        data = hass.data[DOMAIN].pop(entry.entry_id)
        api = data[DATA_API]
        await api.async_close()
        _LOGGER.info("Trackmate GPS integration unloaded")
    
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    _LOGGER.debug("Updating Trackmate GPS options")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating Trackmate GPS entry from version %s", entry.version)
    
    if entry.version == 1:
        # No migration needed yet
        pass
    
    return True
