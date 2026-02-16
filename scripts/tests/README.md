# Tests for ACCC Mergers Scripts

This directory contains comprehensive test suites for all Python scripts in the ACCC mergers data processing pipeline.

## Test Structure

- `test_normalization.py` - Tests for data normalization functions
- `test_cutoff.py` - Tests for cutoff date logic and merger filtering
- `test_extract_mergers.py` - Tests for merger extraction and filename sanitization
- `test_generate_weekly_digest.py` - Tests for weekly digest generation
- `test_parse_determination.py` - Tests for determination PDF parsing
- `test_parse_questionnaire.py` - Tests for questionnaire PDF parsing
- `test_generate_static_data.py` - Tests for static data generation

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### Run All Tests

```bash
# From the project root
pytest

# With coverage report
pytest --cov=scripts --cov-report=html
```

### Run Specific Test Files

```bash
# Run tests for a specific module
pytest scripts/tests/test_normalization.py

# Run a specific test class
pytest scripts/tests/test_cutoff.py::TestParseDate

# Run a specific test function
pytest scripts/tests/test_cutoff.py::TestParseDate::test_parse_iso_datetime
```

### Run Tests with Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

## Test Coverage

The test suite aims for comprehensive coverage of:

1. **Core Logic** - Business logic and data transformations
2. **Edge Cases** - Boundary conditions and unusual inputs
3. **Error Handling** - Invalid inputs and error conditions
4. **Data Validation** - Input sanitization and security checks

## Writing New Tests

When adding new tests:

1. Follow the existing naming conventions (`test_*.py`, `Test*`, `test_*`)
2. Use descriptive test names that explain what is being tested
3. Include docstrings for test classes and complex test functions
4. Group related tests into test classes
5. Use fixtures for common test data (when needed)
6. Mark tests appropriately (unit, integration, slow, requires_data)

## Continuous Integration

These tests should be run as part of the CI/CD pipeline before:
- Merging pull requests
- Deploying to production
- Making releases

## Notes

- Some tests may require mock data or fixtures for PDF parsing
- Tests are designed to run without external dependencies where possible
- All tests should be deterministic and not depend on current date/time (except where explicitly testing date logic)
