# Test Suite Documentation

## Overview

This test suite provides comprehensive coverage for the container-media-organizer project, including unit tests, integration tests, performance tests, and security tests.

**Current Coverage Target:** >80% code coverage with branch coverage

## Test Organization

```
tests/
├── conftest.py                      # Shared pytest fixtures
├── fixtures/                        # Test data and mock factories
│   ├── database_fixtures.py         # Pre-populated DB scenarios
│   ├── filesystem_fixtures.py       # File structure generators
│   └── mock_dmr.py                  # Mock DMR responses
├── unit/                            # Unit tests
│   ├── test_config.py
│   ├── test_core/                   # Core module tests
│   │   ├── test_logger.py
│   │   ├── test_database.py
│   │   └── test_database_edge_cases.py
│   ├── test_scanner/                # Scanner tests
│   │   └── test_filesystem.py
│   ├── test_ai/                     # AI module tests
│   │   ├── test_dmr_client.py
│   │   ├── test_dmr_edge_cases.py
│   │   └── test_identifier.py
│   └── test_organizer/              # Organizer tests
│       ├── test_merger.py
│       ├── test_deduplicator.py
│       └── test_cleanup.py
├── integration/                     # Integration tests
│   ├── test_full_pipeline.py
│   └── test_error_recovery.py
├── performance/                     # Performance tests
│   └── test_large_libraries.py
└── security/                        # Security tests
    └── test_path_validation.py
```

## Running Tests

### Run All Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run all tests with coverage
pytest --cov=src --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Run Specific Test Categories

```bash
# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests (without DMR)
pytest tests/integration/ -v -m "not requires_dmr"

# Performance tests
pytest tests/performance/ -v -m performance

# Security tests
pytest tests/security/ -v -m security

# Skip slow tests
pytest -v -m "not slow"
```

### Run Specific Test Files or Functions

```bash
# Run specific file
pytest tests/unit/test_organizer/test_deduplicator.py -v

# Run specific test class
pytest tests/unit/test_organizer/test_deduplicator.py::TestHashFile -v

# Run specific test function
pytest tests/unit/test_organizer/test_deduplicator.py::TestHashFile::test_hashes_file_correctly -v
```

### Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# Generate terminal coverage report
pytest --cov=src --cov-report=term-missing

# Enforce minimum coverage threshold
pytest --cov=src --cov-fail-under=80

# Generate XML coverage report (for CI)
pytest --cov=src --cov-report=xml
```

## Test Markers

Tests are marked with pytest markers to control execution:

- `@pytest.mark.integration` - Integration test (may be slow)
- `@pytest.mark.performance` - Performance test (may be very slow)
- `@pytest.mark.slow` - Very slow test (skip in CI)
- `@pytest.mark.security` - Security test
- `@pytest.mark.requires_dmr` - Requires Docker Model Runner to be running

### Using Markers

```bash
# Run only integration tests
pytest -v -m integration

# Run everything except slow tests
pytest -v -m "not slow"

# Run integration and performance tests
pytest -v -m "integration or performance"

# Skip tests requiring DMR
pytest -v -m "not requires_dmr"
```

## Test Fixtures

### Database Fixtures

Located in `tests/fixtures/database_fixtures.py`:

- `populated_db` - Database with sample files and creator mappings
- `db_with_duplicates` - Database with duplicate files (same hash)
- `db_with_unhashed_files` - Database with files needing hashing (NULL hashes)

### Filesystem Fixtures

Located in `tests/fixtures/filesystem_fixtures.py`:

- `simple_media_structure` - Basic creator folders with files
- `scattered_media_structure` - Unorganized media files
- `organized_media_structure` - Properly organized structure
- `media_with_duplicates` - Files with duplicate content
- `media_with_special_chars` - Files with unicode and special characters
- `container_folder_structure` - Container folder with subfolders
- `bracket_prefixed_folders` - Folders starting with '[' (should be skipped)

### Mock DMR Fixtures

Located in `tests/fixtures/mock_dmr.py`:

- `MockDMRResponse` - Builder for mock DMR API responses
- `mock_creator_identification_response()` - Generate AI identification responses
- `mock_malformed_json_response()` - Generate malformed responses for error testing

## Writing New Tests

### Unit Test Example

```python
"""Tests for new module."""
import pytest
from media_organizer.new_module import NewClass


class TestNewFeature:
    """Test new feature functionality."""

    def test_basic_operation(self, tmp_path):
        """Test basic operation works correctly."""
        # Arrange
        instance = NewClass()

        # Act
        result = instance.do_something()

        # Assert
        assert result is not None
```

### Using Fixtures

```python
def test_with_database(self, populated_db):
    """Test using pre-populated database."""
    count = populated_db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    assert count == 3

def test_with_filesystem(self, simple_media_structure):
    """Test using filesystem structure."""
    files = list(simple_media_structure.rglob('*.jpg'))
    assert len(files) > 0
```

### Mocking External Dependencies

```python
def test_with_mock_dmr(self, mocker):
    """Test with mocked DMR client."""
    from tests.fixtures.mock_dmr import MockDMRResponse

    mock_response = MockDMRResponse.success("Test content")
    mocker.patch('requests.post', return_value=mock_response)

    # Your test code here
```

## Coverage Goals

### Overall Targets

- **Overall Coverage:** >80%
- **Critical Modules:** >90% (Database, Deduplicator, Merger)
- **Branch Coverage:** >70%

### Current Status

Run `pytest --cov=src --cov-report=term-missing` to see current coverage.

### Checking Coverage

```bash
# View coverage summary
pytest --cov=src --cov-report=term

# View detailed line-by-line coverage
pytest --cov=src --cov-report=term-missing

# Generate HTML report for browser
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

## Continuous Integration

Tests are run automatically in GitHub Actions on every push and pull request.

### CI Test Command

```bash
# Run in CI (skips slow tests and DMR-dependent tests)
pytest tests/unit/ -v --cov=src --cov-report=xml
pytest tests/integration/ -v -m "not requires_dmr"
```

### Updating CI

The CI configuration is in `.github/workflows/validate.yml`. To add new test steps:

```yaml
- name: Run tests
  run: |
    pytest tests/unit/ -v --cov=src --cov-report=xml
    pytest tests/integration/ -v -m "not requires_dmr"
```

## Troubleshooting

### Tests Failing Locally

1. Ensure all dependencies are installed:
   ```bash
   pip install -e ".[dev]"
   ```

2. Clear pytest cache:
   ```bash
   pytest --cache-clear
   ```

3. Run with verbose output:
   ```bash
   pytest -vv --tb=short
   ```

### Import Errors

If you see import errors, ensure the package is installed in development mode:

```bash
pip install -e .
```

### Fixture Not Found

If pytest can't find a fixture:

1. Check `conftest.py` imports the fixture module
2. Verify `pytest_plugins` list includes the fixture module
3. Ensure fixture module is in `tests/fixtures/`

### Slow Tests

To skip slow tests during development:

```bash
pytest -v -m "not slow and not performance"
```

## Best Practices

1. **One assertion per test** - Tests should verify one thing
2. **Use descriptive test names** - Name should describe what is being tested
3. **Arrange-Act-Assert** - Structure tests clearly
4. **Use fixtures** - Avoid code duplication with fixtures
5. **Mock external dependencies** - Tests should be isolated
6. **Test edge cases** - Don't just test the happy path
7. **Keep tests fast** - Unit tests should run in milliseconds

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [pytest-mock documentation](https://pytest-mock.readthedocs.io/)
