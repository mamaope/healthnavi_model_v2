"""
Unit tests for authentication endpoints.
"""

import pytest
from fastapi import status


def test_register_user_success(client):
    """Test successful user registration."""
    response = client.post(
        "/api/v2/auth/register",
        json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "securepass123",
            "first_name": "New",
            "last_name": "User"
        }
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["success"] == 1
    assert "access_token" in data["data"]
    assert "user" in data["data"]


def test_register_user_duplicate_email(client, test_user):
    """Test registration with duplicate email."""
    response = client.post(
        "/api/v2/auth/register",
        json={
            "email": "test@example.com",
            "username": "differentuser",
            "password": "securepass123",
            "first_name": "Different",
            "last_name": "User"
        }
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert data["success"] == 0


def test_register_user_invalid_email(client):
    """Test registration with invalid email."""
    response = client.post(
        "/api/v2/auth/register",
        json={
            "email": "invalid-email",
            "username": "newuser",
            "password": "securepass123",
            "first_name": "New",
            "last_name": "User"
        }
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_register_user_short_password(client):
    """Test registration with password too short."""
    response = client.post(
        "/api/v2/auth/register",
        json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "short",
            "first_name": "New",
            "last_name": "User"
        }
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_login_success(client, test_user):
    """Test successful login."""
    response = client.post(
        "/api/v2/auth/login",
        json={
            "email": "test@example.com",
            "password": "testpass123"
        }
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] == 1
    assert "access_token" in data["data"]
    assert "user" in data["data"]


def test_login_invalid_credentials(client, test_user):
    """Test login with invalid password."""
    response = client.post(
        "/api/v2/auth/login",
        json={
            "email": "test@example.com",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["success"] == 0


def test_login_nonexistent_user(client):
    """Test login with non-existent user."""
    response = client.post(
        "/api/v2/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "somepassword"
        }
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_unauthorized(client):
    """Test accessing protected endpoint without token."""
    response = client.get("/api/v2/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_success(client, auth_token):
    """Test getting current user with valid token."""
    response = client.get(
        "/api/v2/auth/me",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] == 1
    assert data["data"]["email"] == "test@example.com"


def test_change_password_success(client, auth_token):
    """Test changing password successfully."""
    response = client.post(
        "/api/v2/auth/change-password",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "current_password": "testpass123",
            "new_password": "newpass123"
        }
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] == 1


def test_change_password_wrong_current(client, auth_token):
    """Test changing password with wrong current password."""
    response = client.post(
        "/api/v2/auth/change-password",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "current_password": "wrongpassword",
            "new_password": "newpass123"
        }
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert data["success"] == 0


def test_change_password_short_new(client, auth_token):
    """Test changing password with too short new password."""
    response = client.post(
        "/api/v2/auth/change-password",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "current_password": "testpass123",
            "new_password": "short"
        }
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
