"""Trackmate GPS API client with enterprise features."""
import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from collections import deque

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    STORAGE_VERSION,
    STORAGE_KEY,
    COOKIE_EXPIRY_HOURS,
    COOKIE_REFRESH_BEFORE_EXPIRY,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW,
)

_LOGGER = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter to prevent API bans."""

    def __init__(self, max_requests: int, window: int):
        """Initialize rate limiter."""
        self.max_requests = max_requests
        self.window = window
        self.requests = deque()

    async def acquire(self):
        """Wait if necessary to respect rate limits."""
        now = datetime.now()
        
        # Remove old requests outside the window
        while self.requests and (now - self.requests[0]).total_seconds() > self.window:
            self.requests.popleft()
        
        # If we're at the limit, wait
        if len(self.requests) >= self.max_requests:
            oldest_request = self.requests[0]
            wait_time = self.window - (now - oldest_request).total_seconds()
            if wait_time > 0:
                _LOGGER.debug(
                    "Rate limit reached. Waiting %.2f seconds before next request",
                    wait_time,
                )
                await asyncio.sleep(wait_time)
                # Recursively try again
                await self.acquire()
                return
        
        # Record this request
        self.requests.append(now)


class TrackmateAPI:
    """Trackmate GPS API client."""

    LOGIN_URL = "https://trackmategps.com/Account/Login"
    DATA_URL = "https://trackmategps.com/en-US/Tracking/GetLatestPositions"

    def __init__(self, hass: HomeAssistant, username: str, password: str):
        """Initialize the API client."""
        self.hass = hass
        self.username = username
        self.password = password
        self.session: Optional[aiohttp.ClientSession] = None
        self.cookies: Optional[Dict] = None
        self.cookie_expiry: Optional[datetime] = None
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.rate_limiter = RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)
        self._login_lock = asyncio.Lock()

    async def async_setup(self):
        """Set up the API client."""
        self.session = aiohttp.ClientSession()
        await self._load_cookies()

    async def async_close(self):
        """Close the API client."""
        if self.session:
            await self.session.close()

    async def _load_cookies(self):
        """Load cookies from persistent storage."""
        try:
            data = await self.store.async_load()
            if data:
                self.cookies = data.get("cookies")
                expiry_str = data.get("expiry")
                if expiry_str:
                    self.cookie_expiry = datetime.fromisoformat(expiry_str)
                    _LOGGER.debug("Loaded cookies from storage, expiry: %s", self.cookie_expiry)
                    
                    # Check if cookies are still valid
                    if datetime.now() >= self.cookie_expiry:
                        _LOGGER.info("Stored cookies expired, will re-authenticate")
                        self.cookies = None
                        self.cookie_expiry = None
        except Exception as err:
            _LOGGER.warning("Failed to load cookies from storage: %s", err)

    async def _save_cookies(self):
        """Save cookies to persistent storage."""
        if self.cookies and self.cookie_expiry:
            try:
                # Convert cookies to serializable format
                cookie_dict = {}
                
                # Handle both dict and SimpleCookie types
                if isinstance(self.cookies, dict):
                    # Already a dict, but might contain Morsel objects
                    for key, value in self.cookies.items():
                        if hasattr(value, 'value'):
                            cookie_dict[key] = value.value
                        else:
                            cookie_dict[key] = str(value)
                else:
                    # SimpleCookie or similar
                    for key, morsel in self.cookies.items():
                        cookie_dict[key] = morsel.value if hasattr(morsel, 'value') else str(morsel)
                
                await self.store.async_save({
                    "cookies": cookie_dict,
                    "expiry": self.cookie_expiry.isoformat(),
                })
                _LOGGER.debug("Saved cookies to storage")
            except Exception as err:
                _LOGGER.warning("Failed to save cookies to storage: %s", err)

    async def login(self):
        """Login to Trackmate GPS (no CSRF version)."""
        async with self._login_lock:
            # Check if we have valid cookies
            if self.cookies and self.cookie_expiry:
                time_until_expiry = (self.cookie_expiry - datetime.now()).total_seconds()
                if time_until_expiry > COOKIE_REFRESH_BEFORE_EXPIRY:
                    _LOGGER.debug("Using cached cookies (valid for %.0f more seconds)", time_until_expiry)
                    return

            _LOGGER.info("Logging in to Trackmate GPS")
            await self.rate_limiter.acquire()
            
            payload = {
                "Email": self.username,
                "Password": self.password,
            }
            
            try:
                async with self.session.post(
                    self.LOGIN_URL,
                    data=payload,
                    allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": "https://trackmategps.com",
                        "Referer": self.LOGIN_URL,
                    }
                ) as resp:
                    _LOGGER.debug("Login response: status=%d, url=%s", resp.status, resp.url)
                    
                    final_url = str(resp.url)
                    
                    # Check if still on login page (failed)
                    if "Login" in final_url or "login" in final_url:
                        _LOGGER.error("Login failed - still on login page")
                        raise ConfigEntryAuthFailed("Invalid username or password")
                    
                    # Success - save cookies
                    self.cookies = resp.cookies
                    self.cookie_expiry = datetime.now() + timedelta(hours=COOKIE_EXPIRY_HOURS)
                    
                    _LOGGER.info("Login successful, redirected to: %s", final_url)
                    await self._save_cookies()
                    
            except aiohttp.ClientError as err:
                _LOGGER.error("Network error during login: %s", err)
                raise ConfigEntryAuthFailed(f"Network error: {err}")
            except asyncio.TimeoutError:
                _LOGGER.error("Login request timed out")
                raise ConfigEntryAuthFailed("Login request timed out")

    async def get_positions(self) -> Dict[str, Any]:
        """Get latest vehicle positions."""
        await self.login()
        await self.rate_limiter.acquire()
        
        try:
            async with self.session.post(
                self.DATA_URL,
                data="dummy=1",
                cookies=self.cookies,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": "https://trackmategps.com/en-US/Tracking",
                }
            ) as resp:
                # Check if we got redirected to login (session expired)
                if resp.url.path.endswith("/Login") or "/Account/Login" in str(resp.url):
                    _LOGGER.warning("Session expired, forcing re-authentication")
                    self.cookies = None
                    self.cookie_expiry = None
                    # Retry with fresh login
                    return await self.get_positions()
                
                resp.raise_for_status()
                
                data = await resp.json()
                _LOGGER.debug("Retrieved position data for %d vehicles", 
                            len(data.get("MotusObject", {}).get("Points", [])))
                return data
                
        except aiohttp.ClientResponseError as err:
            if err.status == 401 or err.status == 403:
                _LOGGER.error("Authentication error (status %d), forcing re-auth", err.status)
                self.cookies = None
                self.cookie_expiry = None
                raise ConfigEntryAuthFailed("Session expired or invalid credentials")
            _LOGGER.error("HTTP error getting positions: %s", err)
            raise
        except aiohttp.ClientError as err:
            _LOGGER.error("Network error getting positions: %s", err)
            raise
        except asyncio.TimeoutError:
            _LOGGER.error("Request timed out getting positions")
            raise

    async def test_connection(self) -> bool:
        """Test the API connection."""
        try:
            await self.login()
            await self.get_positions()
            return True
        except ConfigEntryAuthFailed:
            return False
        except Exception as err:
            _LOGGER.error("Connection test failed: %s", err)
            return False

    async def get_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostic information."""
        return {
            "cookies_cached": self.cookies is not None,
            "cookie_expiry": self.cookie_expiry.isoformat() if self.cookie_expiry else None,
            "rate_limiter_requests": len(self.rate_limiter.requests),
            "rate_limiter_max": self.rate_limiter.max_requests,
            "rate_limiter_window": self.rate_limiter.window,
        }