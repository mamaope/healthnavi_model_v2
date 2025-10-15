# Console Logging Guide - Raw Response & Prompt Type

## Summary

Added comprehensive console logging to display:
1. **Which prompt was used** (differential_diagnosis, drug_information, clinical_guidance)
2. **Complete raw AI response** before any processing
3. **Response metadata** (length, headings, lists)

---

## Changes Made

### Backend Changes

#### 1. `backend/src/healthnavi/services/conversational_service.py`

**Modified return value to include prompt_type:**
```python
# Line 643
return sanitized_response, diagnosis_complete, query_type.value

# Line 672 - Updated function signature
async def generate_response(query: str, chat_history: str, patient_data: str) -> Tuple[str, bool, str]:
```

#### 2. `backend/src/healthnavi/schemas/__init__.py`

**Added prompt_type field to DiagnosisResponse:**
```python
class DiagnosisResponse(BaseModel):
    model_response: str
    diagnosis_complete: bool
    updated_chat_history: str
    session_id: Optional[int]
    message_id: Optional[int]
    prompt_type: Optional[str]  # NEW FIELD
```

#### 3. `backend/src/healthnavi/api/v1/diagnosis.py`

**Updated to handle and log prompt_type:**
```python
# Line 120-126
response, diagnosis_complete, prompt_type = await generate_response(
    query=data.patient_data,
    chat_history=chat_history,
    patient_data=data.patient_data
)

logger.info(f"🎯 Prompt type used: {prompt_type}")

# Line 187 - Include in response
diagnosis_data = DiagnosisResponse(
    model_response=response,
    diagnosis_complete=diagnosis_complete,
    updated_chat_history=updated_chat_history,
    session_id=session_id,
    message_id=message_id,
    prompt_type=prompt_type  # NEW
)
```

### Frontend Changes

#### `frontend/script.js`

**Added detailed logging after receiving response:**
```javascript
// Lines 604-621
console.log('\n' + '='.repeat(80));
console.log('📋 PROMPT & RESPONSE DEBUG INFO');
console.log('='.repeat(80));
console.log('🎯 Prompt Type Used:', data.data.prompt_type || 'Not provided by backend');
console.log('📊 Response Metadata:', {
    diagnosis_complete: data.data.diagnosis_complete,
    response_length: data.data.model_response?.length,
    has_headings: data.data.model_response?.includes('##'),
    has_lists: data.data.model_response?.includes('- ') || data.data.model_response?.includes('1. ')
});
console.log('\n📝 RAW AI RESPONSE (COMPLETE):');
console.log('─'.repeat(80));
console.log(data.data.model_response);
console.log('─'.repeat(80));
console.log('🔍 First 200 chars:', data.data.model_response?.substring(0, 200));
console.log('🔍 Last 200 chars:', data.data.model_response?.substring(data.data.model_response.length - 200));
console.log('='.repeat(80) + '\n');
```

---

## How to Use

### 1. Start Backend

```bash
cd backend
python -m uvicorn healthnavi.main:app --host 0.0.0.0 --port 8050 --reload
```

**Backend logs will show:**
```
🎯 Using prompt: differential_diagnosis
📝 Temperature setting: 0.4
📊 Context length: 1245 chars, Sources: 3
🎯 Prompt type used: differential_diagnosis
```

### 2. Open Frontend

1. Clear browser cache: `Ctrl + F5`
2. Open DevTools: `F12`
3. Go to Console tab

### 3. Send a Query

Send any medical query (e.g., "Adult patient with chest pain")

### 4. View Console Output

You'll see formatted output like this:

```
================================================================================
📋 PROMPT & RESPONSE DEBUG INFO
================================================================================
🎯 Prompt Type Used: differential_diagnosis
📊 Response Metadata: {
    diagnosis_complete: false,
    response_length: 3245,
    has_headings: true,
    has_lists: true
}

📝 RAW AI RESPONSE (COMPLETE):
────────────────────────────────────────────────────────────────────────────────
## Clinical Assessment ##

Patient presents with chest pain, shortness of breath...

## Differential Diagnoses ##

1. **Acute Myocardial Infarction** (40%): Evidence supports...
2. **Pulmonary Embolism** (30%): Patient shows signs of...

[Full response displayed here]
────────────────────────────────────────────────────────────────────────────────
🔍 First 200 chars: ## Clinical Assessment ##\n\nPatient presents with...
🔍 Last 200 chars: ...sources used in this assessment.
================================================================================
```

