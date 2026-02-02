"""Tests for Trackmate GPS coordinator and integration."""
import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.trackmate import async_setup_entry, async_unload_entry
from custom_components.trackmate.coordinator import TrackmateCoordinator
from custom_components.trackmate.const import DOMAIN, DATA_COORDINATOR, DATA_API


class TestCoordinator:
    """Test TrackmateCoordinator."""

    @pytest.mark.asyncio
    async def test_coordinator_update_success(self, hass, mock_api):
        """Test successful coordinator update."""
        coordinator = TrackmateCoordinator(hass, mock_api, scan_interval=30)
        
        data = await coordinator._async_update_data()
        
        assert "MotusObject" in data
        assert "Points" in data["MotusObject"]
        assert len(data["MotusObject"]["Points"]) == 2

    @pytest.mark.asyncio
    async def test_coordinator_update_invalid_data(self, hass, mock_api):
        """Test coordinator update with invalid data."""
        mock_api.get_positions = AsyncMock(return_value={})
        
        coordinator = TrackmateCoordinator(hass, mock_api, scan_interval=30)
        
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_coordinator_update_auth_failed(self, hass, mock_api):
        """Test coordinator update when auth fails."""
        mock_api.get_positions = AsyncMock(side_effect=ConfigEntryAuthFailed)
        
        coordinator = TrackmateCoordinator(hass, mock_api, scan_interval=30)
        
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_coordinator_update_scan_interval(self, hass, mock_api):
        """Test updating scan interval."""
        coordinator = TrackmateCoordinator(hass, mock_api, scan_interval=30)
        
        assert coordinator.update_interval == timedelta(seconds=30)
        
        coordinator.update_scan_interval(60)
        
        assert coordinator.update_interval == timedelta(seconds=60)


class TestIntegrationSetup:
    """Test integration setup and lifecycle."""

    @pytest.mark.asyncio
    async def test_setup_entry_success(self, hass, mock_config_entry):
        """Test successful setup."""
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
        ), patch(
            "custom_components.trackmate.hass.config_entries.async_forward_entry_setups",
            new_callable=AsyncMock,
        ) as mock_forward:
            
            result = await async_setup_entry(hass, mock_config_entry)
            
            assert result is True
            assert DOMAIN in hass.data
            assert mock_config_entry.entry_id in hass.data[DOMAIN]
            assert DATA_COORDINATOR in hass.data[DOMAIN][mock_config_entry.entry_id]
            assert DATA_API in hass.data[DOMAIN][mock_config_entry.entry_id]

    @pytest.mark.asyncio
    async def test_setup_entry_auth_failed(self, hass, mock_config_entry):
        """Test setup with auth failure."""
        mock_api = MagicMock()
        mock_api.async_setup = AsyncMock()
        mock_api.async_close = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=False)
        
        with patch(
            "custom_components.trackmate.TrackmateAPI",
            return_value=mock_api,
        ):
            with pytest.raises(ConfigEntryAuthFailed):
                await async_setup_entry(hass, mock_config_entry)
            
            # Verify cleanup
            assert mock_api.async_close.called

    @pytest.mark.asyncio
    async def test_setup_entry_not_ready(self, hass, mock_config_entry):
        """Test setup when not ready."""
        mock_api = MagicMock()
        mock_api.async_setup = AsyncMock(side_effect=Exception("Network error"))
        mock_api.async_close = AsyncMock()
        
        with patch(
            "custom_components.trackmate.TrackmateAPI",
            return_value=mock_api,
        ):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(hass, mock_config_entry)
            
            # Verify cleanup
            assert mock_api.async_close.called

    @pytest.mark.asyncio
    async def test_unload_entry_success(self, hass, mock_config_entry):
        """Test successful unload."""
        # Set up first
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
        ), patch(
            "custom_components.trackmate.hass.config_entries.async_forward_entry_setups",
            new_callable=AsyncMock,
        ):
            await async_setup_entry(hass, mock_config_entry)
        
        # Now unload
        with patch(
            "custom_components.trackmate.hass.config_entries.async_unload_platforms",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await async_unload_entry(hass, mock_config_entry)
            
            assert result is True
            assert mock_api.async_close.called
            assert mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})

    @pytest.mark.asyncio
    async def test_unload_entry_failed(self, hass, mock_config_entry):
        """Test failed unload."""
        # Set up first
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
        ), patch(
            "custom_components.trackmate.hass.config_entries.async_forward_entry_setups",
            new_callable=AsyncMock,
        ):
            await async_setup_entry(hass, mock_config_entry)
        
        # Now unload with failure
        with patch(
            "custom_components.trackmate.hass.config_entries.async_unload_platforms",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await async_unload_entry(hass, mock_config_entry)
            
            assert result is False
            # Data should still be there since unload failed
            assert mock_config_entry.entry_id in hass.data.get(DOMAIN, {})
