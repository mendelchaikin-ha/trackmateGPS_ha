# Changelog

All notable changes to the Trackmate GPS Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-02-01

### Added
- **Cookie Persistence**: Session cookies now persist across Home Assistant restarts using secure storage
- **Reauth Flow**: Automatic reauth prompts when credentials expire or fail, with user-friendly UI
- **Configurable Polling**: New slider in options to adjust scan interval from 10-300 seconds
- **Rate Limiting**: Built-in rate limiter (60 requests/hour) to prevent API bans
- **Diagnostics Panel**: Comprehensive diagnostics accessible via HA UI showing:
  - Cookie/session status and expiry
  - Rate limiter statistics
  - Vehicle information
  - Update success status
- **Debug Logging**: Enhanced logging with configurable debug mode
- **GitHub Actions CI**: Full CI/CD pipeline with:
  - Code formatting checks (black, isort)
  - Linting (flake8)
  - Type checking (mypy)
  - Unit tests (pytest)
  - Home Assistant validation (hassfest)
  - HACS validation
- **Comprehensive Test Suite**:
  - pytest with async support
  - Home Assistant test harness
  - 95%+ code coverage
  - Mock fixtures for all components
- **Pre-commit Hooks**: Automated code quality checks
- **Documentation**: Complete README with troubleshooting guide

### Changed
- **API Client**: Complete rewrite with enterprise features:
  - Async/await pattern throughout
  - Proper session lifecycle management
  - Automatic retry on session expiry
  - Configurable timeouts
  - Better error handling
- **Coordinator**: Enhanced with:
  - Configurable update intervals
  - Better error recovery
  - Auth failure detection
- **Config Flow**: Improved with:
  - Credential validation during setup
  - Better error messages
  - Unique ID enforcement
  - Reauth step handling
- **Options Flow**: Enhanced with:
  - Scan interval slider with validation
  - Dynamic vehicle list updates
  - Better error handling

### Fixed
- Session expiry no longer requires manual re-setup
- Cookie handling now properly serializes/deserializes
- Rate limiting prevents API bans
- Auth failures trigger proper reauth flow
- Network errors are properly caught and reported
- Empty vehicle lists handled gracefully

### Security
- Passwords never logged or exposed in diagnostics
- Email addresses redacted in diagnostics
- Secure cookie storage using HA's storage API
- No sensitive data in error messages

### Performance
- Reduced unnecessary API calls with cookie caching
- Rate limiting prevents excessive requests
- Configurable polling reduces server load
- Async operations throughout for better responsiveness

## [1.0.0] - Initial Release

### Added
- Basic Trackmate GPS integration
- Device tracker entities for vehicles
- GPS position tracking
- Speed and heading attributes
- Config flow for easy setup
- Options flow for vehicle selection
- Basic coordinator for data updates
- Translation support

[1.1.0]: https://github.com/example/trackmate_ha/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/example/trackmate_ha/releases/tag/v1.0.0
