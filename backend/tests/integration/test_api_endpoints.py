"""
Integration tests for API endpoints.
"""

import pytest
from fastapi import status


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/api/v2/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] == 1
    assert data["data"]["status"] == "healthy"


def test_admin_metrics_unauthorized(client):
    """Test admin metrics endpoint without authentication."""
    response = client.get("/api/v2/admin/metrics")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_admin_metrics_forbidden(client, auth_token):
    """Test admin metrics endpoint with non-admin user."""
    response = client.get(
        "/api/v2/admin/metrics",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_metrics_success(client, admin_token):
    """Test admin metrics endpoint with admin user."""
    response = client.get(
        "/api/v2/admin/metrics?days=30",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] == 1
    assert "data" in data


def test_admin_users_list(client, admin_token):
    """Test admin users list endpoint."""
    response = client.get(
        "/api/v2/admin/users?limit=10&offset=0",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] == 1
    assert "users" in data["data"]
    assert "total" in data["data"]


def test_admin_users_with_filters(client, admin_token):
    """Test admin users endpoint with filters."""
    response = client.get(
        "/api/v2/admin/users?limit=10&is_active=true&role=user",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] == 1


def test_admin_users_with_sorting(client, admin_token):
    """Test admin users endpoint with sorting."""
    response = client.get(
        "/api/v2/admin/users?limit=10&sort_by=created_at&sort_order=desc",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] == 1


def test_diagnosis_endpoint_validation(client):
    """Test diagnosis endpoint input validation."""
    # Test with too short patient data
    response = client.post(
        "/api/v2/diagnosis/diagnose",
        json={
            "patient_data": "ab"  # Too short
        }
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_diagnosis_endpoint_success(client):
    """Test diagnosis endpoint with valid input."""
    response = client.post(
        "/api/v2/diagnosis/diagnose",
        json={
            "patient_data": "Patient presents with fever and cough for 3 days"
        }
    )
    # May return 200 or 503 depending on AI service availability
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
