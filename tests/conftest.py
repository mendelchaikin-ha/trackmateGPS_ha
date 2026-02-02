"""Test fixtures for Trackmate GPS integration."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.trackmate.const import DOMAIN


@pytest.fixture
def mock_api():
    """Mock TrackmateAPI."""
    api = MagicMock()
    api.async_setup = AsyncMock()
    api.async_close = AsyncMock()
    api.test_connection = AsyncMock(return_value=True)
    api.login = AsyncMock()
    api.get_positions = AsyncMock(return_value={
        "MotusObject": {
            "Points": [
                {
                    "VehicleDescription": "Bus 101",
                    "Latitude": 40.7128,
                    "Longitude": -74.0060,
                    "Speed": 25,
                    "Heading": 180,
                },
                {
                    "VehicleDescription": "Bus 102",
                    "Latitude": 40.7580,
                    "Longitude": -73.9855,
                    "Speed": 30,
                    "Heading": 90,
                },
            ]
        }
    })
    api.get_diagnostics = AsyncMock(return_value={
        "cookies_cached": True,
        "cookie_expiry": "2026-02-02T12:00:00",
        "rate_limiter_requests": 5,
        "rate_limiter_max": 60,
        "rate_limiter_window": 3600,
    })
    return api


@pytest.fixture
def mock_config_entry():
    """Mock ConfigEntry."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        "username": "test@example.com",
        "password": "test_password",
        "label": "Test Account",
    }
    entry.options = {
        "scan_interval": 30,
        "buses": ["Bus 101"],
    }
    entry.version = 1
    entry.title = "Test Account"
    return entry


@pytest.fixture
async def hass_with_integration(hass: HomeAssistant, mock_api, mock_config_entry):
    """Set up Home Assistant with Trackmate integration."""
    with patch(
        "custom_components.trackmate.TrackmateAPI",
        return_value=mock_api,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
    
    return hass


@pytest.fixture
def mock_rate_limiter():
    """Mock RateLimiter."""
    limiter = MagicMock()
    limiter.acquire = AsyncMock()
    return limiter
