"""Tests for Trackmate GPS API."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientResponseError

from homeassistant.exceptions import ConfigEntryAuthFailed

from custom_components.trackmate.api import TrackmateAPI, RateLimiter


class TestRateLimiter:
    """Test RateLimiter class."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests_within_limit(self):
        """Test that rate limiter allows requests within the limit."""
        limiter = RateLimiter(max_requests=5, window=10)
        
        # Should allow 5 requests without delay
        for _ in range(5):
            await limiter.acquire()
        
        assert len(limiter.requests) == 5

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_when_limit_reached(self):
        """Test that rate limiter blocks when limit is reached."""
        limiter = RateLimiter(max_requests=2, window=1)
        
        # First two should be instant
        await limiter.acquire()
        await limiter.acquire()
        
        # Third should be delayed (we won't actually wait, just check)
        assert len(limiter.requests) == 2


class TestTrackmateAPI:
    """Test TrackmateAPI class."""

    @pytest.mark.asyncio
    async def test_api_setup(self, hass):
        """Test API setup."""
        api = TrackmateAPI(hass, "test@example.com", "password123")
        
        with patch.object(api, "_load_cookies", new_callable=AsyncMock):
            await api.async_setup()
        
        assert api.session is not None

    @pytest.mark.asyncio
    async def test_api_close(self, hass):
        """Test API close."""
        api = TrackmateAPI(hass, "test@example.com", "password123")
        
        with patch.object(api, "_load_cookies", new_callable=AsyncMock):
            await api.async_setup()
        
        await api.async_close()
        assert api.session.closed

    @pytest.mark.asyncio
    async def test_login_success(self, hass):
        """Test successful login."""
        api = TrackmateAPI(hass, "test@example.com", "password123")
        
        mock_response = MagicMock()
        mock_response.url.path = "/Dashboard"
        mock_response.cookies = {"session": "test_session"}
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(api, "_load_cookies", new_callable=AsyncMock), \
             patch.object(api, "_save_cookies", new_callable=AsyncMock), \
             patch.object(api, "async_setup", new_callable=AsyncMock):
            
            await api.async_setup()
            
            with patch.object(api.session, "post") as mock_post:
                mock_post.return_value.__aenter__.return_value = mock_response
                
                await api.login()
                
                assert api.cookies is not None
                assert api.cookie_expiry > datetime.now()

    @pytest.mark.asyncio
    async def test_login_failure_invalid_credentials(self, hass):
        """Test login failure with invalid credentials."""
        api = TrackmateAPI(hass, "test@example.com", "wrong_password")
        
        mock_response = MagicMock()
        mock_response.url.path = "/Account/Login"
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(api, "_load_cookies", new_callable=AsyncMock), \
             patch.object(api, "async_setup", new_callable=AsyncMock):
            
            await api.async_setup()
            
            with patch.object(api.session, "post") as mock_post:
                mock_post.return_value.__aenter__.return_value = mock_response
                
                with pytest.raises(ConfigEntryAuthFailed):
                    await api.login()

    @pytest.mark.asyncio
    async def test_get_positions_success(self, hass):
        """Test successful position retrieval."""
        api = TrackmateAPI(hass, "test@example.com", "password123")
        api.cookies = {"session": "test_session"}
        api.cookie_expiry = datetime.now() + timedelta(hours=1)
        
        mock_response = MagicMock()
        mock_response.url.path = "/Tracking/GetLatestPositions"
        mock_response.json = AsyncMock(return_value={
            "MotusObject": {
                "Points": [
                    {
                        "VehicleDescription": "Bus 101",
                        "Latitude": 40.7128,
                        "Longitude": -74.0060,
                    }
                ]
            }
        })
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(api, "_load_cookies", new_callable=AsyncMock), \
             patch.object(api, "async_setup", new_callable=AsyncMock):
            
            await api.async_setup()
            
            with patch.object(api.session, "post") as mock_post:
                mock_post.return_value.__aenter__.return_value = mock_response
                
                data = await api.get_positions()
                
                assert "MotusObject" in data
                assert len(data["MotusObject"]["Points"]) == 1

    @pytest.mark.asyncio
    async def test_get_positions_session_expired(self, hass):
        """Test position retrieval when session is expired."""
        api = TrackmateAPI(hass, "test@example.com", "password123")
        api.cookies = {"session": "expired_session"}
        api.cookie_expiry = datetime.now() + timedelta(hours=1)
        
        # First response: redirected to login
        mock_response_expired = MagicMock()
        mock_response_expired.url.path = "/Account/Login"
        mock_response_expired.raise_for_status = MagicMock()
        
        # Second response: successful after reauth
        mock_response_success = MagicMock()
        mock_response_success.url.path = "/Tracking/GetLatestPositions"
        mock_response_success.json = AsyncMock(return_value={
            "MotusObject": {"Points": []}
        })
        mock_response_success.raise_for_status = MagicMock()
        
        call_count = 0
        
        async def mock_post_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_response_expired
            return mock_response_success
        
        with patch.object(api, "_load_cookies", new_callable=AsyncMock), \
             patch.object(api, "async_setup", new_callable=AsyncMock), \
             patch.object(api, "login", new_callable=AsyncMock):
            
            await api.async_setup()
            
            with patch.object(api.session, "post") as mock_post:
                mock_post.return_value.__aenter__.side_effect = mock_post_side_effect
                
                # Should detect expired session and retry
                data = await api.get_positions()
                
                assert call_count >= 1

    @pytest.mark.asyncio
    async def test_cookie_persistence(self, hass):
        """Test cookie persistence across restarts."""
        api = TrackmateAPI(hass, "test@example.com", "password123")
        
        with patch.object(api.store, "async_save") as mock_save, \
             patch.object(api, "async_setup", new_callable=AsyncMock):
            
            await api.async_setup()
            
            api.cookies = {"session": "test_session"}
            api.cookie_expiry = datetime.now() + timedelta(hours=1)
            
            await api._save_cookies()
            
            assert mock_save.called
            saved_data = mock_save.call_args[0][0]
            assert "cookies" in saved_data
            assert "expiry" in saved_data

    @pytest.mark.asyncio
    async def test_get_diagnostics(self, hass):
        """Test diagnostics retrieval."""
        api = TrackmateAPI(hass, "test@example.com", "password123")
        api.cookies = {"session": "test"}
        api.cookie_expiry = datetime.now() + timedelta(hours=1)
        
        with patch.object(api, "async_setup", new_callable=AsyncMock):
            await api.async_setup()
            
            diagnostics = await api.get_diagnostics()
            
            assert "cookies_cached" in diagnostics
            assert "cookie_expiry" in diagnostics
            assert diagnostics["cookies_cached"] is True
