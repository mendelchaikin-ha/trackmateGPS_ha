"""Constants for the Trackmate GPS integration."""

DOMAIN = "trackmate"

# Configuration
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_LABEL = "label"
CONF_BUSES = "buses"
CONF_SCAN_INTERVAL = "scan_interval"

# Data storage keys
DATA_COORDINATOR = "coordinator"
DATA_API = "api"
DATA_STORE = "store"

# Defaults
DEFAULT_SCAN_INTERVAL = 30  # seconds
MIN_SCAN_INTERVAL = 10  # seconds - rate limiting
MAX_SCAN_INTERVAL = 300  # seconds

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_cookies"

# Rate limiting
RATE_LIMIT_REQUESTS = 60  # max requests per hour
RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds

# Cookie persistence
COOKIE_EXPIRY_HOURS = 12
COOKIE_REFRESH_BEFORE_EXPIRY = 300  # 5 minutes in seconds
