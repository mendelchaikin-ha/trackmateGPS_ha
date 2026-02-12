"""Constants for the Trackmate GPS integration."""

DOMAIN = "trackmate"

CONF_FLARESOLVERR_URL = "flaresolverr_url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_VEHICLE_IDS = "vehicle_ids"
CONF_SESSION_REFRESH = "session_refresh_minutes"

DEFAULT_FS_URL = "http://localhost:8191/v1"
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_SESSION_REFRESH = 30

BASE_URL = "https://trackmategps.com"
LOGIN_URL = f"{BASE_URL}/en/Account/Login"
MAP_URL = f"{BASE_URL}/en/Map"
