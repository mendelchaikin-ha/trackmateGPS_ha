"""Trackmate GPS API client - Self-contained with automatic cookie management."""
import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from collections import deque
import json

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_interval

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
        
        while self.requests and (now - self.requests[0]).total_seconds() > self.window:
            self.requests.popleft()
        
        if len(self.requests) >= self.max_requests:
            oldest_request = self.requests[0]
            wait_time = self.window - (now - oldest_request).total_seconds()
            if wait_time > 0:
                _LOGGER.debug("Rate limit reached. Waiting %.2f seconds", wait_time)
                await asyncio.sleep(wait_time)
                await self.acquire()
                return
        
        self.requests.append(now)


class TrackmateAPI:
    """Trackmate GPS API client with automatic cookie management."""

    LOGIN_URL = "https://trackmategps.com/Account/Login"
    DATA_URL = "https://trackmategps.com/en-US/Tracking/GetLatestPositions"

    def __init__(self, hass: HomeAssistant, username: str, password: str, entry_id: Optional[str] = None):
        """Initialize the API client."""
        self.hass = hass
        self.username = username
        self.password = password
        self.entry_id = entry_id or "temp"
        self.session: Optional[aiohttp.ClientSession] = None
        self.cookies: Optional[Dict[str, str]] = None
        self.cookie_expiry: Optional[datetime] = None
        self.store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{self.entry_id}")
        self.rate_limiter = RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)
        self._login_lock = asyncio.Lock()
        self._refresh_task = None
        self._refresh_unsub = None

    async def async_setup(self):
        """Set up the API client."""
        _LOGGER.error("!!! ASYNC_SETUP CALLED !!!")
        _LOGGER.info("Setting up Trackmate API client for %s (entry_id: %s)", self.username, self.entry_id)
        
        # Create session with relaxed SSL (some HA installations have SSL issues)
        _LOGGER.error("!!! Creating SSL context !!!")
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        _LOGGER.error("!!! Creating connector with system DNS !!!")
        # Use ThreadedResolver instead of aiodns (which times out)
        from aiohttp.resolver import ThreadedResolver
        resolver = ThreadedResolver()
        
        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            resolver=resolver  # Use threaded (system) DNS resolver
        )
        
        _LOGGER.error("!!! Creating session !!!")
        self.session = aiohttp.ClientSession(connector=connector)
        _LOGGER.debug("HTTP session created (using system DNS resolver)")
        
        _LOGGER.error("!!! Loading cookies !!!")
        await self._load_cookies()
        
        _LOGGER.error("!!! Setup complete !!!")
        
        # Only start background refresh if this is a real entry (not validation)
        if self.entry_id != "temp":
            self._start_cookie_refresh_timer()
            _LOGGER.info("Background cookie refresh scheduled")
        else:
            _LOGGER.debug("Skipping background refresh setup for validation")

    async def async_close(self):
        """Close the API client."""
        # Stop background refresh
        if self._refresh_unsub:
            self._refresh_unsub()
        
        if self.session:
            await self.session.close()

    def _start_cookie_refresh_timer(self):
        """Start the automatic cookie refresh timer."""
        # Refresh every 11 hours
        refresh_interval = timedelta(hours=11)
        
        async def _refresh_cookies_task(now):
            """Background task to refresh cookies."""
            try:
                _LOGGER.info("Background cookie refresh triggered")
                await self._refresh_cookies()
            except Exception as err:
                _LOGGER.error("Background cookie refresh failed: %s", err)
        
        # Schedule the refresh
        self._refresh_unsub = async_track_time_interval(
            self.hass,
            _refresh_cookies_task,
            refresh_interval
        )
        _LOGGER.info("Cookie auto-refresh scheduled every 11 hours")

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
                await self.store.async_save({
                    "cookies": self.cookies,
                    "expiry": self.cookie_expiry.isoformat(),
                })
                _LOGGER.debug("Saved cookies to storage")
            except Exception as err:
                _LOGGER.warning("Failed to save cookies to storage: %s", err)

    async def _http_login(self) -> Dict[str, str]:
        """Login using direct HTTP requests (no browser needed)."""
        _LOGGER.info("==> _http_login() ENTERED <==")
        _LOGGER.info("Logging in to Trackmate via HTTP...")
        _LOGGER.debug("Username: %s", self.username)
        _LOGGER.debug("Login URL: %s", self.LOGIN_URL)
        
        # Quick connectivity test first
        try:
            _LOGGER.info("Testing basic connectivity...")
            async with self.session.get(
                "https://trackmategps.com/",
                timeout=aiohttp.ClientTimeout(total=5),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                }
            ) as test_resp:
                _LOGGER.info("✓ Connectivity OK - status %d", test_resp.status)
        except Exception as e:
            _LOGGER.error("✗ Connectivity test failed: %s", e)
            raise ConfigEntryAuthFailed(f"Cannot reach trackmategps.com: {e}")
        
        try:
            # Step 1: GET login page to get CSRF token
            _LOGGER.debug("Step 1: Getting login page for CSRF token")
            _LOGGER.debug("About to make GET request to %s", self.LOGIN_URL)
            
            async with self.session.get(
                self.LOGIN_URL,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                }
            ) as resp:
                _LOGGER.debug("GET request completed!")
                _LOGGER.debug("Login page response status: %d", resp.status)
                resp.raise_for_status()
                html = await resp.text()
                _LOGGER.debug("Login page HTML length: %d", len(html))
                
                # Log first 500 chars to see what we're getting
                _LOGGER.debug("HTML preview: %s", html[:500])
                
                # Extract CSRF token
                import re
                csrf_match = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html)
                csrf_token = csrf_match.group(1) if csrf_match else ""
                _LOGGER.debug("CSRF token found: %s", "Yes" if csrf_token else "No")
                
                # Also look for what input fields exist
                email_field = "Email" in html
                username_field = "Username" in html or "username" in html
                _LOGGER.debug("Form has 'Email' field: %s", email_field)
                _LOGGER.debug("Form has 'Username' field: %s", username_field)
            
            # Step 2: POST login credentials
            _LOGGER.debug("Step 2: Posting login credentials")
            
            # Determine if this is an email or username login
            is_email = "@" in self.username
            
            # Build login data based on login type
            if is_email:
                _LOGGER.debug("Detected email format - using Email field")
                login_data = {
                    "Email": self.username,
                    "Password": self.password,
                }
            else:
                _LOGGER.debug("Detected username format - using Username field")
                login_data = {
                    "Username": self.username,
                    "Password": self.password,
                }
            
            if csrf_token:
                login_data["__RequestVerificationToken"] = csrf_token
            
            _LOGGER.debug("Login data prepared with fields: %s", list(login_data.keys()))
            
            async with self.session.post(
                self.LOGIN_URL,
                data=login_data,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://trackmategps.com",
                    "Referer": self.LOGIN_URL,
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-User": "?1",
                    "Cache-Control": "max-age=0",
                }
            ) as resp:
                _LOGGER.debug("Login POST response status: %d", resp.status)
                _LOGGER.debug("Final URL after redirects: %s", resp.url)
                
                # Read response HTML for debugging
                response_html = await resp.text()
                _LOGGER.debug("Response HTML length: %d", len(response_html))
                
                # If we hit an error page, log the content
                if "Error" in str(resp.url) or "error" in str(resp.url).lower():
                    _LOGGER.error("Error page HTML (first 1000 chars): %s", response_html[:1000])
                
                # Check if redirected to tracking page (success)
                if "Tracking" in str(resp.url):
                    _LOGGER.info("Login successful! Redirected to: %s", resp.url)
                    
                    # Extract cookies from session
                    cookies = {}
                    for cookie in self.session.cookie_jar:
                        cookies[cookie.key] = cookie.value
                    
                    _LOGGER.info("Got %d cookies", len(cookies))
                    
                    if not cookies:
                        _LOGGER.error("No cookies received after login!")
                        raise ConfigEntryAuthFailed("Login succeeded but no cookies received")
                    
                    return cookies
                    
                elif "Error" in str(resp.url) or "Login" in str(resp.url):
                    _LOGGER.error("Login failed - redirected to: %s", resp.url)
                    raise ConfigEntryAuthFailed("Invalid credentials or login rejected")
                else:
                    _LOGGER.warning("Unexpected redirect: %s", resp.url)
                    raise ConfigEntryAuthFailed("Unexpected login response")
                    
        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP error during login: %s (type: %s)", err, type(err).__name__)
            _LOGGER.exception("Full traceback:")
            raise ConfigEntryAuthFailed(f"Network error: {err}")
        except asyncio.TimeoutError:
            _LOGGER.error("Login timed out after 30 seconds")
            _LOGGER.error("This usually means network connectivity issue or DNS problem")
            raise ConfigEntryAuthFailed("Login timeout - check network connectivity")
        except Exception as err:
            _LOGGER.error("Unexpected error during login: %s (type: %s)", err, type(err).__name__)
            _LOGGER.exception("Full traceback:")
            raise ConfigEntryAuthFailed(f"Login failed: {err}")

    async def _refresh_cookies(self):
        """Refresh authentication cookies."""
        _LOGGER.info("==> _refresh_cookies() START <==")
        
        async with self._login_lock:
            _LOGGER.info("==> Login lock acquired!")
            _LOGGER.info("==> About to acquire rate limiter...")
            
            await self.rate_limiter.acquire()
            
            _LOGGER.info("==> Rate limiter acquired!")
            
            try:
                _LOGGER.info("==> About to call _http_login()")
                _LOGGER.info("==> Session object: %s", self.session)
                _LOGGER.info("==> Session closed: %s", self.session.closed if self.session else "No session")
                
                self.cookies = await self._http_login()
                
                _LOGGER.info("==> _http_login() returned!")
                _LOGGER.debug("_http_login() returned successfully")
                self.cookie_expiry = datetime.now() + timedelta(hours=COOKIE_EXPIRY_HOURS)
                await self._save_cookies()
                _LOGGER.info("Cookies refreshed successfully, valid until %s", self.cookie_expiry)
                
                # Send notification to user (only for real entries, not validation)
                if self.entry_id != "temp":
                    await self.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "Trackmate GPS",
                            "message": f"Cookies refreshed successfully for {self.username}",
                            "notification_id": f"trackmate_{self.entry_id}"
                        }
                    )
                    
            except Exception as err:
                _LOGGER.error("Failed to refresh cookies: %s", err)
                # Send error notification (only for real entries)
                if self.entry_id != "temp":
                    await self.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "⚠️ Trackmate GPS Error",
                            "message": f"Failed to refresh cookies for {self.username}: {err}",
                            "notification_id": f"trackmate_error_{self.entry_id}"
                        }
                    )
                raise

    async def login(self):
        """Ensure we have valid cookies."""
        _LOGGER.debug("login() called")
        
        # Check if we have valid cookies
        if self.cookies and self.cookie_expiry:
            time_until_expiry = (self.cookie_expiry - datetime.now()).total_seconds()
            if time_until_expiry > COOKIE_REFRESH_BEFORE_EXPIRY:
                _LOGGER.debug("Using cached cookies (valid for %.0f more seconds)", time_until_expiry)
                return

        # Need to refresh
        _LOGGER.debug("Need to refresh cookies, calling _refresh_cookies()")
        await self._refresh_cookies()

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
                # Check if redirected to login (cookies expired)
                if "/Login" in str(resp.url) or "/Account/Login" in str(resp.url):
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
            if err.status in (401, 403):
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
        _LOGGER.error("!!! TEST_CONNECTION CALLED !!!")
        _LOGGER.info("Testing Trackmate API connection...")
        
        try:
            _LOGGER.error("!!! Step 1: Calling login() !!!")
            await self.login()
            
            _LOGGER.error("!!! Step 2: Login succeeded, calling get_positions() !!!")
            await self.get_positions()
            
            _LOGGER.error("!!! Step 3: Everything succeeded !!!")
            _LOGGER.info("Connection test PASSED")
            return True
            
        except ConfigEntryAuthFailed as err:
            _LOGGER.error("!!! TEST FAILED: ConfigEntryAuthFailed: %s !!!", err)
            _LOGGER.exception("Full traceback:")
            raise  # Re-raise so config_flow sees it
            
        except Exception as err:
            _LOGGER.error("!!! TEST FAILED: Unexpected error: %s (type: %s) !!!", err, type(err).__name__)
            _LOGGER.exception("Full traceback:")
            raise  # Re-raise so config_flow sees it

    async def get_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostic information."""
        return {
            "cookies_cached": self.cookies is not None,
            "cookie_expiry": self.cookie_expiry.isoformat() if self.cookie_expiry else None,
            "rate_limiter_requests": len(self.rate_limiter.requests),
            "rate_limiter_max": self.rate_limiter.max_requests,
            "rate_limiter_window": self.rate_limiter.window,
            "username": self.username,
            "auto_refresh_enabled": self._refresh_unsub is not None,
        }
