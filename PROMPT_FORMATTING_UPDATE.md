# Prompt Formatting Update - Concise Markdown Rules

## Overview

Updated all AI prompts to enforce concise, token-efficient Markdown formatting for optimal readability and minimal token usage.

---

## Changes Made

### Updated Files

1. **backend/config/prompts/clinical_guidance.json**
2. **backend/config/prompts/differential_diagnosis.json**
3. **backend/config/prompts/drug_information.json**

---

## New Formatting Rules

### Concise Markdown Format

- Use `#`, `##`, `###` for headings and subheadings
- Separate paragraphs with **ONE** blank line only
- Use short, clear sentences and compact paragraphs
- Use `-` for bullets or `1.` for numbered points, keeping items single-line
- Highlight key terms with **bold**, *italics*, or `code` for commands/variables
- Use fenced code blocks (```) only when needed
- Use Markdown tables for structured comparisons
- Include links as `[text](url)`
- Use `>` for notes, tips, or warnings
- Insert `---` to separate major sections
- Keep outputs clean, direct, free from filler text

### Spacing Rules

- **ONE** blank line before and after each `##` heading
- **ONE** blank line before and after each `###` subheading  
- **ONE** blank line before and after each list (numbered or bullet)
- Each list item on its **OWN** separate line
- **NEVER** run headings, paragraphs, and lists together on the same line

---

## Benefits

✅ **Token Efficiency** - Reduced token usage per response

✅ **Readability** - Clean, scannable format for healthcare professionals

✅ **Consistency** - Standardized output across all query types

✅ **Rendering** - Optimized for frontend markdown parser

---

## Frontend Compatibility

The frontend `script.js` already includes:

- `fixMarkdownSpacing()` - Auto-fixes spacing issues
- `renderMarkdownWithEnhancements()` - Renders with marked.js + DOMPurify
- Support for headings, lists, tables, code blocks, blockquotes
- Medical-specific icons and styling

---

## Testing

To test the updated prompts:

1. Start backend server
2. Send clinical query
3. Verify response follows concise format
4. Check proper spacing and readability

---

## Query Types Affected

### Clinical Guidance
- Evidence-based clinical recommendations
- Treatment protocols
- Monitoring and follow-up

### Differential Diagnosis  
- JSON-structured clinical assessments
- Probability percentages
- Critical safety alerts

### Drug Information
- Pharmacology data
- Side effects by frequency
- Drug interactions and contraindications

---

## Version History

- **v2.2.0** (Clinical Guidance) - Added concise formatting rules
- **v4.1.0** (Differential Diagnosis) - Added JSON string formatting rules
- **v2.2.0** (Drug Information) - Added concise formatting rules

---

> **Note:** All prompts maintain strict evidence-based guidelines and source citation requirements.

