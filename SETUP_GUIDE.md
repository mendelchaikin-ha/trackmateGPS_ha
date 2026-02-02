# Setup & Configuration Guide

## Quick Start

### 1. Installation

#### Via HACS (Recommended)
1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots menu → "Custom repositories"
4. Add repository URL: `https://github.com/example/trackmate_ha`
5. Category: "Integration"
6. Click "Add"
7. Find "Trackmate GPS" and click "Install"
8. Restart Home Assistant

#### Manual Installation
1. Download the latest release from GitHub
2. Extract to `config/custom_components/trackmate`
3. Restart Home Assistant

### 2. Initial Configuration

1. Navigate to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Trackmate GPS"
4. Enter your credentials:
   - **Account Name**: A friendly name (e.g., "School Buses")
   - **Email**: Your Trackmate GPS account email
   - **Password**: Your Trackmate GPS password
5. Click **Submit**

The integration will:
- Validate your credentials
- Fetch available vehicles
- Create device tracker entities
- Begin polling for updates

### 3. Configure Options

Click **Configure** on the integration to access options:

#### Vehicle Selection
- **Purpose**: Choose which vehicles to track
- **Default**: All vehicles in your account
- **How to**: Check the vehicles you want to track
- **Tip**: Reduce tracked vehicles to lower API usage

#### Scan Interval
- **Purpose**: How often to update positions
- **Range**: 10-300 seconds
- **Default**: 30 seconds
- **Recommendations**:
  - Real-time tracking: 15-30 seconds
  - Normal use: 30-60 seconds
  - Battery/bandwidth saving: 60-300 seconds

## Advanced Configuration

### Rate Limiting

The integration enforces a 60 requests/hour limit to prevent API bans.

**Calculate your rate**:
- Scan interval 30s = 120 requests/hour ⚠️ (too high)
- Scan interval 60s = 60 requests/hour ✅ (at limit)
- Scan interval 90s = 40 requests/hour ✅ (safe)

**Best practice**: Use 60+ seconds for most scenarios.

### Debug Logging

Enable debug logs in `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.trackmate: debug
    custom_components.trackmate.api: debug
    custom_components.trackmate.coordinator: debug
```

**View logs**:
1. Settings → System → Logs
2. Filter by "trackmate"

**What you'll see**:
- API calls and responses
- Cookie management
- Rate limiter activity
- Authentication flows
- Error details

### Cookie Management

Cookies are automatically managed but you can:

**Check cookie status**:
1. Download diagnostics (see below)
2. Look for `cookies_cached` and `cookie_expiry`

**Force re-authentication**:
1. Settings → Devices & Services
2. Find Trackmate GPS
3. Click "Reauthenticate"
4. Enter credentials

**Storage location**: `.storage/trackmate_cookies`

### Diagnostics

**Download diagnostics**:
1. Settings → Devices & Services
2. Click three dots on Trackmate GPS
3. Select "Download Diagnostics"

**Contains**:
- Session status
- Rate limiter stats
- Vehicle information
- Configuration details
- Update history

**Privacy**: Email is redacted, no passwords included.

## Entity Management

### Device Tracker Entities

Each vehicle creates an entity:
- **Entity ID**: `device_tracker.trackmate_{vehicle_name}`
- **State**: `home`, `not_home`, or specific zone
- **Attributes**:
  - `latitude`: Current position
  - `longitude`: Current position
  - `speed`: Speed in km/h (if available)
  - `heading`: Direction in degrees (if available)
  - `source_type`: Always "gps"

### Customizing Entities

**Rename entity**:
1. Developer Tools → States
2. Find your entity
3. Click the entity
4. Change "Entity ID" or "Friendly Name"

**Customize icon**:
```yaml
homeassistant:
  customize:
    device_tracker.trackmate_bus_101:
      icon: mdi:bus-school
```

**Set home zone**:
The `home` zone is used to determine `home`/`not_home` state. Configure in Settings → Areas.

## Automation Examples

### Notify when bus arrives

```yaml
automation:
  - alias: "Bus Arriving Home"
    trigger:
      - platform: state
        entity_id: device_tracker.trackmate_bus_101
        to: "home"
    action:
      - service: notify.mobile_app
        data:
          message: "School bus has arrived!"
```

### Track bus on map

```yaml
# Lovelace card
type: map
entities:
  - device_tracker.trackmate_bus_101
  - device_tracker.trackmate_bus_102
```

### Monitor speed

```yaml
automation:
  - alias: "Bus Speeding Alert"
    trigger:
      - platform: numeric_state
        entity_id: device_tracker.trackmate_bus_101
        attribute: speed
        above: 80
    action:
      - service: notify.admin
        data:
          message: "Bus 101 is speeding: {{ state_attr('device_tracker.trackmate_bus_101', 'speed') }} km/h"
```

## Troubleshooting

### Authentication Issues

**Symptom**: "Invalid username or password" error

**Solutions**:
1. Verify credentials on trackmategps.com
2. Check for typos in email/password
3. Ensure account is active
4. Try reauth flow (see above)

### No Vehicles Showing

**Symptom**: Integration setup succeeds but no entities created

**Check**:
1. Log in to trackmategps.com - do vehicles appear there?
2. Check integration options - are vehicles selected?
3. Download diagnostics - check vehicle count
4. Review logs for API errors

**Solutions**:
1. Reconfigure integration
2. Select "all vehicles" in options
3. Restart Home Assistant

### Rate Limit Errors

**Symptom**: Updates stop or slow down, logs show rate limit messages

**Solutions**:
1. Increase scan interval to 90-120 seconds
2. Download diagnostics to check rate limiter stats
3. Wait 1 hour for limit to reset
4. Reduce number of tracked vehicles

### Session Expiring

**Symptom**: Frequent reauth requests

**Check diagnostics**:
- Cookie expiry time should be ~12 hours ahead
- `cookies_cached` should be true

**Solutions**:
1. Check system time is correct
2. Verify storage permissions
3. Check `.storage` directory exists and is writable
4. Review logs for cookie save/load errors

### Connection Errors

**Symptom**: "Cannot connect" errors

**Check**:
1. Internet connectivity
2. trackmategps.com is accessible
3. No firewall blocking HTTPS
4. Home Assistant can reach internet

**Solutions**:
1. Test from Home Assistant host: `curl https://trackmategps.com`
2. Check proxy settings if using one
3. Review network logs
4. Try manual API call for testing

## Maintenance

### Regular Tasks

**Weekly**:
- Check diagnostics for any issues
- Review rate limiter stats

**Monthly**:
- Update to latest version
- Review and clean up unused entities
- Check log file size

**As Needed**:
- Update credentials if changed
- Adjust scan interval based on needs
- Add/remove vehicles

### Updating

**Via HACS**:
1. HACS → Integrations
2. Find "Trackmate GPS"
3. Click "Update"
4. Restart Home Assistant

**Manual**:
1. Download latest release
2. Replace files in `custom_components/trackmate`
3. Restart Home Assistant

### Uninstalling

1. Remove integration from UI
2. Restart Home Assistant
3. Delete `custom_components/trackmate` (if manual install)
4. Delete `.storage/trackmate_cookies` (optional)

## Getting Help

**Before asking for help**:
1. Download diagnostics
2. Enable debug logging
3. Check logs for errors
4. Review this guide

**Where to get help**:
- GitHub Issues (bugs/features)
- GitHub Discussions (questions)
- Home Assistant Community Forum

**Include when reporting issues**:
- Home Assistant version
- Integration version
- Diagnostics file (redact if needed)
- Relevant log entries
- Steps to reproduce
