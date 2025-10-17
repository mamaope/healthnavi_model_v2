"""
Unified AI Configuration for HealthNavi AI CDSS.

This module provides centralized configuration for all AI-related components
including models, prompts, classification rules, and generation parameters.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Query type enumeration for classification."""
    DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"
    DRUG_INFORMATION = "drug_information"
    CLINICAL_GUIDANCE = "clinical_guidance"
    GENERAL_QUERY = "general_query"


class ModelProvider(Enum):
    """AI model provider enumeration."""
    VERTEX_AI = "vertex_ai"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class ModelConfig:
    """Configuration for AI models."""
    provider: ModelProvider
    model_name: str
    max_tokens: int = 4000
    temperature: float = 0.1
    top_p: float = 0.8
    top_k: int = 40
    safety_settings: Dict[str, Any] = field(default_factory=dict)
    generation_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptConfig:
    """Configuration for prompt templates."""
    template: str
    variables: List[str] = field(default_factory=list)
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    max_length: int = 8000


@dataclass
class ClassificationRule:
    """Rule for query classification."""
    keywords: List[str]
    query_type: QueryType
    confidence_threshold: float = 0.7
    priority: int = 1


@dataclass
class AIConfig:
    """Main AI configuration container."""
    models: Dict[str, ModelConfig] = field(default_factory=dict)
    prompts: Dict[QueryType, PromptConfig] = field(default_factory=dict)
    classification_rules: List[ClassificationRule] = field(default_factory=list)
    default_model: str = "gemini-2.5-flash"
    fallback_model: str = "gemini-2.5-flash"
    max_retries: int = 3
    timeout_seconds: int = 30
    enable_caching: bool = True
    enable_logging: bool = True


