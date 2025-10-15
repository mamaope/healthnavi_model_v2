# Heading Format Fix - Closed Heading Syntax

## Summary

Updated all prompt templates to use **closed heading syntax** (`## Heading ##`) instead of open headings (`## Heading`). This ensures proper markdown parsing and prevents AI models from continuing text on the same line as headings.

---

## Problem

When using open heading syntax (`## Heading`), AI models sometimes:
- Continue text on the same line after the heading
- Don't properly recognize where the heading ends
- Create rendering issues in the frontend

---

## Solution

Use **closed heading syntax** where headings are explicitly closed with `##`:

### ❌ Before (Open Headings)
```markdown
## Clinical Assessment
Content here...
```

### ✅ After (Closed Headings)
```markdown
## Clinical Assessment ##
Content here...
```

---

## Files Updated

### 1. backend/config/prompts/clinical_guidance.json
- Version: 2.3.0 → **2.4.0**
- Updated markdown format rules to specify closed headings
- Updated example sections to use `## Heading ##` format
- Added explicit reminder about closed heading format

**Changes:**
```json
"Use ## for main section headings with CLOSING ## (e.g., ## 🏥 Clinical Assessment ##)"
"Use ### for subsections with CLOSING ### (e.g., ### Subsection ###)"
```

**Example sections:**
```markdown
## 🏥 Clinical Assessment ##
## ⚕️ Recommended Approach ##
## 📊 Monitoring & Follow-Up ##
## ⚠️ Contraindications & Warnings ##
## 📚 Sources ##
```

### 2. backend/config/prompts/drug_information.json
- Version: 2.3.0 → **2.4.0**
- Updated markdown format rules to specify closed headings
- Updated example sections to use `## Heading ##` format
- Added explicit reminder about closed heading format

**Example sections:**
```markdown
## 💊 Drug Overview ##
## ⚠️ Side Effects ##
## 🔄 Drug Interactions ##
## 🚫 Contraindications ##
## 🧬 Mechanism of Action ##
## 🧪 Chemical Information ##
## 📚 Sources ##
```

### 3. backend/config/prompts/differential_diagnosis.json
- Version: 4.1.0 → **4.2.0**
- Added "Markdown in JSON Strings" section
- Specified closed heading format for any markdown within JSON values

**Changes:**
```json
"Markdown in JSON Strings

If you include markdown headings in JSON string values:

- Use CLOSED HEADING format: ## Heading ## (not just ## Heading)
- This ensures proper rendering in the frontend
- Example: ## Clinical Assessment ## or ### Subsection ###"
```

---

## Why Closed Headings Work Better

### 1. **Explicit Boundaries**
The closing `##` explicitly marks where the heading ends, preventing the AI from accidentally continuing text on the same line.

### 2. **Valid Markdown Syntax**
Both syntaxes are valid in ATX-style markdown:
- `## Heading` (open style)
- `## Heading ##` (closed style)

### 3. **Better Parsing**
Markdown parsers like `marked.js` handle both formats correctly, but closed headings are more explicit and less ambiguous.

### 4. **Consistent AI Output**
AI models are more likely to respect the heading format when it's explicitly closed, leading to more consistent output formatting.

---

## Frontend Compatibility

### marked.js Renderer

The frontend uses `marked.js` for markdown rendering. The custom heading renderer in `frontend/script.js` (lines 904-958) receives the `text` parameter which has already been parsed by `marked.js`.

**The parser automatically strips the closing `##` symbols**, so the renderer receives clean heading text:
- Input: `## Clinical Assessment ##`
- Parsed text parameter: `Clinical Assessment`
- Output: `<h2>🏥 Clinical Assessment</h2>`

✅ **No changes needed in frontend code** - the renderer already handles both formats correctly.

---

## Format Rules Summary

All prompts now enforce these rules:

### Heading Format
- **Main headings:** `## Heading ##`
- **Subheadings:** `### Subheading ###`
- **Always close with same number of #**

### Spacing Rules
- ONE blank line before each heading
- ONE blank line after each heading
- ONE blank line before each list
- ONE blank line after each list
- Each list item on its own line

### Example Format
```markdown
Previous content here.

## Main Section ##

Content paragraph here.

### Subsection ###

More content here.

- List item 1
- List item 2

## Next Section ##

More content.
```

---

## Testing

### Test Closed Heading Format

1. Start backend server:
```bash
cd backend
python -m uvicorn healthnavi.main:app --host 0.0.0.0 --port 8050 --reload
```

2. Send test query and check console for:
```
🎯 Using prompt: clinical_guidance
✅ Loaded prompt [clinical_guidance] v2.4.0
```

3. Verify AI response uses closed headings:
```markdown
## 🏥 Clinical Assessment ##

Patient presents with...

## ⚕️ Recommended Approach ##

First-line treatment...
```

---

## Benefits

✅ **Explicit formatting** - Clear boundaries for headings

✅ **Consistent output** - AI models follow format more reliably

✅ **Proper rendering** - No text accidentally merged with headings

✅ **Better parsing** - Less ambiguity in markdown structure

✅ **Future-proof** - Works with any markdown parser

---

## Rollback Instructions

If issues occur, revert to previous versions:

```bash
cd backend/config/prompts
git restore clinical_guidance.json drug_information.json differential_diagnosis.json
```

Or manually change version numbers back to:
- `clinical_guidance.json`: `"version": "2.3.0"`
- `drug_information.json`: `"version": "2.3.0"`
- `differential_diagnosis.json`: `"version": "4.1.0"`

And remove closed heading instructions from the templates.

---

## Related Files

- `backend/config/prompts/clinical_guidance.json` - Clinical guidance prompts
- `backend/config/prompts/drug_information.json` - Drug information prompts
- `backend/config/prompts/differential_diagnosis.json` - Differential diagnosis prompts
- `frontend/script.js` (lines 904-958) - Heading renderer
- `PROMPT_CONSISTENCY_UPDATE.md` - Previous formatting update

---

> **Status:** ✅ Complete - All prompts now use closed heading format (`## Heading ##`)

