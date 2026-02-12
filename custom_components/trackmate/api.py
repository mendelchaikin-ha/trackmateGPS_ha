"""TrackmateGPS client – direct HTTP login with FlareSolverr fallback."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import BASE_URL, LOGIN_URL, MAP_URL

_LOGGER = logging.getLogger(__name__)

TRACKING_URL = f"{BASE_URL}/en-US/Tracking/GetLatestPositions"


class TrackmateError(Exception):
    """Base error."""

class TrackmateConnectionError(TrackmateError):
    """Cannot reach service."""

class TrackmateAuthError(TrackmateError):
    """Login failed."""


def _parse_html(html: str):
    from bs4 import BeautifulSoup  # noqa: E402
    return BeautifulSoup(html, "html.parser")


class TrackmateClient:
    def __init__(self, fs_url: str, username: str,
                 password: str) -> None:
        self._fs_url = fs_url
        self._username = username
        self._password = password
        self._cookies: dict[str, str] = {}
        self._user_agent: str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36")
        self._logged_in: bool = False
        self._http: aiohttp.ClientSession | None = None
        self._use_flaresolverr: bool = False

    async def _ensure_http(self) -> aiohttp.ClientSession:
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession()
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.closed:
            await self._http.close()

    # ── Direct HTTP login (fast, no FlareSolverr) ─────────────────────────

    async def _direct_login(self) -> bool:
        """Try logging in with plain aiohttp. Fast path."""
        _LOGGER.info("Trying direct login for %s***",
                     self._username[:3])
        session = await self._ensure_http()
        headers = {"User-Agent": self._user_agent}

        try:
            # 1) GET login page
            async with session.get(
                LOGIN_URL, headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=True,
            ) as resp:
                _LOGGER.debug("Direct GET login -> %s", resp.status)
                if resp.status == 403:
                    _LOGGER.info(
                        "Cloudflare blocked direct access, "
                        "will use FlareSolverr")
                    return False
                if resp.status != 200:
                    _LOGGER.debug(
                        "Login page status %s", resp.status)
                    return False
                html = await resp.text()

                # Check for Cloudflare challenge
                if ("cf-browser-verification" in html
                        or "challenge-platform" in html
                        or "Just a moment" in html):
                    _LOGGER.info(
                        "Cloudflare challenge detected, "
                        "will use FlareSolverr")
                    return False

                # Grab cookies from response
                get_cookies = {
                    k: v.value
                    for k, v in resp.cookies.items()
                }

            # 2) Parse form
            soup = _parse_html(html)
            token_el = soup.select_one(
                "input[name='__RequestVerificationToken']")
            token = token_el["value"] if token_el else ""

            uname_field = "Username"
            pwd_field = "Password"
            form = soup.select_one(
                "form[action*='Login'], form#loginForm, "
                "form[method='post']")
            if form:
                for inp in form.select(
                    "input[type='text'], input[type='email']"
                ):
                    if n := inp.get("name"):
                        uname_field = n
                        break
                for inp in form.select("input[type='password']"):
                    if n := inp.get("name"):
                        pwd_field = n
                        break

            _LOGGER.debug("Form: %s / %s, token=%s",
                          uname_field, pwd_field,
                          "yes" if token else "no")

            # 3) POST login
            post_data: dict[str, str] = {
                uname_field: self._username,
                pwd_field: self._password,
            }
            if token:
                post_data["__RequestVerificationToken"] = token

            async with session.post(
                LOGIN_URL,
                data=post_data,
                headers={
                    "User-Agent": self._user_agent,
                    "Referer": LOGIN_URL,
                },
                cookies=get_cookies,
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=True,
            ) as resp2:
                final_url = str(resp2.url).lower()
                _LOGGER.debug("Post-login URL: %s (status %s)",
                              final_url, resp2.status)

                # Collect all cookies
                all_cookies = dict(get_cookies)
                for k, v in resp2.cookies.items():
                    all_cookies[k] = v.value
                # Also get from cookie jar
                for cookie in session.cookie_jar:
                    all_cookies[cookie.key] = cookie.value

                if "account/login" in final_url:
                    html2 = await resp2.text()
                    if ("cf-browser-verification" in html2
                            or "challenge-platform" in html2):
                        _LOGGER.info(
                            "Cloudflare on POST, "
                            "will use FlareSolverr")
                        return False
                    _LOGGER.debug("Still on login page")
                    return False

                self._cookies = all_cookies
                self._logged_in = True
                self._use_flaresolverr = False
                _LOGGER.info(
                    "Direct login OK - %d cookies",
                    len(self._cookies))
                return True

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.debug("Direct login failed: %s", e)
            return False

    # ── FlareSolverr login (slow fallback) ────────────────────────────────

    async def _fs_request(self, body: dict,
                          timeout: int = 120) -> dict:
        session = await self._ensure_http()
        try:
            async with session.post(
                self._fs_url, json=body,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise TrackmateConnectionError(
                        f"FlareSolverr {resp.status}: {text[:300]}")
                return await resp.json()
        except TrackmateConnectionError:
            raise
        except aiohttp.ClientConnectorError as e:
            raise TrackmateConnectionError(
                f"Cannot reach FlareSolverr at "
                f"{self._fs_url}") from e
        except aiohttp.ClientError as e:
            raise TrackmateConnectionError(str(e)) from e
        except (TimeoutError, asyncio.CancelledError) as e:
            raise TrackmateConnectionError(
                f"Timeout connecting to FlareSolverr") from e
        except Exception as e:
            _LOGGER.exception("FlareSolverr error")
            raise TrackmateConnectionError(str(e)) from e

    async def _flaresolverr_login(self) -> bool:
        _LOGGER.info("FlareSolverr login for %s***",
                     self._username[:3])

        # GET login page
        resp = await self._fs_request({
            "cmd": "request.get",
            "url": LOGIN_URL,
            "maxTimeout": 60000,
        })
        if resp.get("status") != "ok":
            raise TrackmateConnectionError(
                resp.get("message", "FS GET failed"))

        sol = resp["solution"]
        html = sol.get("response", "")
        self._user_agent = sol.get("userAgent", self._user_agent)
        get_cookies = sol.get("cookies", [])

        soup = _parse_html(html)
        token_el = soup.select_one(
            "input[name='__RequestVerificationToken']")
        token = token_el["value"] if token_el else ""

        uname_field = "Username"
        pwd_field = "Password"
        form = soup.select_one(
            "form[action*='Login'], form#loginForm, "
            "form[method='post']")
        if form:
            for inp in form.select(
                "input[type='text'], input[type='email']"
            ):
                if n := inp.get("name"):
                    uname_field = n
                    break
            for inp in form.select("input[type='password']"):
                if n := inp.get("name"):
                    pwd_field = n
                    break

        # POST login
        parts = []
        if token:
            parts.append(
                f"__RequestVerificationToken={quote(token)}")
        parts.append(
            f"{quote(uname_field)}={quote(self._username)}")
        parts.append(
            f"{quote(pwd_field)}={quote(self._password)}")

        resp2 = await self._fs_request({
            "cmd": "request.post",
            "url": LOGIN_URL,
            "postData": "&".join(parts),
            "cookies": get_cookies,
            "maxTimeout": 60000,
        })
        if resp2.get("status") != "ok":
            raise TrackmateAuthError(
                resp2.get("message", "FS POST failed"))

        sol2 = resp2["solution"]
        final_url = sol2.get("url", "").lower()

        if "account/login" in final_url:
            raise TrackmateAuthError("Invalid credentials")

        self._cookies = {
            c["name"]: c["value"]
            for c in sol2.get("cookies", [])
        }
        self._logged_in = True
        self._use_flaresolverr = True
        _LOGGER.info("FlareSolverr login OK - %d cookies",
                     len(self._cookies))
        return True

    # ── Login (tries direct first) ────────────────────────────────────────

    async def login(self) -> bool:
        _LOGGER.info("Logging into TrackmateGPS for %s***",
                     self._username[:3])
        try:
            if await self._direct_login():
                return True
            _LOGGER.info("Direct login failed, trying FlareSolverr")
            return await self._flaresolverr_login()
        except (TrackmateConnectionError, TrackmateAuthError):
            self._logged_in = False
            raise
        except Exception as e:
            self._logged_in = False
            raise TrackmateError(f"Login error: {e}") from e

    @property
    def logged_in(self) -> bool:
        return self._logged_in

    # ── Fetch vehicles ────────────────────────────────────────────────────

    async def get_vehicles(self) -> dict[str, dict[str, Any]]:
        if not self._logged_in:
            await self.login()

        vehicles = await self._fetch_tracking_api()

        if not vehicles:
            _LOGGER.warning("No vehicles found for %s***",
                            self._username[:3])
        return vehicles

    async def _fetch_tracking_api(
        self, _retried: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """Load tracking page, negotiate SignalR, then call API."""
        session = await self._ensure_http()
        headers = {"User-Agent": self._user_agent}

        # Step 1: Visit the tracking page (inits server session)
        tracking_page_url = f"{BASE_URL}/en/Tracking"
        try:
            async with session.get(
                tracking_page_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=True,
            ) as resp:
                page_html = await resp.text()
                final_url = str(resp.url).lower()
                _LOGGER.debug(
                    "Tracking page -> %s (%d chars)",
                    resp.status, len(page_html))

                if "login" in final_url:
                    if _retried:
                        _LOGGER.warning(
                            "Session lost after re-login")
                        return {}
                    _LOGGER.info("Session expired")
                    self._logged_in = False
                    await self.login()
                    return await self._fetch_tracking_api(
                        _retried=True)

        except aiohttp.ClientError as e:
            _LOGGER.debug("Tracking page error: %s", e)
            return {}

        # Step 2: Negotiate SignalR connection
        import urllib.parse as _up
        connection_data = json.dumps([
            {"name": "trackingupdates"},
            {"name": "alertshub"},
            {"name": "taskrouteshub"},
        ])
        negotiate_url = (
            f"{BASE_URL}/signalr/negotiate?"
            f"clientProtocol=2.1&"
            f"connectionData="
            f"{_up.quote(connection_data)}")

        signalr_token = None
        try:
            async with session.get(
                negotiate_url,
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "text/plain, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": tracking_page_url,
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                ct = resp.headers.get("Content-Type", "")
                _LOGGER.debug(
                    "SignalR negotiate -> %s (ct=%s)",
                    resp.status, ct)

                if resp.status == 200 and "json" in ct:
                    neg_data = await resp.json()
                    signalr_token = neg_data.get(
                        "ConnectionToken", "")
                    _LOGGER.debug(
                        "SignalR token: %s",
                        "yes" if signalr_token else "no")
                else:
                    text = await resp.text()
                    _LOGGER.debug(
                        "SignalR negotiate fail: %.200s",
                        text)

        except aiohttp.ClientError as e:
            _LOGGER.debug("SignalR negotiate error: %s", e)

        # Step 3: Connect with longPolling transport
        # This returns the initial batch of ALL current
        # vehicle positions (even parked ones), unlike SSE
        # which just says "initialized".
        vehicles: dict[str, dict[str, Any]] = {}
        all_points: list[dict] = []
        msg_id = None

        if signalr_token:
            lp_base = {
                "transport": "longPolling",
                "clientProtocol": "2.1",
                "connectionToken": signalr_token,
                "connectionData": connection_data,
            }
            lp_headers = {
                "User-Agent": self._user_agent,
                "Accept": "application/json, "
                          "text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": tracking_page_url,
            }

            connect_url = (
                f"{BASE_URL}/signalr/connect?"
                + "&".join(f"{k}={_up.quote(str(v))}"
                           for k, v in lp_base.items()))

            try:
                async with session.get(
                    connect_url,
                    headers=lp_headers,
                    timeout=aiohttp.ClientTimeout(
                        total=30, sock_read=25),
                ) as resp:
                    text = await resp.text()
                    _LOGGER.debug(
                        "LP connect -> %s (%d chars)",
                        resp.status, len(text))

                    if resp.status == 200 and text.strip():
                        try:
                            msg = json.loads(text)
                            msg_id = msg.get("C")
                            new_pts = _extract_signalr_points(
                                msg)
                            if new_pts:
                                _LOGGER.debug(
                                    "  Connect: %d points",
                                    len(new_pts))
                                all_points.extend(new_pts)
                            elif msg.get("M"):
                                _LOGGER.debug(
                                    "  Connect msgs: %d "
                                    "(no points)",
                                    len(msg["M"]))
                            else:
                                _LOGGER.debug(
                                    "  Connect: init "
                                    "(no msgs yet)")
                        except json.JSONDecodeError as e:
                            _LOGGER.debug(
                                "  Connect JSON err: %s",
                                e)

            except asyncio.TimeoutError:
                _LOGGER.debug("LP connect timeout")
            except aiohttp.ClientError as e:
                _LOGGER.debug("LP connect error: %s", e)

        # Step 4: Start the connection
        if signalr_token:
            start_url = (
                f"{BASE_URL}/signalr/start?"
                + "&".join(f"{k}={_up.quote(str(v))}"
                           for k, v in lp_base.items()))

            try:
                async with session.get(
                    start_url,
                    headers=lp_headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    text = await resp.text()
                    _LOGGER.debug(
                        "LP start -> %s: %s",
                        resp.status, text[:200])
            except (aiohttp.ClientError,
                    asyncio.TimeoutError) as e:
                _LOGGER.debug("LP start error: %s", e)

        # Step 5: Poll for updates (the server sends
        # position batches here). If connect already
        # gave us data, 1 poll is enough. Otherwise
        # try up to 2 polls with longer timeout.
        if signalr_token:
            max_polls = 1 if all_points else 2
            for poll_attempt in range(max_polls):
                poll_params = dict(lp_base)
                if msg_id:
                    poll_params["messageId"] = msg_id
                poll_url = (
                    f"{BASE_URL}/signalr/poll?"
                    + "&".join(
                        f"{k}={_up.quote(str(v))}"
                        for k, v in poll_params.items()))

                try:
                    async with session.get(
                        poll_url,
                        headers=lp_headers,
                        timeout=aiohttp.ClientTimeout(
                            total=30, sock_read=25),
                    ) as resp:
                        text = await resp.text()
                        _LOGGER.debug(
                            "LP poll #%d -> %s (%d chars)",
                            poll_attempt, resp.status,
                            len(text))

                        if resp.status != 200:
                            continue
                        if not text.strip():
                            continue

                        msg = json.loads(text)
                        # Track message ID for next poll
                        if msg.get("C"):
                            msg_id = msg["C"]
                        new_pts = _extract_signalr_points(
                            msg)
                        if new_pts:
                            _LOGGER.debug(
                                "  Poll #%d: %d points",
                                poll_attempt, len(new_pts))
                            all_points.extend(new_pts)

                except asyncio.TimeoutError:
                    _LOGGER.debug(
                        "LP poll #%d timeout",
                        poll_attempt)
                except (aiohttp.ClientError,
                        json.JSONDecodeError) as e:
                    _LOGGER.debug(
                        "LP poll #%d error: %s",
                        poll_attempt, e)
                    break

        # Deduplicate points: keep the latest per asset
        if all_points:
            latest: dict[int, dict] = {}
            for pt in all_points:
                aid = pt.get("IdAsset", 0)
                latest[aid] = pt  # last wins
            deduped = list(latest.values())
            _LOGGER.debug(
                "Collected %d total points, %d unique",
                len(all_points), len(deduped))
            vehicles = _parse_motus(
                {"Points": deduped})
            if vehicles:
                _LOGGER.info(
                    "Got %d vehicles via SignalR",
                    len(vehicles))
                return vehicles

        _LOGGER.debug("Falling back to page scrape")

        # Fallback: extract allUserVehicles from page HTML
        import re as _re
        var_pattern = (
            r'var\s+allUserVehicles\s*=\s*'
            r'"(\[.+?\])"\s*;')
        m = _re.search(var_pattern, page_html, _re.DOTALL)
        if m:
            try:
                raw = m.group(1).replace('\\"', '"')
                asset_list = json.loads(raw)
                _LOGGER.info(
                    "Extracted %d vehicles from page JS",
                    len(asset_list))
                for asset in asset_list:
                    aid = asset.get("Id", 0)
                    aname = asset.get("AssetName", "")
                    vid = _slug(str(aid))
                    vehicles[vid] = {
                        "id": vid,
                        "asset_id": aid,
                        "name": aname,
                        "latitude": 0.0,
                        "longitude": 0.0,
                        "speed": None,
                        "heading": None,
                        "last_update": None,
                        "source": "page_scrape",
                    }
            except (json.JSONDecodeError, Exception) as e:
                _LOGGER.debug("Page scrape failed: %s", e)

        return vehicles

    # ── Validate (config flow) ────────────────────────────────────────────

    async def validate(self) -> bool:
        """Check FlareSolverr is reachable."""
        result = await self._fs_request(
            {"cmd": "sessions.list"}, timeout=10)
        if result.get("status") != "ok":
            raise TrackmateConnectionError(
                "FlareSolverr not responding")
        return True


# ══════════════════════════════════════════════════════════════════════════

def _extract_signalr_points(msg: dict) -> list[dict]:
    """Extract vehicle Points from a SignalR longPoll message.

    The server sends:
      {M: [{H: "trackingUpdates",
            M: "updateBatchPositions",
            A: [[{Points: [pt1, pt2, ...]}, ...]]}]}

    A[0] is a list of batch objects, each with a Points array.
    We flatten all Points into a single list.
    """
    points: list[dict] = []
    for m in msg.get("M", []):
        method = m.get("M", "")
        if "position" not in method.lower() and \
           "batch" not in method.lower() and \
           "send" not in method.lower():
            continue
        for arg in m.get("A", []):
            if isinstance(arg, list):
                # arg = [{Points: [...]}, ...]
                for batch in arg:
                    if isinstance(batch, dict):
                        pts = batch.get("Points", [])
                        if isinstance(pts, list):
                            points.extend(pts)
            elif isinstance(arg, dict):
                pts = arg.get("Points", [])
                if isinstance(pts, list):
                    points.extend(pts)
    return points


def _slug(text: str) -> str:
    t = re.sub(r"[^\w\s-]", "", (text or "").lower().strip())
    return re.sub(r"[\s_-]+", "_", t).strip("_") or "unknown"


def _parse_motus(data: dict) -> dict[str, dict[str, Any]]:
    """Parse MotusObject.Points into vehicle dict."""
    vehicles: dict[str, dict[str, Any]] = {}

    motus = data.get("MotusObject") or data
    points = motus.get("Points", [])

    if not points and isinstance(data, list):
        points = data

    if not points:
        _LOGGER.debug("No Points found. Keys: %s",
                       list(data.keys())[:15])
        return vehicles

    _LOGGER.info("Parsing %d vehicle points", len(points))

    for pt in points:
        if not isinstance(pt, dict):
            continue

        lat = pt.get("Latitude")
        lng = pt.get("Longitude")
        if lat is None or lng is None:
            continue
        try:
            la, lo = float(lat), float(lng)
        except (ValueError, TypeError):
            continue
        if not (-90 <= la <= 90 and -180 <= lo <= 180):
            continue

        asset_id = pt.get("IdAsset", 0)
        name = (pt.get("VehicleDescription")
                or pt.get("Id")
                or f"Vehicle {asset_id}")
        vid = _slug(str(asset_id) or str(name))

        vehicles[vid] = {
            "id": vid,
            "asset_id": asset_id,
            "name": str(name),
            "latitude": la,
            "longitude": lo,
            "speed": pt.get("Speed"),
            "heading": pt.get("Direction"),
            "last_update": (pt.get("DateTimeRecord")
                            or pt.get("DeviceDateTime")),
            "imei": pt.get("Imei"),
            "main_power": pt.get("MainPower"),
            "odometer": pt.get("OdoMeter"),
            "satellites": pt.get("SatelittesCount"),
            "status_id": pt.get("StatusId"),
            "icon": pt.get("IconImage"),
            "info_html": pt.get("InfoHTML"),
            "idle_start": pt.get("IdleStart") or None,
            "stop_time": pt.get("StopTime") or None,
            "recent_movement": pt.get("RecentMovement"),
            "battery_level": pt.get("BatteryLevelPercent"),
            "battery_charging": pt.get("BatteryCharging"),
            "altitude": pt.get("Altitude"),
            "css_class": pt.get("CssClasses"),
            "source": "signalr",
        }

        _LOGGER.debug("  Vehicle: %s at %.5f,%.5f spd=%s",
                       name, la, lo, pt.get("Speed"))

    return vehicles

                try:
                    async with session.get(
                        poll_url,
                        headers=lp_headers,
                        timeout=aiohttp.ClientTimeout(
                            total=30, sock_read=25),
                    ) as resp:
                        text = await resp.text()
                        _LOGGER.debug(
                            "LP poll #%d -> %s (%d chars)",
                            poll_attempt, resp.status,
                            len(text))

                        if resp.status != 200:
                            continue
                        if not text.strip():
                            continue

                        msg = json.loads(text)
                        # Track message ID for next poll
                        if msg.get("C"):
                            msg_id = msg["C"]
                        new_pts = _extract_signalr_points(
                            msg)
                        if new_pts:
                            _LOGGER.debug(
                                "  Poll #%d: %d points",
                                poll_attempt, len(ne