class AIConfigManager:
    """Manager for AI configuration loading and validation."""
    
    def __init__(self, config_dir: Optional[str] = None):
        """Initialize the AI configuration manager."""
        if config_dir is None:
            # Try multiple possible paths for the config directory
            possible_paths = [
                Path(__file__).parent.parent.parent.parent / "config",  # Relative from this file
                Path("/app/config"),  # Absolute path in Docker container
                Path("backend/config"),  # Relative from project root
                Path("./config"),  # Current directory
            ]
            
            self.config_dir = None
            for path in possible_paths:
                logger.info(f"Checking path: {path}")
                logger.info(f"Path exists: {path.exists()}")
                if path.exists():
                    prompts_dir = path / "prompts"
                    logger.info(f"Prompts dir exists: {prompts_dir.exists()}")
                    if prompts_dir.exists():
                        self.config_dir = path
                        logger.info(f"Found config directory at: {self.config_dir}")
                        break
            
            if self.config_dir is None:
                logger.warning("Could not find config directory, using default configuration")
                self.config_dir = Path("/app/config")  # Fallback
        else:
            self.config_dir = Path(config_dir)
        
        self._config: Optional[AIConfig] = None
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from files."""
        try:
            # Load model profiles
            models = self._load_model_profiles()
            
            # Load prompts
            prompts = self._load_prompts()
            
            # Load classification rules
            classification_rules = self._load_classification_rules()
            
            # Create main config
            self._config = AIConfig(
                models=models,
                prompts=prompts,
                classification_rules=classification_rules
            )
            
            logger.info("AI configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load AI configuration: {e}")
            # Fallback to default configuration
            self._config = self._get_default_config()
    
    def _load_model_profiles(self) -> Dict[str, ModelConfig]:
        """Load model profiles from JSON file."""
        models_file = self.config_dir / "model_profiles.json"
        
        if not models_file.exists():
            logger.warning(f"Model profiles file not found: {models_file}")
            return self._get_default_models()
        
        try:
            with open(models_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            models = {}
            for model_name, config_data in data.items():
                models[model_name] = ModelConfig(
                    provider=ModelProvider(config_data.get("provider", "vertex_ai")),
                    model_name=config_data.get("model_name", model_name),
                    max_tokens=config_data.get("max_tokens", 4000),
                    temperature=config_data.get("temperature", 0.1),
                    top_p=config_data.get("top_p", 0.8),
                    top_k=config_data.get("top_k", 40),
                    safety_settings=config_data.get("safety_settings", {}),
                    generation_config=config_data.get("generation_config", {})
                )
            
            return models
            
        except Exception as e:
            logger.error(f"Failed to load model profiles: {e}")
            return self._get_default_models()
    
    def _load_prompts(self) -> Dict[QueryType, PromptConfig]:
        """Load prompt templates from JSON files."""
        prompts_dir = self.config_dir / "prompts"
        prompts = {}
        
        logger.info(f"Loading prompts from: {prompts_dir}")
        logger.info(f"Config dir exists: {self.config_dir.exists()}")
        logger.info(f"Prompts dir exists: {prompts_dir.exists()}")
        
        if not prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {prompts_dir}")
            return self._get_default_prompts()
        
        # Load each prompt file
        prompt_files = {
            "differential_diagnosis.json": QueryType.DIFFERENTIAL_DIAGNOSIS,
            "drug_information.json": QueryType.DRUG_INFORMATION,
            "clinical_guidance.json": QueryType.CLINICAL_GUIDANCE
        }
        
        for filename, query_type in prompt_files.items():
            file_path = prompts_dir / filename
            
            logger.info(f"Checking file: {file_path}")
            logger.info(f"File exists: {file_path.exists()}")
            
            if not file_path.exists():
                logger.warning(f"Prompt file not found: {file_path}")
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                logger.info(f"Loaded prompt for {query_type}: {len(data.get('template', ''))} characters")
                
                prompts[query_type] = PromptConfig(
                    template=data.get("template", ""),
                    variables=data.get("variables", []),
                    validation_rules=data.get("validation_rules", {}),
                    max_length=data.get("max_length", 8000)
                )
                
            except Exception as e:
                logger.error(f"Failed to load prompt {filename}: {e}")
        
        # Add default prompts for missing types
        default_prompts = self._get_default_prompts()
        for query_type, prompt_config in default_prompts.items():
            if query_type not in prompts:
                logger.info(f"Using default prompt for {query_type}")
                prompts[query_type] = prompt_config
        
        logger.info(f"Total prompts loaded: {len(prompts)}")
        return prompts
    
    def _load_classification_rules(self) -> List[ClassificationRule]:
        """Load classification rules from JSON file."""
        rules_file = self.config_dir / "classification_rules.json"
        
        if not rules_file.exists():
            logger.warning(f"Classification rules file not found: {rules_file}")
            return self._get_default_classification_rules()
        
        try:
            with open(rules_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            rules = []
            for rule_data in data.get("rules", []):
                rules.append(ClassificationRule(
                    keywords=rule_data.get("keywords", []),
                    query_type=QueryType(rule_data.get("query_type", "general_query")),
                    confidence_threshold=rule_data.get("confidence_threshold", 0.7),
                    priority=rule_data.get("priority", 1)
                ))
            
            return rules
            
        except Exception as e:
            logger.error(f"Failed to load classification rules: {e}")
            return self._get_default_classification_rules()
    
    def _get_default_models(self) -> Dict[str, ModelConfig]:
        """Get default model configurations."""
        return {
            "gemini-2.5-flash": ModelConfig(
        provider=ModelProvider.VERTEX_AI,
                model_name="gemini-2.5-flash",
                max_tokens=4000,
        temperature=0.1,
        top_p=0.8,
                top_k=40,
                safety_settings={}
            )
        }
    
    def _get_default_prompts(self) -> Dict[QueryType, PromptConfig]:
        """Get default prompt configurations."""
        return {
            QueryType.DIFFERENTIAL_DIAGNOSIS: PromptConfig(
                template=f"""RULES: 1. **Source of Truth**: Base your entire analysis strictly on the REFERENCE TEXT TO USE. Do NOT reference sources that are not explicitly provided in the knowledge base. 2. **Selective Citations**: Only cite sources when: - Making specific clinical recommendations or diagnostic criteria - Stating clinical guidelines or protocols - Referencing specific diagnostic tests or treatment approaches - Quoting or paraphrasing specific clinical information Do NOT cite sources for general medical knowledge, basic pathophysiology, or common clinical observations. 3. **Accurate Citations**: When citing, use ONLY the exact source names from the AVAILABLE KNOWLEDGE BASE SOURCES list. Include page numbers, section names, or specific document identifiers when available in the format: [Source: document_name, page/section]. 4. **Medical Acronyms**: Interpret and correctly use common medical acronyms. 5. **Critical Assessment**: Always begin by checking for life-threatening conditions. If any vital signs are in a dangerous range, issue an "CRITICAL ALERT" immediately and prioritize urgent interventions. 6. **Output Format**: Structure your response using the following json format given below: 7. Add a probability percentage (0-100%) for each diagnosis listed in the differential, based on the information provided., signs, or recommendations. - Be direct and factual - no conversational greetings or filler words. 8. Provide output in json format. 9. If you need more information to refine the diagnosis or management plan, include an "ADDITIONAL INFORMATION NEEDED" section with one focused, essential question. 10. If the provided patient information is insufficient to generate a differential diagnosis, clearly state this and request more details. 11. If the patient information indicates a non-medical issue (e.g., social, psychological), state that a medical differential diagnosis is not applicable and suggest appropriate non-medical resources.

