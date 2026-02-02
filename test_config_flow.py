"""Tests for Trackmate GPS config flow."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.trackmate.const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_LABEL
from custom_components.trackmate.config_flow import (
    TrackmateConfigFlow,
    CannotConnect,
    InvalidAuth,
)


class TestConfigFlow:
    """Test Trackmate config flow."""

    @pytest.mark.asyncio
    async def test_user_flow_success(self, hass):
        """Test successful user flow."""
        flow = TrackmateConfigFlow()
        flow.hass = hass
        
        # Show form
        result = await flow.async_step_user()
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        
        # Submit valid credentials
        with patch.object(flow, "_validate_credentials", new_callable=AsyncMock):
            result = await flow.async_step_user({
                CONF_LABEL: "Test Account",
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "password123",
            })
        
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Test Account"
        assert result["data"][CONF_USERNAME] == "test@example.com"

    @pytest.mark.asyncio
    async def test_user_flow_invalid_auth(self, hass):
        """Test user flow with invalid credentials."""
        flow = TrackmateConfigFlow()
        flow.hass = hass
        
        # Submit invalid credentials
        with patch.object(flow, "_validate_credentials", side_effect=InvalidAuth):
            result = await flow.async_step_user({
                CONF_LABEL: "Test Account",
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "wrong_password",
            })
        
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_auth"

    @pytest.mark.asyncio
    async def test_user_flow_cannot_connect(self, hass):
        """Test user flow when cannot connect."""
        flow = TrackmateConfigFlow()
        flow.hass = hass
        
        # Submit when network is down
        with patch.object(flow, "_validate_credentials", side_effect=CannotConnect):
            result = await flow.async_step_user({
                CONF_LABEL: "Test Account",
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "password123",
            })
        
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_reauth_flow_success(self, hass):
        """Test successful reauth flow."""
        # Create existing entry
        entry = MagicMock()
        entry.entry_id = "test_entry"
        entry.data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "old_password",
            CONF_LABEL: "Test Account",
        }
        entry.title = "Test Account"
        
        flow = TrackmateConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "test_entry"}
        
        with patch.object(
            hass.config_entries,
            "async_get_entry",
            return_value=entry,
        ):
            # Start reauth
            result = await flow.async_step_reauth(entry.data)
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "reauth_confirm"
            
            # Submit new credentials
            with patch.object(flow, "_validate_credentials", new_callable=AsyncMock), \
                 patch.object(hass.config_entries, "async_update_entry"), \
                 patch.object(hass.config_entries, "async_reload"):
                
                result = await flow.async_step_reauth_confirm({
                    CONF_USERNAME: "test@example.com",
                    CONF_PASSWORD: "new_password",
                })
            
            assert result["type"] == FlowResultType.ABORT
            assert result["reason"] == "reauth_successful"

    @pytest.mark.asyncio
    async def test_reauth_flow_invalid_auth(self, hass):
        """Test reauth flow with invalid credentials."""
        entry = MagicMock()
        entry.entry_id = "test_entry"
        entry.data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "old_password",
            CONF_LABEL: "Test Account",
        }
        entry.title = "Test Account"
        
        flow = TrackmateConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "test_entry"}
        
        with patch.object(
            hass.config_entries,
            "async_get_entry",
            return_value=entry,
        ):
            result = await flow.async_step_reauth(entry.data)
            
            # Submit invalid credentials
            with patch.object(flow, "_validate_credentials", side_effect=InvalidAuth):
                result = await flow.async_step_reauth_confirm({
                    CONF_USERNAME: "test@example.com",
                    CONF_PASSWORD: "wrong_password",
                })
            
            assert result["type"] == FlowResultType.FORM
            assert result["errors"]["base"] == "invalid_auth"

    @pytest.mark.asyncio
    async def test_validate_credentials_success(self, hass):
        """Test credential validation success."""
        flow = TrackmateConfigFlow()
        flow.hass = hass
        
        mock_api = MagicMock()
        mock_api.async_setup = AsyncMock()
        mock_api.async_close = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        
        with patch(
            "custom_components.trackmate.config_flow.TrackmateAPI",
            return_value=mock_api,
        ):
            await flow._validate_credentials("test@example.com", "password123")
            
            assert mock_api.async_setup.called
            assert mock_api.test_connection.called
            assert mock_api.async_close.called

    @pytest.mark.asyncio
    async def test_validate_credentials_failure(self, hass):
        """Test credential validation failure."""
        flow = TrackmateConfigFlow()
        flow.hass = hass
        
        mock_api = MagicMock()
        mock_api.async_setup = AsyncMock()
        mock_api.async_close = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=False)
        
        with patch(
            "custom_components.trackmate.config_flow.TrackmateAPI",
            return_value=mock_api,
        ):
            with pytest.raises(InvalidAuth):
                await flow._validate_credentials("test@example.com", "wrong_password")

    @pytest.mark.asyncio
    async def test_unique_id_already_configured(self, hass):
        """Test that duplicate usernames are rejected."""
        flow = TrackmateConfigFlow()
        flow.hass = hass
        
        # Mock existing entry with same username
        with patch.object(flow, "_abort_if_unique_id_configured", side_effect=Exception("Already configured")):
            with patch.object(flow, "_validate_credentials", new_callable=AsyncMock):
                with pytest.raises(Exception, match="Already configured"):
                    await flow.async_step_user({
                        CONF_LABEL: "Test Account",
                        CONF_USERNAME: "test@example.com",
                        CONF_PASSWORD: "password123",
                    })
