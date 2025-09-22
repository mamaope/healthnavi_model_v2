"""
Core configuration module for HealthNavi AI CDSS.

This module contains application-wide configuration settings,
environment variable handling, and core utilities.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """Application settings."""
    
    # Application
    APP_NAME: str = "HealthNavi AI CDSS"
    VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secure-secret-key-min-32-characters-long")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "your-encryption-key-for-sensitive-data-32-chars")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://healthnavi_user:SecurePass123!@db:5432/healthnavi_cdss")
    DB_USER: str = os.getenv("DB_USER", "healthnavi_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "SecurePass123!")
    DB_HOST: str = os.getenv("DB_HOST", "db")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "healthnavi_cdss")
    
    # Google Cloud / Vertex AI
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    GOOGLE_CLOUD_PROJECT: Optional[str] = os.getenv("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    
    # Email Configuration
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "noreply@healthnavi.ai")
    FROM_NAME: str = os.getenv("FROM_NAME", "HealthNavi AI CDSS")
    
    # API Configuration
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8050")
    API_PREFIX: str = "/api/v2"
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # User Roles
    VALID_ROLES: list = ["user", "admin", "super_admin"]
    DEFAULT_ROLE: str = "user"

# Global settings instance
settings = Settings()

def get_config() -> Settings:
    """Get application configuration."""
    return settings