RULES
Source of Truth
-Use ONLY the REFERENCE TEXT TO USE.
-Do NOT reference external sources.

Citations
-Cite sources ONLY for:
-Clinical recommendations or diagnostic criteria

Guidelines/protocols
-Diagnostic tests or treatment

Format: [Source: document_name, page/section].
-Do NOT cite general/common knowledge.      

Critical Safety
-Always check first for life-threatening conditions.
-If present → set "critical_alert": true and add urgent interventions under "management".       

Clinical Standards
-Correctly use medical acronyms.
-Assign probability % (0–100%) for each differential diagnosis.

Output Format
-Must return valid JSON only.
-Follow the schema below exactly.
-Do not include any extra commentary or text outside of JSON.

JSON Schema
{
  "clinical_overview": "[Provide a brief 1-2 paragraph overview summarizing the case in relation to the question or user query, highlighting key clinical features and initial impression]",
  "critical_alert": "boolean",
  "differential_diagnoses": [
    {
      "diagnosis": "[primary diagnosis]",
      "probability_percent": "number",
      "evidence": "[Brief explanation with supporting/opposing evidence, cite specific guidelines when applicable]",
      "citations": ["string"]
    },
    {
      "diagnosis": "[secondary diagnosis]",
      "probability_percent": "number",
      "evidence": "[Brief explanation with supporting/opposing evidence, cite specific guidelines when applicable]",
      "citations": ["string"]
    }
  ],
  "immediate_workup": [{
    "test_or_investigation": "[name of test or investigation]",
    "reasoning": "[brief explanation of why this test or investigation is essential] [Cite specific guidelines when applicable]",
    "citations": ["string"]
  }],
    "management": [{
        "intervention": "[name of intervention]",
        "reasoning": "[brief explanation of why this intervention is essential] [Cite specific guidelines when applicable]",
        "citations": ["string"]
    }],
  "red_flags": [{
    "red_flag": "[name of red flag]",
    "reasoning": "[brief explanation of why this red flag is important] [Cite specific guidelines when applicable]",
    "citations": ["string"]
  }],
  "additional_information_needed": [{
    "question": "[question]",
    "reasoning": "[brief explanation of why this question is important] [Cite specific guidelines when applicable]",
    "citations": ["string"]
  }],
  "sources_used": ["string"]
}

Input Variables

