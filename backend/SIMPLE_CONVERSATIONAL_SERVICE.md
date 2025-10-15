# Simple Conversational Service

## Overview

The Simple Conversational Service provides a clean, easy-to-use interface for AI-powered medical conversations. It combines the best features of the modular approach while maintaining simplicity and ease of use.

## Key Features

- **Simple API** - Easy to use with minimal configuration
- **Automatic Classification** - Automatically detects query types (drug info, diagnosis, general)
- **Built-in Validation** - Input validation and response sanitization
- **Professional Prompts** - Optimized prompts for different medical query types
- **Error Handling** - Robust error handling with retry mechanisms
- **Backward Compatible** - Works with existing code without changes

## Quick Start

### Basic Usage

```python
from healthnavi.services.simple_conversational_service import generate_response

# Simple usage (legacy interface)
response_text, is_complete = await generate_response(
    query="What are the side effects of aspirin?",
    patient_data="65-year-old male with hypertension"
)
```

### Enhanced Usage

```python
from healthnavi.services.simple_conversational_service import ConversationRequest, process_conversation

# Enhanced usage with more control
request = ConversationRequest(
    query="What are the side effects of aspirin?",
    patient_data="65-year-old male with hypertension",
    chat_history="Previous conversation about medications",
    user_id="user123"
)

response = await process_conversation(request)

print(f"Response: {response.response}")
print(f"Query Type: {response.query_type.value}")
print(f"Confidence: {response.confidence}")
print(f"Complete: {response.is_complete}")
print(f"Processing Time: {response.processing_time:.2f}s")
print(f"Sources: {response.sources}")
```

## Query Types

The service automatically classifies queries into three types:

### 1. Drug Information (`drug_info`)
- **Keywords**: side effects, contraindications, dosing, interactions, mechanism
- **Temperature**: 0.2 (conservative for factual information)
- **Use Case**: Drug safety information, pharmacology questions

### 2. Diagnosis (`diagnosis`)
- **Keywords**: differential diagnosis, diagnose, year-old, presents with, patient with
- **Temperature**: 0.4 (balanced for clinical reasoning)
- **Use Case**: Clinical assessment, differential diagnosis

### 3. General (`general`)
- **Keywords**: Default for all other queries
- **Temperature**: 0.3 (balanced for general medical information)
- **Use Case**: General medical questions, explanations

## Configuration

### Environment Variables

```bash
# Model Configuration
AI_MODEL=gemini-2.5-flash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# Generation Settings
AI_MAX_TOKENS=3000
AI_MAX_CONTEXT_LENGTH=3000
AI_MAX_SOURCES=5

# Temperature Settings
AI_DRUG_TEMPERATURE=0.2
AI_DIAGNOSIS_TEMPERATURE=0.4
AI_GENERAL_TEMPERATURE=0.3

# Validation
AI_ENABLE_VALIDATION=true
AI_MAX_RESPONSE_LENGTH=10000

# Retry Settings
AI_MAX_RETRIES=3
AI_RETRY_DELAY=1.0
```

### Programmatic Configuration

```python
from healthnavi.core.simple_config import get_simple_config

config = get_simple_config()
print(config.to_dict())
```

## Response Format

### Drug Information Response
```
**DRUG OVERVIEW**
Brief overview of the drug

**SIDE EFFECTS**
- Very Common: [list]
- Common: [list]
- Uncommon: [list]

**DRUG INTERACTIONS**
Known interactions or "No interactions documented"

**CONTRAINDICATIONS**
Contraindications or "No contraindications documented"

**Sources:** [source list]
```

### Diagnosis Response
```
**CLINICAL OVERVIEW**
1-2 paragraph summary

**DIFFERENTIAL DIAGNOSES**
1. [Primary Diagnosis] (XX%): [Justification]
2. [Secondary Diagnosis] (XX%): [Justification]

**IMMEDIATE WORKUP**
Essential tests and investigations

**MANAGEMENT**
Treatment recommendations

**RED FLAGS**
Warning signs requiring urgent attention

**Sources:** [source list]
```

### General Response
```
Clear, structured response with:
- Brief context about the topic
- Main information organized with headings
- Specific citations when stating medical facts
- Appropriate medical warnings if discussing serious conditions

**Sources:** [source list]
```

## Error Handling

The service includes comprehensive error handling:

```python
try:
    response = await process_conversation(request)
except HTTPException as e:
    if e.status_code == 429:
        print("Rate limit exceeded, please try again later")
    elif e.status_code == 500:
        print("AI service error, please try again")
    else:
        print(f"Error: {e.detail}")
```

## Service Information

Get information about the service:

```python
from healthnavi.services.simple_conversational_service import get_conversational_service

service = get_conversational_service()
info = service.get_service_info()
print(info)
```

Output:
```json
{
  "service_name": "SimpleConversationalService",
  "version": "1.0.0",
  "model": "gemini-2.5-flash",
  "max_context_length": 3000,
  "max_sources": 5,
  "max_tokens": 3000,
  "supported_query_types": ["drug_info", "diagnosis", "general"]
}
```

## Examples

### Drug Information Query
```python
request = ConversationRequest(
    query="What are the side effects of metformin?",
    patient_data="Type 2 diabetes patient"
)

response = await process_conversation(request)
# Returns structured drug information with side effects, interactions, etc.
```

### Diagnosis Query
```python
request = ConversationRequest(
    query="45-year-old female presents with chest pain",
    patient_data="Patient has hypertension and family history of heart disease"
)

response = await process_conversation(request)
# Returns differential diagnosis with probabilities and workup recommendations
```

### General Medical Query
```python
request = ConversationRequest(
    query="What is hypertension?",
    patient_data="General medical question"
)

response = await process_conversation(request)
# Returns general medical information with proper structure
```

## Integration with Existing Code

The service is designed to be a drop-in replacement for the existing conversational service:

```python
# This will automatically use the new simplified service
from healthnavi.services.conversational_service import generate_response

response_text, is_complete = await generate_response(
    query="What are the side effects of aspirin?",
    chat_history="",
    patient_data="65-year-old male with hypertension"
)
```

## Best Practices

1. **Use the enhanced interface** for new code to get access to metadata
2. **Provide context** in patient_data for better responses
3. **Handle errors gracefully** with appropriate user messages
4. **Monitor processing time** for performance optimization
5. **Use appropriate query types** for better classification

## Troubleshooting

### Common Issues

1. **Empty Response**: Check if query is too short or contains invalid characters
2. **Rate Limit**: Implement exponential backoff for retry logic
3. **Safety Filters**: Rephrase query if it triggers safety filters
4. **Context Too Long**: Reduce patient_data length if context is truncated

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger('healthnavi.services.simple_conversational_service').setLevel(logging.DEBUG)
```

## Performance

- **Response Time**: Typically 2-5 seconds depending on query complexity
- **Context Handling**: Automatically truncates long contexts
- **Caching**: No built-in caching, but can be added at the application level
- **Retry Logic**: Automatic retry with exponential backoff

## Security

- **Input Validation**: All inputs are validated and sanitized
- **Response Sanitization**: Responses are cleaned of potentially harmful content
- **Secure Logging**: Sensitive data is not logged
- **Error Handling**: No sensitive information leaked in error messages

## Migration from Legacy Service

The simplified service is backward compatible. To migrate:

1. **No changes needed** for existing code using `generate_response`
2. **Optional upgrade** to use `process_conversation` for enhanced features
3. **Configuration** can be updated via environment variables
4. **Testing** recommended to ensure compatibility

This simplified approach provides all the benefits of the modular system while maintaining ease of use and simplicity.

















