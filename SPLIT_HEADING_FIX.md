# Split Heading Fix - Complete

## Problem

The AI was generating headings split across multiple lines:

```
## 💊
Priority Drugs
```

Instead of:
```
## 💊 Priority Drugs ##
```

This caused headings to not display properly in the frontend.

---

## Solution

Upgraded the `fix_unclosed_headings()` function to handle **TWO cases**:

### Case 1: Unclosed Headings
```
Before: ## Priority Drugs
After:  ## Priority Drugs ##
```

### Case 2: Split Headings (NEW!)
```
Before: ## 💊
        Priority Drugs
After:  ## 💊 Priority Drugs ##
```

---

## Implementation

### Detection Logic

The function now detects split headings by:

1. **Checking if heading line has ONLY emojis/symbols**
   - Uses regex: `not re.search(r'[a-zA-Z0-9]', content)`
   - Matches lines like `## 💊` or `## 💧` but not `## 💊 Drugs`

2. **Checking if next line has the heading text**
   - Ensures next line is not empty
   - Ensures next line is not another heading
   - Grabs the text from next line

3. **Merging the lines**
   - Combines: `level + emoji + text + level`
   - Example: `## 💊 Priority Drugs ##`
   - Skips both original lines (i += 2)

### Code

```python
@staticmethod
def fix_unclosed_headings(response: str) -> str:
    """
    Automatically fix markdown heading issues:
    1. Close unclosed headings: ## Text → ## Text ##
    2. Merge split headings: ## 💊\nText → ## 💊 Text ##
    """
    lines = response.split('\n')
    fixed_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Check if line starts with heading marker
        if stripped.startswith('#'):
            heading_match = re.match(r'^(#{1,6})\s*(.*?)\s*(?:#{1,6})?\s*$', stripped)
            
            if heading_match:
                level = heading_match.group(1)  # # or ## or ###
                content = heading_match.group(2).strip()  # The heading text
                
                # Case 1: Heading has only emoji/symbols, no text
                if content and not re.search(r'[a-zA-Z0-9]', content):
                    # Check if next line has the actual heading text
                    if i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].strip().startswith('#'):
                        next_line = lines[i + 1].strip()
                        # Merge emoji line with text line
                        merged_heading = f"{level} {content} {next_line} {level}"
                        fixed_lines.append(merged_heading)
                        logger.debug(f"Merged split heading: '{stripped}' + '{next_line}' → '{merged_heading}'")
                        i += 2  # Skip both lines
                        continue
                
                # Case 2: Regular heading (with or without emoji, but has text)
                if content:
                    fixed_heading = f"{level} {content} {level}"
                    fixed_lines.append(fixed_heading)
                    if stripped != fixed_heading:
                        logger.debug(f"Fixed heading: '{stripped}' → '{fixed_heading}'")
                else:
                    # Empty heading, keep as is
                    fixed_lines.append(line)
            else:
                # Doesn't match heading pattern, keep as is
                fixed_lines.append(line)
        else:
            # Not a heading line, keep as is
            fixed_lines.append(line)
        
        i += 1
    
    return '\n'.join(fixed_lines)
```

---

## Examples

### Example 1: Split Heading with Emoji

**Input:**
```
## 💊
Priority Drugs

The following drugs are:
```

**Output:**
```
## 💊 Priority Drugs ##

The following drugs are:
```

**Log:**
```
DEBUG: Merged split heading: '## 💊' + 'Priority Drugs' → '## 💊 Priority Drugs ##'
```

---

### Example 2: Split Heading with Multiple Emojis

**Input:**
```
## 💧💉
Intravenous Fluids

Normal saline is:
```

**Output:**
```
## 💧💉 Intravenous Fluids ##

Normal saline is:
```

---

### Example 3: Regular Unclosed Heading (Still Works)

**Input:**
```
## Treatment Options

Step 1: Assessment
```

**Output:**
```
## Treatment Options ##

Step 1: Assessment
```

