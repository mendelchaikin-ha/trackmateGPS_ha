# Trackmate GPS Integration for Home Assistant

[![CI](https://github.com/example/trackmate_ha/workflows/CI/badge.svg)](https://github.com/example/trackmate_ha/actions)
[![codecov](https://codecov.io/gh/example/trackmate_ha/branch/main/graph/badge.svg)](https://codecov.io/gh/example/trackmate_ha)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)

Enterprise-grade Home Assistant integration for Trackmate GPS vehicle tracking.

## Version 1.1.1 - Enterprise Features

### 🚀 What's New in v1.1

- **Cookie Persistence**: Sessions persist across Home Assistant restarts
- **Automatic Reauth**: Smart reauth flow when credentials expire
- **Configurable Polling**: Adjust update frequency via UI slider (10-300 seconds)
- **Rate Limiting**: Built-in protection against API bans
- **Diagnostics Panel**: Detailed system health information
- **Logger Debug Mode**: Enhanced debugging capabilities
- **GitHub Actions CI**: Automated testing and validation
- **Comprehensive Tests**: Full pytest suite with HA test harness

## Features

### Core Functionality
- Real-time GPS tracking of Trackmate vehicles
- Device tracker entities for each vehicle
- Latitude/longitude position tracking
- Speed and heading information (when available)
- Automatic session management

### Enterprise Capabilities
- **Persistent Sessions**: Cookies stored securely, survive restarts
- **Smart Authentication**: Automatic reauth flow via HA UI
- **Rate Limiting**: 60 requests/hour limit with automatic throttling
- **Configurable Polling**: 10-300 second intervals, default 30s
- **Error Handling**: Comprehensive error recovery and logging
- **Diagnostics**: Built-in system health monitoring

## Installation

### HACS (Recommended)

1. Add this repository to HACS as a custom repository
2. Search for "Trackmate GPS" in HACS
3. Click Install
4. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/trackmate` directory to your Home Assistant `custom_components` folder
2. Restart Home Assistant

## Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Trackmate GPS"
4. Enter your credentials:
   - **Account Name**: Friendly name for this account
   - **Email**: Your Trackmate GPS email
   - **Password**: Your Trackmate GPS password

### Options

After setup, click **Configure** on the integration to access:

#### Vehicle Selection
- Select specific vehicles to track
- Leave empty to track all vehicles
- Updated dynamically from your account

#### Scan Interval
- **Range**: 10-300 seconds
- **Default**: 30 seconds
- **Recommended**: 30-60 seconds for normal use
- **Note**: Lower intervals may trigger rate limiting

## Rate Limiting

The integration includes built-in rate limiting to prevent API bans:

- **Limit**: 60 requests per hour
- **Behavior**: Automatic throttling when limit approached
- **Status**: Check Diagnostics panel for current usage

### Recommended Settings
- **Normal use**: 30-60 second interval
- **High-frequency tracking**: 15-30 seconds (monitor rate limit)
- **Battery saving**: 60-300 seconds

## Reauth Flow

If your session expires or credentials change:

1. You'll receive a notification in Home Assistant
2. Click the notification or go to the integration
3. Click **Reauthenticate**
4. Enter your credentials
5. Integration resumes automatically

## Diagnostics

Access detailed diagnostics via:
1. Go to **Settings** → **Devices & Services**
2. Find your Trackmate GPS integration
3. Click the three dots menu
4. Select **Download Diagnostics**

### Diagnostics Include
- Cookie/session status
- Rate limiter statistics
- Vehicle count and information
- Update success status
- Configuration details

## Debug Logging

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.trackmate: debug
```

Then check logs in **Settings** → **System** → **Logs**

## Device Tracker Entities

Each tracked vehicle creates a device tracker entity:

- **Entity ID**: `device_tracker.trackmate_{vehicle_name}`
- **Attributes**:
  - `latitude`: Current latitude
  - `longitude`: Current longitude
  - `speed`: Speed (if available)
  - `heading`: Heading/direction (if available)
  - `source_type`: Always "gps"

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/example/trackmate_ha.git
cd trackmate_ha

# Install development dependencies
pip install -r requirements_dev.txt
pip install -r requirements_test.txt

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=custom_components/trackmate

# Run specific test file
pytest tests/test_api.py -v

# Run with Home Assistant test harness
pytest tests/ --homeassistant-version=latest
```

### Code Quality

```bash
# Format code
black custom_components/trackmate

# Sort imports
isort custom_components/trackmate

# Lint
flake8 custom_components/trackmate

# Type check
mypy custom_components/trackmate

# Run all pre-commit hooks
pre-commit run --all-files
```

### GitHub Actions

All PRs and commits are automatically tested:
- ✅ Code formatting (black, isort)
- ✅ Linting (flake8)
- ✅ Type checking (mypy)
- ✅ Unit tests (pytest)
- ✅ Home Assistant validation (hassfest)
- ✅ HACS validation
- ✅ Integration tests

## Troubleshooting

### Session Expired Repeatedly
- Check credentials are correct
- Verify Trackmate website is accessible
- Check rate limiting hasn't been triggered
- Review diagnostics for cookie expiry time

### Rate Limited
- Increase scan interval to 60+ seconds
- Check diagnostics for rate limiter status
- Wait 1 hour for rate limit to reset

### No Vehicles Showing
- Verify vehicles exist in your Trackmate account
- Check integration options → vehicle selection
- Review logs for API errors
- Download diagnostics to verify data structure

### Connection Errors
- Verify internet connectivity
- Check Trackmate website status
- Review firewall/proxy settings
- Check Home Assistant logs for detailed errors

## Support

- **Issues**: [GitHub Issues](https://github.com/example/trackmate_ha/issues)
- **Discussions**: [GitHub Discussions](https://github.com/example/trackmate_ha/discussions)
- **Home Assistant Community**: [Community Thread](https://community.home-assistant.io/)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add/update tests
5. Ensure all tests pass
6. Submit a pull request

## License

MIT License - see LICENSE file for details

## Credits

Developed for the Home Assistant community.

## Changelog

### v1.1.0 (2026-02-01)
- ✨ Cookie persistence across restarts
- ✨ Automatic reauth flow via HA UI
- ✨ Configurable polling slider (10-300s)
- ✨ Built-in rate limiting (60 req/hour)
- ✨ Diagnostics panel
- ✨ Enhanced debug logging
- ✨ GitHub Actions CI/CD
- ✨ Comprehensive pytest suite
- ✨ Home Assistant test harness
- 🐛 Fixed session expiry handling
- 🐛 Improved error recovery
- 📝 Complete documentation

### v1.0.0
- Initial release
- Basic GPS tracking
- Vehicle selection
- Config flow
