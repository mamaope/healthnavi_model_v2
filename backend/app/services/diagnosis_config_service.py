"""
Diagnosis Configuration Service for HealthNavi AI CDSS

This service handles diagnosis model configuration, prompts, and settings
for different user roles (admin vs regular users).
"""

import logging
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.database import SessionLocal
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

class ModelProvider(Enum):
    """Supported AI model providers."""
    GOOGLE_VERTEX_AI = "google_vertex_ai"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"

@dataclass
class ModelConfiguration:
    """Model configuration settings."""
    provider: str
    model_name: str
    temperature: float
    max_tokens: int
    top_p: float
    frequency_penalty: float
    presence_penalty: float
    timeout: int
    retry_attempts: int

@dataclass
class PromptConfiguration:
    """Prompt configuration settings."""
    system_prompt: str
    user_prompt_template: str
    context_prompt: str
    safety_prompt: str
    disclaimer_prompt: str
    max_context_length: int
    include_chat_history: bool
    include_patient_history: bool

@dataclass
class DiagnosisConfiguration:
    """Complete diagnosis configuration."""
    config_id: str
    name: str
    description: str
    model_config: ModelConfiguration
    prompt_config: PromptConfiguration
    is_default: bool
    is_active: bool
    created_by: int
    created_at: datetime
    updated_at: datetime
    version: str

