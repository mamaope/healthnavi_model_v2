# Conversational Service Migration Guide

## Overview

The conversational service has been completely refactored into a modular, configurable system that provides better maintainability, flexibility, and professional standards. This guide explains the new architecture and how to migrate from the old system.

## New Architecture

### Core Components

1. **AI Configuration (`ai_config.py`)**
   - Centralized configuration for all AI-related settings
   - Model profiles with different temperature, token limits, and parameters
   - Query type definitions and mappings
   - Validation rules and response processing settings

2. **Prompt Manager (`prompt_manager.py`)**
   - Manages prompt templates with external file support
   - Dynamic template loading and caching
   - Version control for prompt templates
   - Support for custom prompt variables

3. **Query Classifier (`query_classifier.py`)**
   - Configurable rule-based classification
   - Support for custom classification rules
   - Multiple classification strategies (rule-based, ML-based, hybrid)
   - Detailed classification analysis and metrics

4. **Response Processor (`response_processor.py`)**
   - Comprehensive response validation and sanitization
   - Configurable validation rules
   - Response formatting and quality assessment
   - Security-focused content filtering

5. **Model Manager (`model_manager.py`)**
   - Centralized model initialization and management
   - Support for multiple model providers
   - Generation configuration management
   - Health monitoring and error handling

6. **Conversational Service V2 (`conversational_service_v2.py`)**
   - Main orchestrator that coordinates all components
   - Enhanced error handling and logging
   - Comprehensive metadata and metrics
   - Backward compatibility with legacy interface

## Configuration Files

### External Configuration Support

The new system supports external configuration files in the `backend/config/` directory:

- `prompts/` - Prompt template files (JSON format)
- `model_profiles.json` - Model configuration profiles
- `classification_rules.json` - Query classification rules

### Environment Variables

New environment variables for AI service configuration:

```bash
# AI Service Configuration
AI_DEFAULT_MODEL=gemini-2.5-flash
AI_MODEL_PROVIDER=vertex_ai
AI_DEFAULT_TEMPERATURE=0.3
AI_DEFAULT_MAX_TOKENS=3000
AI_MAX_CONTEXT_LENGTH=3000
AI_MAX_SOURCES=5
AI_MAX_RETRIES=3
AI_ENABLE_EXTERNAL_PROMPTS=true
AI_ENABLE_RESPONSE_VALIDATION=true
AI_MAX_RESPONSE_LENGTH=10000
```

## Migration Steps

### 1. Update Imports

Replace the old import:
```python
from healthnavi.services.conversational_service import generate_response
```

With the new import:
```python
from healthnavi.services.conversational_service_v2 import generate_response, process_conversation
```

### 2. Use New Interface (Recommended)

For new code, use the enhanced interface:

```python
from healthnavi.services.conversational_service_v2 import ConversationRequest, process_conversation

# Create request
request = ConversationRequest(
    query="What are the side effects of aspirin?",
    chat_history="",
    patient_data="65-year-old male with hypertension",
    user_id="user123",
    session_id="session456"
)

# Process conversation
response = await process_conversation(request)

# Access enhanced response data
print(f"Response: {response.response_text}")
print(f"Query Type: {response.query_type}")
print(f"Confidence: {response.confidence_score}")
print(f"Complete: {response.diagnosis_complete}")
print(f"Metadata: {response.processing_metadata}")
```

### 3. Legacy Interface (Backward Compatible)

The old interface still works:

```python
from healthnavi.services.conversational_service_v2 import generate_response

response_text, diagnosis_complete = await generate_response(
    query="What are the side effects of aspirin?",
    chat_history="",
    patient_data="65-year-old male with hypertension"
)
```

## Key Improvements

### 1. Modularity
- Each component can be independently configured and tested
- Easy to swap out components or add new ones
- Clear separation of concerns

### 2. Configuration Management
- External configuration files for easy updates
- Environment variable support
- Validation and type checking

### 3. Enhanced Error Handling
- Comprehensive error types and messages
- Retry mechanisms with exponential backoff
- Detailed logging and monitoring

### 4. Response Quality
- Multi-stage validation and sanitization
- Quality scoring and metrics
- Configurable validation rules

### 5. Professional Standards
- Comprehensive documentation
- Type hints throughout
- Proper exception handling
- Security-focused design

## Customization Examples

### Custom Prompt Template

Create a new prompt template file at `backend/config/prompts/custom_template.json`:

```json
[
  {
    "name": "custom_medical_template",
    "query_type": "general_query",
    "template": "You are a specialized medical AI...",
    "variables": ["patient_data", "context", "sources", "chat_history"],
    "description": "Custom template for specific medical queries",
    "version": "1.0.0"
  }
]
```

### Custom Model Profile

Add to `backend/config/model_profiles.json`:

```json
{
  "name": "ultra_conservative",
  "provider": "vertex_ai",
  "model_id": "gemini-1.5-pro",
  "temperature": 0.05,
  "max_tokens": 1500,
  "top_p": 0.7,
  "description": "Ultra-conservative settings for critical medical decisions"
}
```

### Custom Classification Rules

Add to `backend/config/classification_rules.json`:

```json
{
  "name": "emergency_detection",
  "query_type": "differential_diagnosis",
  "keywords": ["emergency", "urgent", "critical", "immediate"],
  "patterns": ["emergency.*situation", "urgent.*care", "critical.*condition"],
  "priority": 15,
  "description": "Detects emergency situations requiring immediate attention"
}
```

## Monitoring and Debugging

### Service Information

Get comprehensive service information:

```python
from healthnavi.services.conversational_service_v2 import get_conversational_service

service = get_conversational_service()
info = service.get_service_info()
print(info)
```

### Component Health

Check individual component health:

```python
from healthnavi.services.model_manager import get_model_manager

model_manager = get_model_manager()
is_healthy = model_manager.is_healthy()
print(f"Model Manager Healthy: {is_healthy}")
```

### Reload Components

Reload components after configuration changes:

```python
service = get_conversational_service()
service.reload_components()
```

## Best Practices

1. **Use the new interface** for new development
2. **Configure external files** for easy prompt and rule updates
3. **Monitor service health** in production
4. **Use appropriate model profiles** for different query types
5. **Validate responses** before presenting to users
6. **Log comprehensively** for debugging and monitoring

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all new modules are properly installed
2. **Configuration Errors**: Check environment variables and config files
3. **Model Initialization**: Verify Google Cloud credentials and project settings
4. **Template Loading**: Check file permissions and JSON syntax in config files

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger('healthnavi.services').setLevel(logging.DEBUG)
```

## Performance Considerations

- **Template Caching**: Templates are cached for 5 minutes by default
- **Model Reuse**: Models are initialized once and reused
- **Context Truncation**: Long contexts are automatically truncated
- **Response Validation**: Can be disabled for performance if needed

## Security Features

- **Input Sanitization**: All inputs are validated and sanitized
- **Response Validation**: Responses are checked for harmful content
- **Secure Logging**: Sensitive data is properly handled in logs
- **Error Handling**: No sensitive information leaked in error messages


















