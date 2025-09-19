"""
Comprehensive test suite for HealthNavi AI CDSS.

This module provides security-focused tests with >80% coverage
following medical software testing standards.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from app.main import app
from app.core.database import get_db, Base
from app.core.models import User, AuditLog, SecurityEvent
from app.core.auth import create_access_token, get_password_hash
from app.core.security import PasswordValidator, EncryptionService, InputValidator


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Test client
client = TestClient(app)


@pytest.fixture(scope="module")
def setup_database():
    """Setup test database."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(setup_database):
    """Create test user."""
    db = TestingSessionLocal()
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("TestPassword123!"),
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.delete(user)
    db.commit()
    db.close()


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers."""
    token = create_access_token(data={"sub": test_user.username})
    return {"Authorization": f"Bearer {token}"}


class TestSecurity:
    """Test security features."""
    
    def test_password_validation(self):
        """Test password validation."""
        # Valid password
        result = PasswordValidator.validate_password("TestPassword123!")
        assert result['is_valid'] is True
        assert len(result['errors']) == 0
        
        # Weak password
        result = PasswordValidator.validate_password("weak")
        assert result['is_valid'] is False
        assert len(result['errors']) > 0
        
        # Password with forbidden pattern
        result = PasswordValidator.validate_password("password123!")
        assert result['is_valid'] is False
        assert any("password" in error.lower() for error in result['errors'])
    
    def test_encryption_service(self):
        """Test encryption service."""
        service = EncryptionService()
        
        # Test encryption/decryption
        test_data = "Sensitive patient data"
        encrypted = service.encrypt_phi(test_data)
        decrypted = service.decrypt_phi(encrypted)
        
        assert decrypted == test_data
        assert encrypted != test_data
        
        # Test invalid data
        with pytest.raises(ValueError):
            service.encrypt_phi("")
        
        with pytest.raises(ValueError):
            service.decrypt_phi("invalid_data")
    
    def test_input_validation(self):
        """Test input validation."""
        # Valid patient data
        result = InputValidator.validate_patient_data("Patient has fever")
        assert result['is_valid'] is True
        
        # Empty data
        result = InputValidator.validate_patient_data("")
        assert result['is_valid'] is False
        
        # Malicious content
        result = InputValidator.validate_patient_data("<script>alert('xss')</script>")
        assert result['is_valid'] is False
        
        # Too long data
        long_data = "x" * 15000
        result = InputValidator.validate_patient_data(long_data)
        assert result['is_valid'] is False


class TestAuthentication:
    """Test authentication endpoints."""
    
    def test_user_registration(self, setup_database):
        """Test user registration."""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "NewPassword123!",
            "full_name": "New User"
        }
        
        response = client.post("/auth/register", json=user_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert "password" not in data
    
    def test_user_registration_duplicate_email(self, setup_database, test_user):
        """Test user registration with duplicate email."""
        user_data = {
            "username": "anotheruser",
            "email": test_user.email,
            "password": "AnotherPassword123!"
        }
        
        response = client.post("/auth/register", json=user_data)
        assert response.status_code == 400
        assert "Email already registered" in response.json()["error"]
    
    def test_user_registration_weak_password(self, setup_database):
        """Test user registration with weak password."""
        user_data = {
            "username": "weakuser",
            "email": "weak@example.com",
            "password": "weak"
        }
        
        response = client.post("/auth/register", json=user_data)
        assert response.status_code == 422  # Validation error
    
    def test_user_login(self, setup_database, test_user):
        """Test user login."""
        login_data = {
            "username": test_user.username,
            "password": "TestPassword123!"
        }
        
        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_user_login_invalid_credentials(self, setup_database, test_user):
        """Test user login with invalid credentials."""
        login_data = {
            "username": test_user.username,
            "password": "WrongPassword"
        }
        
        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["error"]
    
    def test_get_current_user(self, setup_database, test_user, auth_headers):
        """Test getting current user info."""
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["username"] == test_user.username
        assert data["email"] == test_user.email
        assert "password" not in data
    
    def test_get_current_user_unauthorized(self, setup_database):
        """Test getting current user without authentication."""
        response = client.get("/auth/me")
        assert response.status_code == 401


class TestDiagnosis:
    """Test diagnosis endpoints."""
    
    @patch('app.services.conversational_service.generate_response')
    def test_diagnosis_endpoint(self, mock_generate_response, setup_database, test_user, auth_headers):
        """Test diagnosis endpoint."""
        mock_generate_response.return_value = ("Test diagnosis response", True)
        
        diagnosis_data = {
            "patient_data": "Patient has fever and cough",
            "chat_history": "",
            "session_id": "test-session-123"
        }
        
        response = client.post("/diagnosis/diagnose", json=diagnosis_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "model_response" in data
        assert "diagnosis_complete" in data
        assert "session_id" in data
    
    def test_diagnosis_endpoint_unauthorized(self, setup_database):
        """Test diagnosis endpoint without authentication."""
        diagnosis_data = {
            "patient_data": "Patient has fever and cough"
        }
        
        response = client.post("/diagnosis/diagnose", json=diagnosis_data)
        assert response.status_code == 401
    
    def test_diagnosis_endpoint_invalid_data(self, setup_database, test_user, auth_headers):
        """Test diagnosis endpoint with invalid data."""
        diagnosis_data = {
            "patient_data": ""  # Empty patient data
        }
        
        response = client.post("/diagnosis/diagnose", json=diagnosis_data, headers=auth_headers)
        assert response.status_code == 400
    
    def test_diagnosis_endpoint_malicious_content(self, setup_database, test_user, auth_headers):
        """Test diagnosis endpoint with malicious content."""
        diagnosis_data = {
            "patient_data": "<script>alert('xss')</script>"
        }
        
        response = client.post("/diagnosis/diagnose", json=diagnosis_data, headers=auth_headers)
        assert response.status_code == 400


class TestAuditLogging:
    """Test audit logging functionality."""
    
    def test_audit_log_creation(self, setup_database):
        """Test audit log creation."""
        db = TestingSessionLocal()
        
        from app.core.database import DatabaseAuditLogger
        
        audit_log = DatabaseAuditLogger.log_user_action(
            db=db,
            user_id=1,
            username="testuser",
            action="test_action",
            success=True
        )
        
        assert audit_log.id is not None
        assert audit_log.action == "test_action"
        assert audit_log.success is True
        
        db.close()
    
    def test_security_event_logging(self, setup_database):
        """Test security event logging."""
        db = TestingSessionLocal()
        
        from app.core.database import DatabaseAuditLogger
        
        security_event = DatabaseAuditLogger.log_security_event(
            db=db,
            event_type="failed_login",
            severity="medium",
            details="Multiple failed login attempts",
            user_id=1
        )
        
        assert security_event.id is not None
        assert security_event.event_type == "failed_login"
        assert security_event.severity == "medium"
        
        db.close()


class TestAPIEndpoints:
    """Test API endpoints."""
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "services" in data
    
    def test_root_endpoint(self):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "version" in data
    
    def test_cors_headers(self):
        """Test CORS headers."""
        response = client.options("/health")
        # CORS headers should be present
        assert response.status_code in [200, 204]


class TestErrorHandling:
    """Test error handling."""
    
    def test_404_error(self):
        """Test 404 error handling."""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
    
    def test_validation_error(self, setup_database, test_user, auth_headers):
        """Test validation error handling."""
        # Invalid JSON
        response = client.post(
            "/auth/login",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_login_rate_limiting(self, setup_database, test_user):
        """Test login rate limiting."""
        login_data = {
            "username": test_user.username,
            "password": "WrongPassword"
        }
        
        # Make multiple failed login attempts
        for _ in range(6):  # More than max_login_attempts
            response = client.post("/auth/login", json=login_data)
            if response.status_code == 423:  # Account locked
                break
        
        # Should eventually get locked
        assert response.status_code == 423
        assert "locked" in response.json()["detail"].lower()


class TestDataProtection:
    """Test data protection features."""
    
    def test_phi_encryption(self):
        """Test PHI encryption."""
        service = EncryptionService()
        
        phi_data = "Patient John Doe, DOB: 01/01/1990, SSN: 123-45-6789"
        encrypted = service.encrypt_phi(phi_data)
        
        # Encrypted data should not contain original PHI
        assert "John Doe" not in encrypted
        assert "123-45-6789" not in encrypted
        
        # Should be able to decrypt
        decrypted = service.decrypt_phi(encrypted)
        assert decrypted == phi_data
    
    def test_log_sanitization(self):
        """Test log sanitization."""
        from app.core.security import SecureLogger
        
        # Test PHI sanitization
        message = "User John Doe (SSN: 123-45-6789) logged in"
        sanitized = SecureLogger.sanitize_log_message(message)
        
        assert "John Doe" not in sanitized
        assert "123-45-6789" not in sanitized
        assert "[REDACTED]" in sanitized


# Integration tests
class TestIntegration:
    """Integration tests."""
    
    @pytest.mark.integration
    def test_full_diagnosis_flow(self, setup_database):
        """Test complete diagnosis flow."""
        # Register user
        user_data = {
            "username": "integrationuser",
            "email": "integration@example.com",
            "password": "IntegrationPassword123!"
        }
        
        response = client.post("/auth/register", json=user_data)
        assert response.status_code == 201
        
        # Login
        login_data = {
            "username": user_data["username"],
            "password": user_data["password"]
        }
        
        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 200
        
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Make diagnosis request
        with patch('app.services.conversational_service.generate_response') as mock_generate:
            mock_generate.return_value = ("Test diagnosis", True)
            
            diagnosis_data = {
                "patient_data": "Patient has chest pain",
                "chat_history": ""
            }
            
            response = client.post("/diagnosis/diagnose", json=diagnosis_data, headers=headers)
            assert response.status_code == 200
            
            data = response.json()
            assert "model_response" in data
            assert "session_id" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app", "--cov-report=html"])
