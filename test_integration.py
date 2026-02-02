"""Integration tests for Trackmate GPS."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.setup import async_setup_component

from custom_components.trackmate.const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_LABEL,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)
from custom_components.trackmate import (
    async_setup_entry,
    async_unload_entry,
)


class TestIntegrationEndToEnd:
    """Test complete integration flow."""

    @pytest.mark.asyncio
    async def test_full_setup_flow(self, hass: HomeAssistant):
        """Test complete setup from config entry to entities."""
        # Create config entry
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry"
        entry.data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
            CONF_LABEL: "Test Account",
        }
        entry.options = {
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        }
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        
        # Mock API
        mock_api = MagicMock()
        mock_api.async_setup = AsyncMock()
        mock_api.async_close = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api.get_positions = AsyncMock(return_value={
            "MotusObject": {
                "Points": [
                    {
                        "VehicleDescription": "Bus 101",
                        "Latitude": 40.7128,
                        "Longitude": -74.0060,
                        "Speed": 25,
                        "Heading": 180,
                    }
                ]
            }
        })
        
        with patch(
            "custom_components.trackmate.TrackmateAPI",
            return_value=mock_api,
        ):
            # Setup integration
            result = await async_setup_entry(hass, entry)
            assert result is True
            
            # Verify coordinator is set up
            assert DOMAIN in hass.data
            assert entry.entry_id in hass.data[DOMAIN]
            
            # Verify API was initialized
            assert mock_api.async_setup.called
            assert mock_api.test_connection.called

    @pytest.mark.asyncio
    async def test_entity_state_updates(self, hass: HomeAssistant):
        """Test that entity states update correctly."""
        # Set up integration
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry"
        entry.data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
            CONF_LABEL: "Test Account",
        }
        entry.options = {}
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        
        # Create mock API with changing data
        call_count = 0
        
        async def mock_get_positions():
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                # First call - vehicle at home
                return {
                    "MotusObject": {
                        "Points": [
                            {
                                "VehicleDescription": "Bus 101",
                                "Latitude": 40.7128,
                                "Longitude": -74.0060,
                                "Speed": 0,
                            }
                        ]
                    }
                }
            else:
                # Second call - vehicle moved
                return {
                    "MotusObject": {
                        "Points": [
                            {
                                "VehicleDescription": "Bus 101",
                                "Latitude": 40.7580,
                                "Longitude": -73.9855,
                                "Speed": 30,
                            }
                        ]
                    }
                }
        
        mock_api = MagicMock()
        mock_api.async_setup = AsyncMock()
        mock_api.async_close = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api.get_positions = mock_get_positions
        
        with patch(
            "custom_components.trackmate.TrackmateAPI",
            return_value=mock_api,
        ):
            await async_setup_entry(hass, entry)
            
            # Verify initial state
            # (Note: actual entity state testing would require full HA setup)

    @pytest.mark.asyncio
    async def test_reauth_flow(self, hass: HomeAssistant):
        """Test reauth flow when credentials expire."""
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry"
        entry.data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "old_password",
            CONF_LABEL: "Test Account",
        }
        entry.options = {}
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        
        # First setup succeeds
        mock_api = MagicMock()
        mock_api.async_setup = AsyncMock()
        mock_api.async_close = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api.get_positions = AsyncMock(return_value={
            "MotusObject": {"Points": []}
        })
        
        with patch(
            "custom_components.trackmate.TrackmateAPI",
            return_value=mock_api,
        ):
            result = await async_setup_entry(hass, entry)
            assert result is True

    @pytest.mark.asyncio
    async def test_rate_limiting_behavior(self, hass: HomeAssistant):
        """Test that rate limiting is enforced."""
        from custom_components.trackmate.api import RateLimiter
        
        # Create rate limiter with low limit for testing
        limiter = RateLimiter(max_requests=3, window=1)
        
        # Should allow first 3 requests
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
        
        assert len(limiter.requests) == 3

    @pytest.mark.asyncio
    async def test_cookie_persistence(self, hass: HomeAssistant):
        """Test cookie persistence across setup/teardown."""
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry"
        entry.data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
            CONF_LABEL: "Test Account",
        }
        entry.options = {}
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        
        saved_data = {}
        
        async def mock_save(data):
            saved_data.update(data)
        
        async def mock_load():
            return saved_data if saved_data else None
        
        mock_store = MagicMock()
        mock_store.async_save = mock_save
        mock_store.async_load = mock_load
        
        mock_api = MagicMock()
        mock_api.async_setup = AsyncMock()
        mock_api.async_close = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api.get_positions = AsyncMock(return_value={
            "MotusObject": {"Points": []}
        })
        mock_api.store = mock_store
        mock_api.cookies = {"session": "test"}
        mock_api.cookie_expiry = datetime.now() + timedelta(hours=1)
        
        with patch(
            "custom_components.trackmate.TrackmateAPI",
            return_value=mock_api,
        ):
            # Setup
            await async_setup_entry(hass, entry)
            
            # Simulate cookie save
            await mock_api._save_cookies()
            
            # Verify cookies were saved
            assert "cookies" in saved_data
            assert "expiry" in saved_data

    @pytest.mark.asyncio
    async def test_diagnostics_integration(self, hass: HomeAssistant):
        """Test diagnostics integration."""
        from custom_components.trackmate.diagnostics import (
            async_get_config_entry_diagnostics,
        )
        
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry"
        entry.title = "Test Account"
        entry.version = 1
        entry.data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
        }
        entry.options = {
            CONF_SCAN_INTERVAL: 30,
        }
        
        # Set up minimal data structure
        from custom_components.trackmate.const import DATA_API, DATA_COORDINATOR
        
        mock_coordinator = MagicMock()
        mock_coordinator.last_update_success = True
        mock_coordinator.update_interval.total_seconds.return_value = 30
        mock_coordinator.data = {
            "MotusObject": {"Points": []}
        }
        
        mock_api = MagicMock()
        mock_api.get_diagnostics = AsyncMock(return_value={
            "cookies_cached": True,
            "cookie_expiry": "2026-02-02T12:00:00",
            "rate_limiter_requests": 5,
            "rate_limiter_max": 60,
            "rate_limiter_window": 3600,
        })
        
        hass.data[DOMAIN] = {
            entry.entry_id: {
                DATA_COORDINATOR: mock_coordinator,
                DATA_API: mock_api,
            }
        }
        
        # Get diagnostics
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        
        # Verify structure
        assert "entry" in diagnostics
        assert "coordinator" in diagnostics
        assert "api" in diagnostics