REFERENCE TEXT TO USE: {context}

AVAILABLE KNOWLEDGE BASE SOURCES: {sources}

PATIENT’S CURRENT INFORMATION: {patient_data}

PREVIOUS CONVERSATION: {chat_history}""",
                variables=["patient_data", "chat_history", "context", "sources"],
                max_length=12000
            ),
            QueryType.DRUG_INFORMATION: PromptConfig(
                template="""You are a medical AI assistant specializing in drug information. Provide comprehensive information about the requested medication.

Drug Query: {query}

Please provide:
1. **Drug Name and Class**
2. **Indications**
3. **Dosage and Administration**
4. **Contraindications**
5. **Side Effects**
6. **Drug Interactions**
7. **Monitoring Requirements**

Format your response with clear headers and bullet points.""",
                variables=["query"],
                max_length=6000
            ),
            QueryType.CLINICAL_GUIDANCE: PromptConfig(
                template="""You are a medical AI assistant providing clinical guidance. Answer the clinical question based on evidence-based medicine.

Clinical Question: {query}

Please provide:
1. **Evidence-Based Answer**
2. **Clinical Guidelines**
3. **Recommendations**
4. **Important Considerations**

Format your response with clear headers and bullet points.""",
                variables=["query"],
                max_length=6000
            ),
            QueryType.GENERAL_QUERY: PromptConfig(
                template="""You are a medical AI assistant. Please provide helpful information about the medical topic.

Query: {query}

Please provide a clear, accurate, and helpful response.""",
                variables=["query"],
                max_length=4000
            )
        }
    
    def _get_default_classification_rules(self) -> List[ClassificationRule]:
        """Get default classification rules."""
        return [
            ClassificationRule(
                keywords=["differential", "diagnosis", "diagnose", "symptoms", "patient"],
            query_type=QueryType.DIFFERENTIAL_DIAGNOSIS,
                confidence_threshold=0.8,
                priority=1
            ),
            ClassificationRule(
                keywords=["drug", "medication", "medicine", "pharmaceutical", "dose", "dosage"],
                query_type=QueryType.DRUG_INFORMATION,
                confidence_threshold=0.7,
                priority=2
            ),
            ClassificationRule(
                keywords=["guideline", "protocol", "treatment", "management", "clinical"],
                query_type=QueryType.CLINICAL_GUIDANCE,
                confidence_threshold=0.7,
                priority=3
            ),
            ClassificationRule(
                keywords=["what", "how", "why", "when", "where"],
                query_type=QueryType.GENERAL_QUERY,
                confidence_threshold=0.5,
                priority=4
            )
        ]
    
    def _get_default_config(self) -> AIConfig:
        """Get default configuration as fallback."""
        return AIConfig(
            models=self._get_default_models(),
            prompts=self._get_default_prompts(),
            classification_rules=self._get_default_classification_rules()
        )
    
    @property
    def config(self) -> AIConfig:
        """Get the current configuration."""
        if self._config is None:
            self._config = self._get_default_config()
        return self._config
    
    def get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """Get configuration for a specific model."""
        return self.config.models.get(model_name)
    
    def get_prompt_config(self, query_type: QueryType) -> Optional[PromptConfig]:
        """Get prompt configuration for a specific query type."""
        return self.config.prompts.get(query_type)
    
    def get_classification_rules(self) -> List[ClassificationRule]:
        """Get all classification rules."""
        return self.config.classification_rules
    
    def reload_config(self) -> None:
        """Reload configuration from files."""
        self._load_config()


# Global configuration manager instance
_config_manager: Optional[AIConfigManager] = None


def get_ai_config_manager() -> AIConfigManager:
    """Get the global AI configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = AIConfigManager()
    return _config_manager


def get_ai_config() -> AIConfig:
    """Get the current AI configuration."""
    return get_ai_config_manager().config


def reload_ai_config() -> None:
    """Reload AI configuration from files."""
    get_ai_config_manager().reload_config()