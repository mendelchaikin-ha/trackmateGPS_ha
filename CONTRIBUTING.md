# Contributing to Trackmate GPS Integration

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful, inclusive, and collaborative. We're all here to make great software.

## Getting Started

### Prerequisites

- Python 3.11 or 3.12
- Home Assistant development environment
- Git
- Basic understanding of Home Assistant integrations

### Development Setup

1. **Fork and clone**:
```bash
git clone https://github.com/yourusername/trackmate_ha.git
cd trackmate_ha
```

2. **Create virtual environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements_dev.txt
pip install -r requirements_test.txt
```

4. **Install pre-commit hooks**:
```bash
pre-commit install
```

5. **Run tests**:
```bash
pytest
```

## Development Workflow

### Branch Strategy

- `main`: Stable releases
- `develop`: Development branch
- Feature branches: `feature/your-feature-name`
- Bug fixes: `fix/issue-description`

### Making Changes

1. **Create a branch**:
```bash
git checkout -b feature/my-new-feature
```

2. **Make your changes**:
   - Write clean, documented code
   - Follow existing code style
   - Add tests for new features
   - Update documentation

3. **Test your changes**:
```bash
# Run tests
pytest

# Run specific test
pytest tests/test_api.py::TestRateLimiter -v

# With coverage
pytest --cov=custom_components/trackmate

# Check code style
black --check custom_components/trackmate
isort --check custom_components/trackmate
flake8 custom_components/trackmate
mypy custom_components/trackmate
```

4. **Commit your changes**:
```bash
git add .
git commit -m "feat: add new feature description"
```

Use conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `test:` Tests
- `refactor:` Code refactoring
- `chore:` Maintenance

5. **Push and create PR**:
```bash
git push origin feature/my-new-feature
```

Then create a Pull Request on GitHub.

## Code Style

### Python Style

We follow PEP 8 with some modifications:

- **Line length**: 127 characters (matches HA)
- **Formatter**: Black
- **Import sorting**: isort with black profile
- **Type hints**: Required for new code
- **Docstrings**: Google style

### Example

```python
"""Module docstring describing purpose."""
import logging
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class MyClass:
    """Class docstring.
    
    Attributes:
        attribute: Description of attribute.
    """
    
    def __init__(self, hass: HomeAssistant, config: Dict[str, Any]) -> None:
        """Initialize the class.
        
        Args:
            hass: Home Assistant instance.
            config: Configuration dictionary.
        """
        self.hass = hass
        self._config = config
    
    async def async_method(self, param: str) -> Optional[str]:
        """Do something asynchronously.
        
        Args:
            param: Description of parameter.
            
        Returns:
            Result or None if failed.
        """
        try:
            result = await self._do_work(param)
            return result
        except Exception as err:
            _LOGGER.error("Error in async_method: %s", err)
            return None
```

## Testing

### Writing Tests

Tests should:
- Cover new functionality
- Test edge cases
- Use mocks appropriately
- Be isolated and repeatable

### Test Structure

```python
"""Tests for my module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.trackmate.my_module import MyClass


class TestMyClass:
    """Test MyClass."""
    
    @pytest.mark.asyncio
    async def test_successful_case(self, hass):
        """Test successful case."""
        my_class = MyClass(hass, {})
        result = await my_class.async_method("test")
        assert result == "expected"
    
    @pytest.mark.asyncio
    async def test_error_case(self, hass):
        """Test error case."""
        my_class = MyClass(hass, {})
        with pytest.raises(ValueError):
            await my_class.async_method(None)
```

### Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_api.py

# Specific test
pytest tests/test_api.py::TestRateLimiter::test_rate_limiter_allows_requests_within_limit

# With output
pytest -v -s

# With coverage
pytest --cov=custom_components/trackmate --cov-report=html

# Integration tests
pytest tests/ --homeassistant-version=latest
```

## Documentation

### Code Documentation

- **Modules**: Docstring at top describing purpose
- **Classes**: Docstring with attributes/behavior
- **Functions**: Docstring with args/returns/raises
- **Complex logic**: Inline comments

### User Documentation

Update when:
- Adding features: Update README.md and SETUP_GUIDE.md
- Changing config: Update translations and docs
- Fixing bugs: Update CHANGELOG.md

## Pull Request Process

### Before Submitting

1. ✅ All tests pass
2. ✅ Code is formatted (black, isort)
3. ✅ No linting errors (flake8)
4. ✅ Type checking passes (mypy)
5. ✅ Documentation updated
6. ✅ CHANGELOG.md updated

### PR Description

Include:
- **What**: Clear description of changes
- **Why**: Reason for changes
- **How**: Implementation approach
- **Testing**: How you tested
- **Breaking changes**: If any

Example:
```markdown
## Description
Adds rate limiting to prevent API bans

## Motivation
Users were getting banned for too many requests

## Implementation
- Added RateLimiter class
- Integrated into API client
- Added tests and documentation

## Testing
- Unit tests for RateLimiter
- Integration tests with mock API
- Manual testing with real account

## Breaking Changes
None
```

### Review Process

1. Automated checks run (CI)
2. Maintainer reviews code
3. Address feedback
4. Approval and merge

## Release Process

Maintainers handle releases:

1. Update version in `manifest.json`
2. Update `CHANGELOG.md`
3. Create GitHub release
4. Tag version: `v1.1.0`

## Areas for Contribution

### Beginner-Friendly

- Documentation improvements
- Adding tests
- Fixing typos
- Improving error messages

### Intermediate

- Bug fixes
- Code refactoring
- Test coverage improvements
- Performance optimizations

### Advanced

- New features
- Architecture improvements
- Security enhancements
- Complex bug fixes

## Getting Help

- **Questions**: GitHub Discussions
- **Bugs**: GitHub Issues
- **Chat**: Home Assistant Discord (tag maintainers)

## Recognition

Contributors are:
- Listed in release notes
- Credited in CHANGELOG.md
- Appreciated in the community!

Thank you for contributing! 🎉