class DiagnosisConfigService:
    """Service for managing diagnosis configurations."""
    
    def __init__(self):
        """Initialize the diagnosis configuration service."""
        self.SessionLocal = SessionLocal
        self.default_config = self._get_default_configuration()
    
    def _get_default_configuration(self) -> DiagnosisConfiguration:
        """Get the default diagnosis configuration."""
        return DiagnosisConfiguration(
            config_id="default",
            name="Default Diagnosis Configuration",
            description="Standard configuration for regular users",
            model_config=ModelConfiguration(
                provider=ModelProvider.GOOGLE_VERTEX_AI.value,
                model_name="gemini-2.0-flash-exp",
                temperature=0.3,
                max_tokens=2048,
                top_p=0.9,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                timeout=30,
                retry_attempts=3
            ),
            prompt_config=PromptConfiguration(
                system_prompt="""You are HealthNavi AI, a clinical decision support system designed to assist healthcare professionals with diagnostic considerations and treatment recommendations.

Your role is to:
1. Analyze patient data and symptoms
2. Provide differential diagnoses
3. Suggest relevant tests and examinations
4. Recommend treatment approaches
5. Highlight urgent conditions requiring immediate attention

Always maintain professional medical standards and emphasize the importance of clinical judgment.""",
                user_prompt_template="""Patient Data: {patient_data}

Chat History: {chat_history}

Please provide a comprehensive diagnostic assessment including:
1. Primary differential diagnoses
2. Recommended investigations
3. Treatment considerations
4. Follow-up recommendations
5. Red flags requiring immediate attention""",
                context_prompt="""Consider the following clinical context:
- Patient demographics and history
- Presenting symptoms and duration
- Physical examination findings
- Previous medical history
- Current medications and allergies""",
                safety_prompt="""IMPORTANT SAFETY CONSIDERATIONS:
- This is a decision support tool, not a replacement for clinical judgment
- Always verify critical findings through appropriate clinical evaluation
- Consider urgent conditions requiring immediate intervention
- Ensure patient safety is the primary concern""",
                disclaimer_prompt="""DISCLAIMER:
This AI system provides decision support only. All clinical decisions must be made by qualified healthcare professionals. The system does not replace clinical judgment, physical examination, or appropriate diagnostic testing.""",
                max_context_length=8000,
                include_chat_history=True,
                include_patient_history=True
            ),
            is_default=True,
            is_active=True,
            created_by=0,  # System
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            version="1.0.0"
        )
    
    def get_configuration_for_user(self, user_id: int) -> DiagnosisConfiguration:
        """Get appropriate configuration for a user based on their role."""
        db = self.SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"User {user_id} not found, using default config")
                return self.default_config
            
            # For now, return default config for all users
            # In the future, we can implement user-specific configurations
            if user.is_admin():
                logger.info(f"Admin user {user_id} using default config")
                return self.default_config
            else:
                logger.info(f"Regular user {user_id} using default config")
                return self.default_config
                
        except SQLAlchemyError as e:
            logger.error(f"Database error getting user config: {e}")
            return self.default_config
        finally:
            db.close()
    
    def get_available_configurations(self, user_id: int) -> List[DiagnosisConfiguration]:
        """Get all available configurations for a user."""
        db = self.SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return [self.default_config]
            
            # For now, return default config
            # In the future, we can implement multiple configurations
            return [self.default_config]
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting available configs: {e}")
            return [self.default_config]
        finally:
            db.close()
    
    def create_custom_configuration(self, user_id: int, config_data: Dict[str, Any]) -> Optional[DiagnosisConfiguration]:
        """Create a custom configuration (admin only)."""
        db = self.SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_admin():
                logger.warning(f"User {user_id} not authorized to create custom config")
                return None
            
            # Create custom configuration
            custom_config = DiagnosisConfiguration(
                config_id=f"custom_{user_id}_{int(datetime.utcnow().timestamp())}",
                name=config_data.get("name", "Custom Configuration"),
                description=config_data.get("description", ""),
                model_config=ModelConfiguration(**config_data.get("model_config", {})),
                prompt_config=PromptConfiguration(**config_data.get("prompt_config", {})),
                is_default=False,
                is_active=True,
                created_by=user_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                version="1.0.0"
            )
            
            # In a real implementation, we would save this to the database
            logger.info(f"Custom configuration created for user {user_id}")
            return custom_config
            
        except Exception as e:
            logger.error(f"Error creating custom configuration: {e}")
            return None
        finally:
            db.close()
    
    def update_configuration(self, user_id: int, config_id: str, updates: Dict[str, Any]) -> bool:
        """Update a configuration (admin only)."""
        db = self.SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_admin():
                logger.warning(f"User {user_id} not authorized to update config")
                return False
            
            # In a real implementation, we would update the database
            logger.info(f"Configuration {config_id} updated by user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return False
        finally:
            db.close()
    
    def delete_configuration(self, user_id: int, config_id: str) -> bool:
        """Delete a configuration (admin only)."""
        db = self.SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_admin():
                logger.warning(f"User {user_id} not authorized to delete config")
                return False
            
            # Cannot delete default configuration
            if config_id == "default":
                logger.warning("Cannot delete default configuration")
                return False
            
            # In a real implementation, we would delete from database
            logger.info(f"Configuration {config_id} deleted by user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting configuration: {e}")
            return False
        finally:
            db.close()
    
    def validate_configuration(self, config_data: Dict[str, Any]) -> List[str]:
        """Validate configuration data."""
        errors = []
        
        # Validate model configuration
        model_config = config_data.get("model_config", {})
        if not isinstance(model_config, dict):
            errors.append("Model configuration must be a dictionary")
        else:
            if "temperature" in model_config:
                temp = model_config["temperature"]
                if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
                    errors.append("Temperature must be between 0 and 2")
            
            if "max_tokens" in model_config:
                tokens = model_config["max_tokens"]
                if not isinstance(tokens, int) or tokens < 1 or tokens > 8192:
                    errors.append("Max tokens must be between 1 and 8192")
        
        # Validate prompt configuration
        prompt_config = config_data.get("prompt_config", {})
        if not isinstance(prompt_config, dict):
            errors.append("Prompt configuration must be a dictionary")
        else:
            required_prompts = ["system_prompt", "user_prompt_template"]
            for prompt in required_prompts:
                if prompt not in prompt_config or not prompt_config[prompt]:
                    errors.append(f"{prompt} is required")
        
        return errors

# Global diagnosis configuration service instance
diagnosis_config_service = DiagnosisConfigService()
