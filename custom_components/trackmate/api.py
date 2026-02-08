"""TrackmateGPS client – uses FlareSolverr for login, aiohttp for scraping."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import quote

import aiohttp
from bs4 import BeautifulSoup

from .const import BASE_URL, LOGIN_URL, MAP_URL

_LOGGER = logging.getLogger(__name__)


class TrackmateError(Exception):
    """Base error."""

class TrackmateConnectionError(TrackmateError):
    """Cannot reach FlareSolverr."""

class TrackmateAuthError(TrackmateError):
    """Login failed."""


class TrackmateClient:
    """One TrackmateGPS account session."""

    def __init__(self, fs_url: str, username: str, password: str) -> None:
        self._fs_url = fs_url
        self._username = username
        self._password = password
        self._session_id = f"tm_{_slug(username.split('@')[0])}"
        self._cookies: dict[str, str] = {}
        self._user_agent: str = ""
        self._logged_in: bool = False
        self._http: aiohttp.ClientSession | None = None

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def _ensure_http(self) -> aiohttp.ClientSession:
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession()
        return self._http

    async def close(self) -> None:
        await self._fs_destroy_session()
        if self._http and not self._http.closed:
            await self._http.close()

    # ── FlareSolverr helpers ──────────────────────────────────────────────

    async def _fs_request(self, body: dict, timeout: int = 90) -> dict:
        """POST to FlareSolverr /v1 endpoint."""
        session = await self._ensure_http()
        try:
            async with session.post(
                self._fs_url, json=body,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise TrackmateConnectionError(
                        f"FlareSolverr returned {resp.status}: {text[:300]}")
                return await resp.json()
        except aiohttp.ClientConnectorError as e:
            raise TrackmateConnectionError(
                f"Cannot reach FlareSolverr at {self._fs_url}. "
                "Is the FlareSolverr addon running?") from e
        except aiohttp.ClientError as e:
            raise TrackmateConnectionError(str(e)) from e

    async def _fs_create_session(self) -> None:
        await self._fs_request({
            "cmd": "sessions.create", "session": self._session_id,
        })

    async def _fs_destroy_session(self) -> None:
        try:
            await self._fs_request({
                "cmd": "sessions.destroy", "session": self._session_id,
            }, timeout=10)
        except Exception:
            pass

    async def _fs_get(self, url: str) -> dict:
        return await self._fs_request({
            "cmd": "request.get", "url": url,
            "session": self._session_id, "maxTimeout": 60000,
        })

    async def _fs_post(self, url: str, post_data: str) -> dict:
        return await self._fs_request({
            "cmd": "request.post", "url": url,
            "postData": post_data,
            "session": self._session_id, "maxTimeout": 60000,
        })

    # ── Login ─────────────────────────────────────────────────────────────

    async def login(self) -> bool:
        """Log into TrackmateGPS via FlareSolverr. Returns True on success."""
        _LOGGER.info("Logging into TrackmateGPS for %s***", self._username[:3])

        try:
            # Fresh session
            await self._fs_destroy_session()
            await self._fs_create_session()

            # 1) GET login page (FlareSolverr handles Cloudflare)
            resp = await self._fs_get(LOGIN_URL)
            if resp.get("status") != "ok":
                raise TrackmateConnectionError(
                    resp.get("message", "FlareSolverr GET failed"))

            sol = resp["solution"]
            html = sol.get("response", "")
            self._user_agent = sol.get("userAgent", "")

            # 2) Parse anti-forgery token + form field names
            soup = BeautifulSoup(html, "html.parser")
            token_el = soup.select_one("input[name='__RequestVerificationToken']")
            token = token_el["value"] if token_el else ""

            uname_field = "Username"
            pwd_field = "Password"
            form = soup.select_one(
                "form[action*='Login'], form#loginForm, form[method='post']")
            if form:
                for inp in form.select("input[type='text'], input[type='email']"):
                    if n := inp.get("name"):
                        uname_field = n
                        break
                for inp in form.select("input[type='password']"):
                    if n := inp.get("name"):
                        pwd_field = n
                        break

            _LOGGER.debug("Form fields: %s / %s, token: %s…",
                          uname_field, pwd_field, token[:20] if token else "none")

            # 3) POST login form
            post_data = (
                f"__RequestVerificationToken={quote(token)}"
                f"&{quote(uname_field)}={quote(self._username)}"
                f"&{quote(pwd_field)}={quote(self._password)}"
            )
            resp2 = await self._fs_post(LOGIN_URL, post_data)
            if resp2.get("status") != "ok":
                raise TrackmateAuthError(
                    resp2.get("message", "FlareSolverr POST failed"))

            sol2 = resp2["solution"]
            final_url = sol2.get("url", "").lower()
            html2 = sol2.get("response", "")

            # 4) Check success
            if "account/login" in final_url:
                soup2 = BeautifulSoup(html2, "html.parser")
                errs = soup2.select(
                    ".validation-summary-errors, .alert-danger, "
                    ".error-message, .text-danger")
                msg = " ".join(e.get_text(strip=True) for e in errs)
                raise TrackmateAuthError(
                    msg or "Still on login page – invalid credentials?")

            # 5) Extract cookies for plain HTTP
            self._cookies = {
                c["name"]: c["value"]
                for c in sol2.get("cookies", [])
            }
            self._logged_in = True
            _LOGGER.info("Login OK – %d cookies, url=%s",
                         len(self._cookies), final_url)
            return True

        except (TrackmateConnectionError, TrackmateAuthError):
            self._logged_in = False
            raise
        except Exception as e:
            self._logged_in = False
            raise TrackmateError(f"Login error: {e}") from e

    @property
    def logged_in(self) -> bool:
        return self._logged_in

    # ── Scrape vehicles ───────────────────────────────────────────────────

    async def get_vehicles(self) -> dict[str, dict[str, Any]]:
        """Fetch vehicle positions. Auto-re-logins on session expiry."""
        if not self._logged_in:
            await self.login()

        vehicles: dict[str, dict[str, Any]] = {}

        # Strategy 1: Probe API endpoints with cookies
        vehicles = await self._probe_api(vehicles)

        # Strategy 2: Parse map page HTML
        if not vehicles:
            vehicles = await self._parse_map(vehicles)

        # Strategy 3: Render map via FlareSolverr (JS-heavy fallback)
        if not vehicles:
            vehicles = await self._fs_render_map(vehicles)

        if not vehicles:
            _LOGGER.warning("No vehicles found for %s***", self._username[:3])

        return vehicles

    async def _http_get(self, url: str, **kw) -> aiohttp.ClientResponse:
        """Authenticated GET with cookies."""
        session = await self._ensure_http()
        headers = {"User-Agent": self._user_agent} if self._user_agent else {}
        headers.update(kw.pop("headers", {}))
        return await session.get(
            url, cookies=self._cookies, headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
            allow_redirects=False, **kw)

    async def _probe_api(self, vehicles: dict) -> dict:
        """Try known XHR/API endpoints."""
        endpoints = [
            "/en/Map/GetVehicles", "/en/Map/GetDevices",
            "/en/Map/GetPositions", "/en/Map/GetMarkers",
            "/en/Map/LoadVehicles", "/en/Map/LoadDevices",
            "/en/Vehicle/GetAll", "/en/Device/GetAll",
            "/en/Home/GetVehicles",
            "/Map/GetVehicles", "/Map/GetDevices",
            "/api/vehicles", "/api/devices", "/api/positions",
            "/en/api/vehicles", "/en/api/devices",
        ]
        xhr_headers = {
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        }
        for ep in endpoints:
            try:
                resp = await self._http_get(
                    f"{BASE_URL}{ep}", headers=xhr_headers)
                # Session expired → redirect to login
                if resp.status == 302:
                    loc = resp.headers.get("Location", "").lower()
                    if "login" in loc:
                        _LOGGER.info("Session expired, re-logging in")
                        self._logged_in = False
                        await self.login()
                        return await self._probe_api({})
                if resp.status != 200:
                    continue
                ct = resp.headers.get("Content-Type", "")
                if "json" not in ct and "javascript" not in ct:
                    continue
                data = await resp.json()
                _LOGGER.info("Hit API endpoint %s", ep)
                vehicles = _merge(f"api_{ep}", data, vehicles)
                if vehicles:
                    return vehicles
            except (aiohttp.ClientError, ValueError):
                continue
        return vehicles

    async def _parse_map(self, vehicles: dict) -> dict:
        """GET the map page, parse embedded vehicle data."""
        try:
            resp = await self._http_get(MAP_URL)
            if resp.status == 302:
                loc = resp.headers.get("Location", "").lower()
                if "login" in loc:
                    self._logged_in = False
                    await self.login()
                    return await self._parse_map({})
            if resp.status != 200:
                return vehicles
            text = await resp.text()
        except aiohttp.ClientError:
            return vehicles

        soup = BeautifulSoup(text, "html.parser")

        for script in soup.find_all("script"):
            src = script.string or ""
            if not src:
                continue
            # JS variable assignments containing arrays/objects
            for pat in [
                r'(?:var\s+)?(?:vehicles|devices|markers|positions|'
                r'vehicleList|deviceList|markerList)'
                r'\s*=\s*(\[.*?\]);',
                r'(?:var\s+)?(?:vehicleData|deviceData|mapData|'
                r'positionData)\s*=\s*(\{.*?\});',
                r"JSON\.parse\s*\(\s*['\"](\[.*?\])['\"]\s*\)",
            ]:
                for m in re.findall(pat, src, re.DOTALL):
                    try:
                        vehicles = _merge("html_js", json.loads(m), vehicles)
                    except (json.JSONDecodeError, TypeError):
                        pass
            # Raw lat/lng pairs
            for lat, lng in re.findall(
                r'(?:lat(?:itude)?)\s*[:=]\s*(-?\d+\.?\d*)\s*[,;]\s*'
                r'(?:lng|lon(?:gitude)?)\s*[:=]\s*(-?\d+\.?\d*)',
                src, re.I,
            ):
                la, lo = float(lat), float(lng)
                if -90 <= la <= 90 and -180 <= lo <= 180:
                    vid = f"vehicle_{len(vehicles)+1}"
                    vehicles[vid] = _vdict(vid, vid, la, lo, source="html_regex")

        # DOM data attributes
        for el in soup.select("[data-lat],[data-latitude]"):
            la = el.get("data-lat") or el.get("data-latitude")
            lo = el.get("data-lng") or el.get("data-lon") or el.get("data-longitude")
            nm = el.get("data-name") or el.get("title") or el.get_text(strip=True)
            if la and lo:
                vid = _slug(nm or f"vehicle_{len(vehicles)+1}")
                vehicles[vid] = _vdict(
                    vid, nm or vid, float(la), float(lo),
                    speed=el.get("data-speed"), heading=el.get("data-heading"),
                    source="html_dom")

        return vehicles

    async def _fs_render_map(self, vehicles: dict) -> dict:
        """Use FlareSolverr to render the JS-heavy map page."""
        try:
            resp = await self._fs_get(MAP_URL)
        except TrackmateError:
            return vehicles

        if resp.get("status") != "ok":
            return vehicles
        sol = resp.get("solution", {})
        html = sol.get("response", "")

        if "account/login" in sol.get("url", "").lower():
            self._logged_in = False
            return vehicles

        # Refresh cookies
        for c in sol.get("cookies", []):
            self._cookies[c["name"]] = c["value"]

        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script"):
            src = script.string or ""
            for pat in [
                r'(?:var\s+)?(?:vehicles|devices|markers|positions|'
                r'vehicleList|deviceList)\s*=\s*(\[.*?\]);',
                r'(?:var\s+)?(?:vehicleData|mapData)\s*=\s*(\{.*?\});',
            ]:
                for m in re.findall(pat, src, re.DOTALL):
                    try:
                        vehicles = _merge("fs_render", json.loads(m), vehicles)
                    except (json.JSONDecodeError, TypeError):
                        pass

        for el in soup.select("[data-lat],[data-latitude]"):
            la = el.get("data-lat") or el.get("data-latitude")
            lo = el.get("data-lng") or el.get("data-lon") or el.get("data-longitude")
            nm = el.get("data-name") or el.get("title") or el.get_text(strip=True)
            if la and lo:
                vid = _slug(nm or f"vehicle_{len(vehicles)+1}")
                vehicles[vid] = _vdict(
                    vid, nm or vid, float(la), float(lo), source="fs_dom")

        return vehicles

    # ── Validate (for config flow) ────────────────────────────────────────

    async def validate(self) -> bool:
        """Quick check: can reach FlareSolverr + can log in."""
        # Test FlareSolverr is reachable
        await self._fs_request({"cmd": "sessions.list"}, timeout=10)
        # Test login
        await self.login()
        return True


# ═══════════════════════════════════════════════════════════════════════════════
#  Shared parsing helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _slug(text: str) -> str:
    t = re.sub(r"[^\w\s-]", "", (text or "").lower().strip())
    return re.sub(r"[\s_-]+", "_", t).strip("_") or "unknown"


def _vdict(vid, name, lat, lng, speed=None, heading=None,
           last_update=None, source="unknown"):
    return {"id": vid, "name": str(name),
            "latitude": float(lat), "longitude": float(lng),
            "speed": speed, "heading": heading,
            "last_update": last_update, "source": source}


_LAT = ("lat", "latitude", "Latitude", "Lat")
_LNG = ("lng", "lon", "longitude", "Longitude", "Lng", "Lon")
_NM = ("name", "Name", "title", "deviceName", "VehicleName",
       "DeviceName", "vehicle_name")


def _first(d: dict, keys):
    for k in keys:
        if (v := d.get(k)) is not None:
            return v
    return None


def _merge(source: str, data, vehicles: dict) -> dict:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return vehicles

    items: list = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        if any(k in data for k in _LAT):
            items = [data]
        else:
            vals = list(data.values())
            if vals and all(isinstance(v, dict) for v in vals):
                items = vals
            else:
                items = [data]

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        lat, lng = _first(item, _LAT), _first(item, _LNG)
        if lat is None or lng is None:
            continue
        try:
            la, lo = float(lat), float(lng)
        except (ValueError, TypeError):
            continue
        if not (-90 <= la <= 90 and -180 <= lo <= 180):
            continue
        name = _first(item, _NM) or f"Vehicle {i + 1}"
        vid = _slug(str(name))
        vehicles[vid] = _vdict(
            vid, name, la, lo,
            speed=item.get("speed") or item.get("Speed"),
            heading=(item.get("heading") or item.get("course")
                     or item.get("Heading")),
            last_update=(item.get("time") or item.get("timestamp")
                         or item.get("lastUpdate") or item.get("LastUpdate")),
            source=source,
        )
    return vehicles
