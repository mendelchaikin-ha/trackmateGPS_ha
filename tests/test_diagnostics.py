"""Tests for Trackmate GPS diagnostics."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from custom_components.trackmate.diagnostics import (
    async_get_config_entry_diagnostics,
    _redact_email,
)
from custom_components.trackmate.const import DOMAIN, DATA_API, DATA_COORDINATOR


class TestDiagnostics:
    """Test diagnostics functionality."""

    @pytest.mark.asyncio
    async def test_diagnostics_generation(self, hass):
        """Test diagnostics data generation."""
        # Create mock entry
        entry = MagicMock()
        entry.entry_id = "test_entry"
        entry.title = "Test Account"
        entry.version = 1
        entry.data = {
            "username": "test@example.com",
            "password": "secret",
            "label": "Test Account",
        }
        entry.options = {
            "scan_interval": 30,
            "buses": ["Bus 101"],
        }
        
        # Create mock coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.last_update_success = True
        mock_coordinator.update_interval.total_seconds.return_value = 30
        mock_coordinator.data = {
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
                    },
                ]
            }
        }
        
        # Create mock API
        mock_api = MagicMock()
        mock_api.get_diagnostics = AsyncMock(return_value={
            "cookies_cached": True,
            "cookie_expiry": "2026-02-02T12:00:00",
            "rate_limiter_requests": 5,
            "rate_limiter_max": 60,
            "rate_limiter_window": 3600,
        })
        
        # Set up hass data
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
        assert "options" in diagnostics
        assert "coordinator" in diagnostics
        assert "api" in diagnostics
        
        # Verify entry data
        assert diagnostics["entry"]["title"] == "Test Account"
        assert diagnostics["entry"]["version"] == 1
        assert "test@" in diagnostics["entry"]["username"]  # Should be redacted
        
        # Verify options
        assert diagnostics["options"]["scan_interval"] == 30
        assert diagnostics["options"]["selected_buses"] == ["Bus 101"]
        
        # Verify coordinator data
        assert diagnostics["coordinator"]["last_update_success"] is True
        assert diagnostics["coordinator"]["update_interval_seconds"] == 30
        assert diagnostics["coordinator"]["data"]["vehicle_count"] == 2
        
        # Verify vehicle data
        vehicles = diagnostics["coordinator"]["data"]["vehicles"]
        assert len(vehicles) == 2
        assert vehicles[0]["description"] == "Bus 101"
        assert vehicles[0]["has_position"] is True
        assert vehicles[0]["has_speed"] is True
        assert vehicles[0]["has_heading"] is True
        assert vehicles[1]["has_speed"] is False
        
        # Verify API data
        assert diagnostics["api"]["cookies_cached"] is True
        assert diagnostics["api"]["rate_limiter_requests"] == 5

    def test_redact_email(self):
        """Test email redaction."""
        # Normal email
        assert _redact_email("test@example.com") == "te**t@example.com"
        
        # Short email
        assert _redact_email("ab@example.com") == "a*@example.com"
        
        # Very short email
        assert _redact_email("a@example.com") == "***"
        
        # Long email
        assert _redact_email("testuser123@example.com") == "te********3@example.com"
        
        # Invalid email
        assert _redact_email("notanemail") == "***"
        
        # Empty string
        assert _redact_email("") == "***"

    @pytest.mark.asyncio
    async def test_diagnostics_with_no_data(self, hass):
        """Test diagnostics when coordinator has no data."""
        entry = MagicMock()
        entry.entry_id = "test_entry"
        entry.title = "Test Account"
        entry.version = 1
        entry.data = {"username": "test@example.com"}
        entry.options = {}
        
        mock_coordinator = MagicMock()
        mock_coordinator.last_update_success = False
        mock_coordinator.update_interval = None
        mock_coordinator.data = None
        
        mock_api = MagicMock()
        mock_api.get_diagnostics = AsyncMock(return_value={
            "cookies_cached": False,
            "cookie_expiry": None,
            "rate_limiter_requests": 0,
            "rate_limiter_max": 60,
            "rate_limiter_window": 3600,
        })
        
        hass.data[DOMAIN] = {
            entry.entry_id: {
                DATA_COORDINATOR: mock_coordinator,
                DATA_API: mock_api,
            }
        }
        
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        
        assert diagnostics["coordinator"]["last_update_success"] is False
        assert diagnostics["coordinator"]["data"] == {}
        assert diagnostics["api"]["cookies_cached"] is False
