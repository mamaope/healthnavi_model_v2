# Chat History Implementation Guide

## Overview

Complete implementation of chat history for continuity between user messages and AI responses.

---

## How It Works

### 1. Frontend (script.js)

**Chat History Array:**
```javascript
let chatHistory = [];
```

**Format Function:**
```javascript
function formatChatHistory() {
    if (chatHistory.length === 0) return '';
    
    return chatHistory.map(entry => 
        `Doctor: ${entry.user}\nAI Assistant: ${entry.ai}`
    ).join('\n\n');
}
```

**Sending to API:**
```javascript
// In sendMessage() function
const response = await fetch(`${API_URL}/diagnosis/diagnose`, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Bearer ${accessToken}`
    },
    body: JSON.stringify({
        patient_data: message,          // Current message
        chat_history: formatChatHistory(), // Previous conversation
        session_id: currentSession.id   // Session ID
    })
});
```

**Updating After Response:**
```javascript
// Add to chat history after AI responds
chatHistory.push({
    user: message,
    ai: data.data.model_response
});
```

---

### 2. Backend (diagnosis.py)

**Receiving Chat History:**
```python
# Get chat history from request or session
chat_history = data.chat_history or ""

# If session_id provided, load history from database
if session_id:
    chat_history = session_service.get_chat_history(session_id, current_user)
```

**Format Example:**
```
Doctor: Adult patient presents with chest pain, shortness of breath, and diaphoresis.
AI Assistant: **CRITICAL ALERT 🚨** The patient presents with...
Doctor: Child does not look ill but has loss in appetite
AI Assistant: Based on the information provided...
```

---

### 3. Database Storage (diagnosis_session_service.py)

**Retrieving Chat History:**
```python
def get_chat_history(self, session_id: int, user: User) -> str:
    """Get formatted chat history for a session."""
    # Get all messages from session
    messages = self.db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.id.asc()).all()
    
    # Format as "Doctor: ... \n AI Assistant: ..."
    chat_history_parts = []
    for msg in messages:
        if msg.message_type == "user":
            chat_history_parts.append(f"Doctor: {msg.content}")
        elif msg.message_type == "assistant":
            chat_history_parts.append(f"AI Assistant: {msg.content}")
    
    return "\n".join(chat_history_parts)
```

---

## Complete Flow

### First Message

```
1. User types: "Adult patient with chest pain"
2. Frontend sends:
   {
     "patient_data": "Adult patient with chest pain",
     "chat_history": "",  // Empty on first message
     "session_id": 123
   }
3. Backend processes, AI responds
4. Frontend stores in chatHistory array
5. Backend stores in database as ChatMessage
```

### Subsequent Messages

```
1. User types: "Patient also has nausea"
2. Frontend sends:
   {
     "patient_data": "Patient also has nausea",
     "chat_history": "Doctor: Adult patient with chest pain\nAI Assistant: [previous response]",
     "session_id": 123
   }
3. Backend retrieves full history from database (includes all previous messages)
4. AI uses context to provide better response
5. Updated history stored
```

---

## Data Format

### Request Payload

```json
{
  "patient_data": "Current user message",
  "chat_history": "Doctor: message1\nAI Assistant: response1\nDoctor: message2\nAI Assistant: response2",
  "session_id": 123
}
```

### Response Payload

```json
{
  "success": true,
  "data": {
    "model_response": "AI response text",
    "diagnosis_complete": false,
    "updated_chat_history": "Doctor: message1\nAI Assistant: response1\nDoctor: message2\nAI Assistant: response2\nDoctor: current_message\nAI Assistant: current_response",
    "session_id": 123,
    "message_id": 456
  }
}
```

---

## Fix Needed in script.js

**IMPORTANT**: Change line 1561 from:
```javascript
`Doctor: ${entry.user}\nModel: ${entry.ai}`
```

To:
```javascript
`Doctor: ${entry.user}\nAI Assistant: ${entry.ai}`
```

This ensures frontend and backend use consistent format.

---

## Testing

### Test Chat Continuity

```javascript
// First message
POST /diagnosis/diagnose
{
  "patient_data": "Adult with chest pain",
  "chat_history": "",
  "session_id": 1
}

// Second message
POST /diagnosis/diagnose
{
  "patient_data": "Also has diaphoresis",
  "chat_history": "Doctor: Adult with chest pain\nAI Assistant: <previous response>",
  "session_id": 1
}
```

### Verify History Format

```python
# Backend endpoint to check
GET /chat/sessions/1/history

# Should return:
{
  "success": true,
  "data": {
    "chat_history": "Doctor: message1\nAI Assistant: response1\nDoctor: message2\nAI Assistant: response2"
  }
}
```

---

## Benefits

✅ **Context Preservation** - AI remembers previous conversation

✅ **Better Responses** - More accurate follow-up questions

✅ **Session Continuity** - Resume conversations later

✅ **Database Backup** - All history stored in database

---

## Error Handling

### No Session ID

```python
if not session_id:
    # Auto-create new session
    new_session = session_service.create_session(...)
    session_id = new_session.id
```

### Chat History Load Failure

```python
try:
    chat_history = session_service.get_chat_history(session_id, user)
except Exception as e:
    logger.warning(f"Could not get chat history: {e}")
    # Continue with provided chat_history from request
```

### Empty History

```javascript
// Frontend
function formatChatHistory() {
    if (chatHistory.length === 0) return '';  // Return empty string
    // ... format logic
}
```

---

## Implementation Checklist

- [x] Frontend formatChatHistory() function
- [x] Send chat_history in API request  
- [x] Backend receives and uses chat_history
- [x] Store messages in database
- [x] Retrieve history from database
- [ ] **Fix "Model:" to "AI Assistant:" in script.js line 1561**
- [x] Test multi-turn conversation
- [x] Verify context is preserved

---

## Example Full Conversation

```
Request 1:
{
  "patient_data": "55yo male with acute chest pain",
  "chat_history": ""
}

Response 1:
{
  "model_response": "🚨 CRITICAL: Need immediate workup...",
  "updated_chat_history": "Doctor: 55yo male with acute chest pain\nAI Assistant: 🚨 CRITICAL: Need immediate workup..."
}

Request 2:
{
  "patient_data": "ECG shows ST elevation in leads II, III, aVF",
  "chat_history": "Doctor: 55yo male with acute chest pain\nAI Assistant: 🚨 CRITICAL: Need immediate workup..."
}

Response 2:
{
  "model_response": "## 🚨 STEMI Alert\nInferior ST-Elevation Myocardial Infarction...",
  "updated_chat_history": "Doctor: 55yo male with acute chest pain\nAI Assistant: 🚨 CRITICAL...\nDoctor: ECG shows ST elevation in leads II, III, aVF\nAI Assistant: ## 🚨 STEMI Alert..."
}
```

---

> **Status:** Implementation complete and working. Just need to fix the label inconsistency in formatChatHistory().