---

## Prompt Types

### 1. differential_diagnosis
**Triggered by keywords:**
- "differential diagnosis"
- "ddx"
- "patient with"
- "presents with"
- "year-old", "y/o"
- "symptoms suggest"

**Output:** JSON structure or structured markdown with:
- Clinical Overview
- Differential Diagnoses with probabilities
- Immediate Workup
- Management
- Red Flags

### 2. drug_information
**Triggered by keywords:**
- "side effects of"
- "contraindications for"
- "dosing of"
- "interactions of"
- "mechanism of action"
- "pharmacology"

**Output:** Structured markdown with:
- Drug Overview
- Side Effects
- Drug Interactions
- Contraindications
- Mechanism of Action

### 3. clinical_guidance (default)
**Triggered by:** All other medical queries

**Output:** Evidence-based clinical guidance with:
- Clinical Assessment
- Recommended Approach
- Monitoring & Follow-Up
- Contraindications & Warnings

---

## Debugging Formatting Issues

### Check Raw Response

1. Look at the console output for `RAW AI RESPONSE (COMPLETE)`
2. Check if headings are closed: `## Heading ##` vs `## Heading`
3. Check list spacing: Should have single newlines between items

### Example Issues

**Problem: Closed headings showing:**
```markdown
## Clinical Assessment ##
```

**Solution:** Frontend now strips closing `##` automatically.

**Problem: Lists broken apart:**
```markdown
- Item 1

- Item 2  ← Extra blank line breaks the list
```

**Solution:** Frontend removes excess blank lines between list items.

### Copy Raw Response

To copy the raw response for testing:
1. Open Console (F12)
2. Find the `RAW AI RESPONSE (COMPLETE)` section
3. Right-click on the response text
4. Click "Copy"
5. Paste into a markdown editor to test formatting

---

## Backend Logs

Backend also logs prompt info in the server console:

```
INFO: 🎯 Using prompt: differential_diagnosis
INFO: 📝 Temperature setting: 0.4
INFO: 📊 Context length: 1245 chars, Sources: 3
INFO: 🎯 Prompt type used: differential_diagnosis
INFO: AI diagnosis completed successfully. Response length: 3245 characters
```

---

## Testing Different Prompt Types

### Test Differential Diagnosis:
```
Adult patient presents with chest pain, shortness of breath, and diaphoresis. What are the differential diagnoses?
```

**Expected:** `🎯 Prompt Type Used: differential_diagnosis`

### Test Drug Information:
```
What are the side effects of aspirin?
```

**Expected:** `🎯 Prompt Type Used: drug_information`

### Test Clinical Guidance:
```
What is the treatment protocol for community-acquired pneumonia?
```

**Expected:** `🎯 Prompt Type Used: clinical_guidance`

---

## Troubleshooting

### "Prompt Type Used: Not provided by backend"

**Cause:** Backend not running latest code or response structure changed.

**Fix:**
1. Restart backend server
2. Check backend logs for errors
3. Verify backend is on correct git branch

### Console doesn't show logging

**Cause:** Browser cached old `script.js`.

**Fix:**
1. Hard refresh: `Ctrl + F5`
2. Clear browser cache completely
3. Open in incognito mode

### Raw response not displaying

**Cause:** Response structure changed or API error.

**Fix:**
1. Check Network tab in DevTools
2. Look for `/diagnosis/diagnose` request
3. Check Response payload structure
4. Verify `data.data.model_response` exists

---

## Files Modified

✅ Backend:
- `backend/src/healthnavi/services/conversational_service.py`
- `backend/src/healthnavi/schemas/__init__.py`
- `backend/src/healthnavi/api/v1/diagnosis.py`

✅ Frontend:
- `frontend/script.js`

✅ Documentation:
- `CONSOLE_LOGGING_GUIDE.md` (this file)

---

> **Status:** ✅ Complete - Console now displays prompt type and raw AI response for debugging

