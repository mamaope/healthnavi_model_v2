# HealthNavi API Tests

This directory contains the test suite for the HealthNavi API.

## Structure

```
tests/
├── conftest.py          # Pytest fixtures and configuration
├── unit/                # Unit tests
│   └── test_auth.py    # Authentication unit tests
└── integration/         # Integration tests
    └── test_api_endpoints.py  # API endpoint integration tests
```

## Running Tests

### Install dependencies
```bash
pip install -r requirements-dev.txt
```

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=healthnavi --cov-report=html
```

### Run specific test file
```bash
pytest tests/unit/test_auth.py
```

### Run specific test
```bash
pytest tests/unit/test_auth.py::test_register_user_success
```

## Test Categories

- **Unit tests**: Test individual functions and methods in isolation
- **Integration tests**: Test API endpoints end-to-end

## Fixtures

- `client`: FastAPI TestClient instance
- `db`: Database session for tests
- `test_user`: Regular user for testing
- `admin_user`: Admin user for testing
- `auth_token`: Authentication token for regular user
- `admin_token`: Authentication token for admin user
