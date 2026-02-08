# TrackmateGPS for Home Assistant

Track your [TrackmateGPS](https://trackmategps.com) vehicles in Home Assistant. Supports **multiple accounts**.

## How it works

```
┌─────────────────┐     ┌────────────────────────────┐
│  FlareSolverr   │◄────│  Trackmate GPS Integration │
│  (alexbelgium)  │     │  (this repo)               │
│  Handles CF +   │     │  Login → scrape → entities  │
│  browser engine │     │                            │
└─────────────────┘     └────────────────────────────┘
```

TrackmateGPS is protected by Cloudflare. This integration uses [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) (available as an addon from [alexbelgium's repo](https://github.com/alexbelgium/hassio-addons)) to bypass Cloudflare, log in, and then scrapes vehicle positions with standard HTTP using the authenticated session cookies.

## Prerequisites

**FlareSolverr** must be installed and running before setting up this integration.

1. Go to **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
2. Add: `https://github.com/alexbelgium/hassio-addons`
3. Find and install **FlareSolverr**
4. Start FlareSolverr (default: port 8191)

## Installation

1. Add this repo to [HACS](https://hacs.xyz) as a custom repository (type: **Integration**)
2. Install **Trackmate GPS** from HACS
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration → Trackmate GPS**
5. Enter:
   - **FlareSolverr URL**: `http://localhost:8191/v1` (default)
   - **Username**: Your TrackmateGPS email/username
   - **Password**: Your TrackmateGPS password
6. Your vehicles appear as `device_tracker` entities on the map

### Multiple accounts

Just add the integration again for each account. Each gets its own config entry and set of `device_tracker` entities.

## Options

After setup, click **Configure** on the integration to adjust:

| Option | Default | Description |
|--------|---------|-------------|
| Update interval | 30s | How often to poll vehicle positions |
| Session refresh | 30min | How often to re-login to keep session alive |
| Vehicle filter | All | Optionally track only specific vehicles |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Cannot reach FlareSolverr" | Make sure FlareSolverr addon is running. Check the URL. |
| "Invalid credentials" | Verify you can log in at trackmategps.com manually. |
| No vehicles after setup | This is the trickiest part — the integration tries multiple scraping strategies (API probing, HTML parsing, JS rendering). Enable debug logging (`custom_components.trackmate`) and check what's happening. |
| Vehicles disappear | Session may have expired. The integration auto-re-logins, but check logs. |

### Debug logging

Add to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.trackmate: debug
```

## Technical details

1. Creates a FlareSolverr session per account
2. `request.get` loads the login page (FlareSolverr solves Cloudflare challenge)
3. Parses ASP.NET anti-forgery token from the HTML
4. `request.post` submits the login form with credentials
5. Extracts session cookies from FlareSolverr response
6. Uses plain `aiohttp` with those cookies to:
   - Probe TrackmateGPS API endpoints (e.g., `/en/Map/GetVehicles`)
   - Parse the map page HTML for embedded vehicle data
   - Fall back to FlareSolverr rendering for JS-only data
7. Creates `device_tracker` entities with GPS coordinates