**Log:**
```
DEBUG: Fixed heading: '## Treatment Options' → '## Treatment Options ##'
```

---

### Example 4: Heading with Emoji and Text (Already Correct Format)

**Input:**
```
## 💊 Drug Overview

Content here
```

**Output:**
```
## 💊 Drug Overview ##

Content here
```

**Log:**
```
DEBUG: Fixed heading: '## 💊 Drug Overview' → '## 💊 Drug Overview ##'
```

---

## Edge Cases Handled

### 1. Empty Next Line
```
Input:
## 💊

Content

Output:
## 💊 ##      ← Closed but no merge (empty line)

Content
```

### 2. Next Line is Another Heading
```
Input:
## 💊
## Another Heading

Output:
## 💊 ##                    ← Not merged (next is heading)
## Another Heading ##
```

### 3. Heading with Only Spaces
```
Input:
##    

Content

Output:
##                ← Kept as is (empty content)

Content
```

---

## Testing

### Manual Testing

Send queries that generate split headings and check backend logs:

```bash
# Check logs for:
DEBUG: Merged split heading: '## 💊' + 'Priority Drugs' → '## 💊 Priority Drugs ##'
INFO: Applied heading closure fix to response
```

### Expected Console Output (Frontend)

```
📝 RAW AI RESPONSE (COMPLETE):
────────────────────────────────────
## 💊 Priority Drugs ##        ← Properly merged!
## 💧 Intravenous Fluids ##    ← Properly merged!
────────────────────────────────────
✂️ [Markdown] Removed closing ## from headings
```

### Visual Verification

All headings should render as proper HTML `<h2>` tags, not plain text.

---

## Benefits

### 1. **Robustness**
- Handles both unclosed AND split headings
- Works with any emoji combination
- No dependency on AI following format rules

### 2. **Automatic**
- Zero manual intervention needed
- Processes every response automatically
- Guarantees consistent output

### 3. **Debuggable**
- Logs every fix with before/after
- Easy to trace issues
- Clear error messages

### 4. **Performance**
- Simple line-by-line processing
- No complex regex backtracking
- Fast even for long responses

---

## Full Processing Pipeline

```
1. AI generates response
   "## 💊\nPriority Drugs"
   
2. Backend detects split heading
   Emoji only: "💊"
   Next line: "Priority Drugs"
   
3. Backend merges and closes
   "## 💊 Priority Drugs ##"
   
4. Backend sanitizes (HTML escape)
   "&lt;preserved&gt;"
   
5. Frontend receives
   "## 💊 Priority Drugs ##"
   
6. Frontend strips closing ##
   "## 💊 Priority Drugs"
   
7. marked.js renders
   <h2>💊 Priority Drugs</h2>
```

---

## Files Modified

| File | Change |
|------|--------|
| `backend/src/healthnavi/services/conversational_service.py` | Upgraded `fix_unclosed_headings()` function |

---

## Rollback

If issues occur, you can revert to the simpler version that only closes headings:

```python
@staticmethod
def fix_unclosed_headings(response: str) -> str:
    """Simple version: only close headings, don't merge."""
    pattern = r'^(#{1,6})\s+(.+?)(?:\s*#{1,6})?\s*$'
    lines = response.split('\n')
    fixed_lines = []
    
    for line in lines:
        if line.strip().startswith('#'):
            match = re.match(pattern, line.strip())
            if match:
                level = match.group(1)
                content = match.group(2).strip()
                fixed_lines.append(f"{level} {content} {level}")
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)
```

---

## Related Files

- `BACKEND_HEADING_FIX_COMPLETE.md` - Original heading fix documentation
- `FORMATTING_RULES_SIMPLIFICATION.md` - Prompt simplification
- `FRONTEND_MARKDOWN_FIX.md` - Frontend preprocessing

---

> **Status:** ✅ Complete - Backend now handles both unclosed headings AND split headings (emoji on one line, text on next line).

