"""
Prompt Manager Module for HealthNavi AI CDSS.

This module handles loading and managing prompt templates from JSON files.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of queries that can be processed."""
    DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"
    DRUG_INFORMATION = "drug_information"
    CLINICAL_GUIDANCE = "clinical_guidance"
    GENERAL_QUERY = "general_query"


@dataclass
class PromptConfig:
    """Configuration for a prompt template."""
    template: str
    variables: List[str]
    validation_rules: Dict[str, any]
    max_length: int
    description: str
    version: str


class PromptManager:
    """Manages prompt templates and their configurations."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the prompt manager."""
        self.config_dir = self._find_config_directory(config_dir)
        self.prompts: Dict[QueryType, PromptConfig] = {}
        self._load_prompts()
    
    def _find_config_directory(self, config_dir: Optional[Path]) -> Path:
        """Find the configuration directory."""
        if config_dir:
            return config_dir
        
        # Try multiple possible paths
        possible_paths = [
            Path("/app/config"),  # Docker container path
            Path(__file__).parent.parent.parent.parent / "config",  # Relative from this file
            Path("backend/config"),  # Relative from project root
            Path("./config"),  # Current directory
        ]
        
        for path in possible_paths:
            logger.info(f"Checking config path: {path}")
            if path.exists() and (path / "prompts").exists():
                logger.info(f"Found config directory at: {path}")
                return path
        
        logger.warning("Could not find config directory, using fallback")
        return Path("/app/config")  # Fallback
    
    def _load_prompts(self) -> None:
        """Load all prompt templates from JSON files."""
        prompts_dir = self.config_dir / "prompts"
        
        logger.info(f"Loading prompts from: {prompts_dir}")
        
        if not prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {prompts_dir}")
            self._load_default_prompts()
            return
        
        # Load each prompt file
        prompt_files = {
            "differential_diagnosis.json": QueryType.DIFFERENTIAL_DIAGNOSIS,
            "drug_information.json": QueryType.DRUG_INFORMATION,
            "clinical_guidance.json": QueryType.CLINICAL_GUIDANCE
        }
        
        for filename, query_type in prompt_files.items():
            file_path = prompts_dir / filename
            
            logger.info(f"Loading prompt file: {file_path}")
            
            if not file_path.exists():
                logger.warning(f"Prompt file not found: {file_path}")
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                prompt_config = PromptConfig(
                    template=data.get("template", ""),
                    variables=data.get("variables", []),
                    validation_rules=data.get("validation_rules", {}),
                    max_length=data.get("max_length", 8000),
                    description=data.get("description", ""),
                    version=data.get("version", "1.0.0")
                )
                
                self.prompts[query_type] = prompt_config
                logger.info(f"Loaded prompt for {query_type}: {len(prompt_config.template)} characters")
                
            except Exception as e:
                logger.error(f"Failed to load prompt {filename}: {e}")
        
        # Add default prompts for missing types
        self._add_default_prompts()
        
        logger.info(f"Total prompts loaded: {len(self.prompts)}")
    
    def _add_default_prompts(self) -> None:
        """Add default prompts for missing query types."""
        if QueryType.GENERAL_QUERY not in self.prompts:
            self.prompts[QueryType.GENERAL_QUERY] = PromptConfig(
                template="You are a helpful medical AI assistant. Please provide accurate and helpful information based on the user's query.",
                variables=["query"],
                validation_rules={},
                max_length=2000,
                description="Default general query prompt",
                version="1.0.0"
            )
    
    def _load_default_prompts(self) -> None:
        """Load default prompts when JSON files are not available."""
        logger.info("Loading default prompts")
        
        self.prompts = {
            QueryType.DIFFERENTIAL_DIAGNOSIS: PromptConfig(
                template="""You are an expert medical AI, assisting a qualified doctor.
Your task is to analyze patient data and provide a structured clinical assessment based only on the provided reference materials.

RULES

Source of Truth

Use ONLY the REFERENCE TEXT TO USE.

Do NOT reference external sources.

Citations

Cite sources ONLY for:

Clinical recommendations or diagnostic criteria

Guidelines/protocols

Diagnostic tests or treatments

Format: [Source: document_name, page/section].

Do NOT cite general/common knowledge.

Critical Safety

Always check first for life-threatening conditions.

If present → set "critical_alert": true and add urgent interventions under "management".

Clinical Standards

Correctly use medical acronyms.

Assign probability % (0–100%) for each differential diagnosis.

Output Format

Must return valid JSON only.

Follow the schema below exactly.

Do not include any extra commentary or text outside of JSON.

JSON Schema
{
  "clinical_overview": "string",
  "critical_alert": "boolean",
  "differential_diagnoses": [
    {
      "diagnosis": "string",
      "probability_percent": "number",
      "evidence": "string",
      "citations": ["string"]
    }
  ],
  "immediate_workup": ["string"],
  "management": ["string"],
  "red_flags": ["string"],
  "additional_information_needed": "string or null",
  "sources_used": ["string"]
}

Input Variables

REFERENCE TEXT TO USE: {context}

AVAILABLE KNOWLEDGE BASE SOURCES: {sources}

PATIENT'S CURRENT INFORMATION: {patient_data}

PREVIOUS CONVERSATION: {chat_history}""",
                variables=["patient_data", "chat_history", "context", "sources"],
                validation_rules={
                    "max_patient_data_length": 10000,
                    "max_chat_history_length": 50000,
                    "require_critical_assessment": True,
                    "require_probability_percentages": True,
                    "output_format": "json_only"
                },
                max_length=12000,
                description="JSON-structured differential diagnosis prompt for structured clinical assessment",
                version="4.0.0"
            ),
            QueryType.DRUG_INFORMATION: PromptConfig(
                template="You are an expert pharmacology AI. Provide comprehensive drug information based on the provided reference materials.",
                variables=["patient_data", "context", "sources", "chat_history"],
                validation_rules={},
                max_length=10000,
                description="Drug information prompt",
                version="2.1.0"
            ),
            QueryType.CLINICAL_GUIDANCE: PromptConfig(
                template="You are an expert clinical AI assistant. Provide evidence-based clinical guidance based on the provided reference materials.",
                variables=["patient_data", "context", "sources", "chat_history"],
                validation_rules={},
                max_length=10000,
                description="Clinical guidance prompt",
                version="2.1.0"
            ),
            QueryType.GENERAL_QUERY: PromptConfig(
                template="You are a helpful medical AI assistant. Please provide accurate and helpful information based on the user's query.",
                variables=["query"],
                validation_rules={},
                max_length=2000,
                description="Default general query prompt",
                version="1.0.0"
            )
        }
    
    def get_prompt(self, query_type: QueryType) -> Optional[PromptConfig]:
        """Get a prompt configuration for a specific query type."""
        return self.prompts.get(query_type)
    
    def get_all_prompts(self) -> Dict[QueryType, PromptConfig]:
        """Get all loaded prompt configurations."""
        return self.prompts.copy()
    
    def reload_prompts(self) -> None:
        """Reload all prompts from JSON files."""
        logger.info("Reloading prompts...")
        self.prompts.clear()
        self._load_prompts()
    
    def get_prompt_template(self, query_type: QueryType) -> str:
        """Get the template string for a specific query type."""
        prompt_config = self.get_prompt(query_type)
        return prompt_config.template if prompt_config else ""
    
    def get_prompt_variables(self, query_type: QueryType) -> List[str]:
        """Get the variables for a specific query type."""
        prompt_config = self.get_prompt(query_type)
        return prompt_config.variables if prompt_config else []


# Global prompt manager instance
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get the global prompt manager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


def reload_prompts() -> None:
    """Reload all prompts."""
    get_prompt_manager().reload_prompts()









