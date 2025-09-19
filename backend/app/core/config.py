"""
Configuration management for HealthNavi AI CDSS.

This module provides secure configuration management following medical software
standards with proper environment variable handling and validation.
"""

import os
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseSettings, field_validator, Field
from pydantic_settings import SettingsConfigDict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseSettings):
    """Database configuration with security validation."""
    
    # Database connection settings
    db_user: str = Field(..., env="DB_USER")
    db_password: str = Field(..., env="DB_PASSWORD")
    db_host: str = Field(default="localhost", env="DB_HOST")
    db_port: int = Field(default=5432, env="DB_PORT")
    db_name: str = Field(..., env="DB_NAME")
    
    # Connection pool settings
    db_pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, env="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")
    
    @field_validator('db_password')
    @classmethod
    def validate_db_password(cls, v):
        """Validate database password strength."""
        if v == 'password' or len(v) < 8:
            raise ValueError('Database password must be at least 8 characters and not be "password"')
        return v
    
    @field_validator('db_port')
    @classmethod
    def validate_db_port(cls, v):
        """Validate database port."""
        if not 1 <= v <= 65535:
            raise ValueError('Database port must be between 1 and 65535')
        return v
    
    @property
    def database_url(self) -> str:
        """Get database URL."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


class SecurityConfig(BaseSettings):
    """Security configuration with validation."""
    
    # JWT settings
    secret_key: str = Field(..., env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # Encryption
    encryption_key: str = Field(..., env="ENCRYPTION_KEY")
    
    # Password settings
    min_password_length: int = Field(default=12, env="MIN_PASSWORD_LENGTH")
    max_password_length: int = Field(default=128, env="MAX_PASSWORD_LENGTH")
    
    # Rate limiting
    max_login_attempts: int = Field(default=5, env="MAX_LOGIN_ATTEMPTS")
    login_lockout_minutes: int = Field(default=15, env="LOGIN_LOCKOUT_MINUTES")
    
    @validator('secret_key')
    def validate_secret_key(cls, v):
        """Validate secret key strength."""
        if v == 'supersecretkey' or len(v) < 32:
            raise ValueError('Secret key must be at least 32 characters and not be the default')
        return v
    
    @validator('encryption_key')
    def validate_encryption_key(cls, v):
        """Validate encryption key."""
        if len(v) < 32:
            raise ValueError('Encryption key must be at least 32 characters')
        return v


class CORSConfig(BaseSettings):
    """CORS configuration with security validation."""
    
    allowed_origins: List[str] = Field(default=[], env="CORS_ORIGINS")
    allowed_methods: List[str] = Field(default=["GET", "POST"], env="CORS_METHODS")
    allowed_headers: List[str] = Field(default=["*"], env="CORS_HEADERS")
    allow_credentials: bool = Field(default=True, env="CORS_CREDENTIALS")
    
    @validator('allowed_origins')
    def validate_origins(cls, v):
        """Validate CORS origins for security."""
        if '*' in v:
            logger.warning("CORS allows all origins (*) - this is insecure for production!")
        return v


class ExternalServicesConfig(BaseSettings):
    """External services configuration."""
    
    # Google Cloud / Vertex AI
    gcp_project_id: str = Field(..., env="GCP_ID")
    gcp_location: str = Field(..., env="GCP_LOCATION")
    google_application_credentials: Optional[str] = Field(None, env="GOOGLE_APPLICATION_CREDENTIALS")
    
    # Azure OpenAI
    azure_openai_endpoint: str = Field(..., env="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: str = Field(..., env="AZURE_OPENAI_API_KEY")
    azure_openai_api_version: str = Field(default="2024-02-01", env="API_VERSION")
    azure_openai_deployment: str = Field(default="text-embedding-3-large", env="DEPLOYMENT")
    
    # Zilliz/Milvus
    milvus_uri: str = Field(..., env="MILVUS_URI")
    milvus_token: str = Field(..., env="MILVUS_TOKEN")
    milvus_collection_name: str = Field(default="medical_knowledge", env="MILVUS_COLLECTION_NAME")
    
    # AWS S3
    aws_access_key_id: str = Field(..., env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(..., env="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(..., env="AWS_REGION")
    aws_s3_bucket: str = Field(default="healthnavi-cdss", env="AWS_S3_BUCKET")
    
    @validator('azure_openai_api_key')
    def validate_azure_key(cls, v):
        """Validate Azure API key."""
        if len(v) < 32:
            raise ValueError('Azure OpenAI API key appears to be invalid')
        return v
    
    @validator('milvus_token')
    def validate_milvus_token(cls, v):
        """Validate Milvus token."""
        if len(v) < 16:
            raise ValueError('Milvus token appears to be invalid')
        return v


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        env="LOG_FORMAT"
    )
    log_file: Optional[str] = Field(None, env="LOG_FILE")
    log_max_size: int = Field(default=10485760, env="LOG_MAX_SIZE")  # 10MB
    log_backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of: {valid_levels}')
        return v.upper()


class ApplicationConfig(BaseSettings):
    """Main application configuration."""
    
    # Application settings
    app_name: str = Field(default="HealthNavi AI CDSS", env="APP_NAME")
    app_version: str = Field(default="2.0.0", env="APP_VERSION")
    app_description: str = Field(default="AI Clinical Decision Support System", env="APP_DESCRIPTION")
    environment: str = Field(default="development", env="ENV")
    debug: bool = Field(default=False, env="DEBUG")
    
    # API settings
    api_root_path: str = Field(default="/api/v2", env="API_ROOT_PATH")
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8050, env="API_PORT")
    
    # Data limits
    max_patient_data_length: int = Field(default=10000, env="MAX_PATIENT_DATA_LENGTH")
    max_chat_history_length: int = Field(default=50000, env="MAX_CHAT_HISTORY_LENGTH")
    max_query_length: int = Field(default=2000, env="MAX_QUERY_LENGTH")
    
    @validator('environment')
    def validate_environment(cls, v):
        """Validate environment setting."""
        valid_envs = ['development', 'staging', 'production']
        if v not in valid_envs:
            raise ValueError(f'Environment must be one of: {valid_envs}')
        return v
    
    @validator('api_port')
    def validate_api_port(cls, v):
        """Validate API port."""
        if not 1 <= v <= 65535:
            raise ValueError('API port must be between 1 and 65535')
        return v


class Config:
    """Main configuration class that combines all config sections."""
    
    def __init__(self):
        """Initialize configuration with validation."""
        try:
            self.database = DatabaseConfig()
            self.security = SecurityConfig()
            self.cors = CORSConfig()
            self.external_services = ExternalServicesConfig()
            self.logging = LoggingConfig()
            self.application = ApplicationConfig()
            
            logger.info("Configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise
    
    def validate_production_readiness(self) -> Dict[str, bool]:
        """
        Validate that configuration is ready for production.
        
        Returns:
            Dict with validation results
        """
        checks = {
            'environment_is_production': self.application.environment == 'production',
            'debug_disabled': not self.application.debug,
            'cors_restricted': '*' not in self.cors.allowed_origins,
            'secret_key_secure': self.security.secret_key != 'supersecretkey',
            'database_password_secure': self.database.db_password != 'password',
            'encryption_key_configured': bool(self.security.encryption_key),
            'log_file_configured': bool(self.logging.log_file),
        }
        
        return checks
    
    def get_database_url(self) -> str:
        """Get database URL."""
        return self.database.database_url
    
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.application.environment == 'production'
    
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.application.environment == 'development'


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config


def validate_environment() -> bool:
    """
    Validate that all required environment variables are set.
    
    Returns:
        True if validation passes, False otherwise
    """
    required_vars = [
        'SECRET_KEY',
        'ENCRYPTION_KEY',
        'DB_USER',
        'DB_PASSWORD',
        'DB_NAME',
        'GCP_ID',
        'GCP_LOCATION',
        'AZURE_OPENAI_ENDPOINT',
        'AZURE_OPENAI_API_KEY',
        'MILVUS_URI',
        'MILVUS_TOKEN',
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_REGION',
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return False
    
    return True


def setup_logging():
    """Setup logging configuration."""
    import logging.config
    
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': config.logging.log_format
            },
        },
        'handlers': {
            'default': {
                'level': config.logging.log_level,
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
            },
        },
        'loggers': {
            '': {
                'handlers': ['default'],
                'level': config.logging.log_level,
                'propagate': False
            }
        }
    }
    
    # Add file handler if configured
    if config.logging.log_file:
        logging_config['handlers']['file'] = {
            'level': config.logging.log_level,
            'formatter': 'standard',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': config.logging.log_file,
            'maxBytes': config.logging.log_max_size,
            'backupCount': config.logging.log_backup_count,
        }
        logging_config['loggers']['']['handlers'].append('file')
    
    logging.config.dictConfig(logging_config)
    logger.info(f"Logging configured with level: {config.logging.log_level}")
