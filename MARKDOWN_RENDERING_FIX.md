# Markdown Rendering Fix - Headings & Lists

## Problem

Some AI responses are still not formatting properly with:
1. **Closed headings** (`## Heading ##`) appearing incorrectly
2. **List items** getting broken apart by excessive blank lines
3. **Lists not rendering** as a single block

---

## Root Causes

### 1. Closed Headings Not Handled
```markdown
## Clinical Assessment ##  ← Closing ## confuses renderer
Content here
```

### 2. Blank Lines Between List Items
```markdown
- Item 1

- Item 2  ← Blank line breaks the list into separate lists
```

Should be:
```markdown
- Item 1
- Item 2  ← No blank line between items
```

---

## Solution

Update the `fixMarkdownSpacing()` function in `frontend/script.js` to:

1. **Strip closing ## from headings** before rendering
2. **Prevent blank lines between consecutive list items**
3. **Keep lists as unified blocks**

---

## Changes Needed

### Change 1: Handle Closed Headings

**Location:** `frontend/script.js` line ~710 (after `let fixed = markdown;`)

**Add this code:**
```javascript
// Handle closed headings: ## Heading ## -> ## Heading
// Remove closing ## or ### from headings (marked.js will parse them anyway)
fixed = fixed.replace(/(#{1,6})\s+(.+?)\s+#{1,6}\s*$/gm, '$1 $2');
console.log('🔧 [Markdown] Removed closing ## from headings');
```

###Change 2: Fix List Spacing (Step 5)

**Location:** `frontend/script.js` line ~803-808

**Replace:**
```javascript
// STEP 5: Add blank lines before numbered lists
fixed = fixed.replace(/([^\n])\n(\d+\.\s)/g, '$1\n\n$2');
// Also ensure blank line before first list item after heading
fixed = fixed.replace(/(##[^\n]+)\n(\d+\.\s)/g, '$1\n\n$2');

// STEP 6: Add blank lines before bullet lists
fixed = fixed.replace(/([^\n])\n([-*]\s)/g, '$1\n\n$2');
```

**With:**
```javascript
// STEP 5: Add blank lines before numbered lists (but NOT between consecutive list items)
// Only add if previous line is NOT a list item
fixed = fixed.replace(/([^\n\d.])\n(\d+\.\s)/g, '$1\n\n$2');
// Also ensure blank line before first list item after heading
fixed = fixed.replace(/(##[^\n]+)\n(\d+\.\s)/g, '$1\n\n$2');

// STEP 6: Add blank lines before bullet lists (but NOT between consecutive list items)
// Only add if previous line is NOT a list item or heading
fixed = fixed.replace(/([^\n\-\*#])\n([-*]\s)/g, '$1\n\n$2');
```

### Change 3: Remove Excess Spacing Between List Items (Step 7)

**Location:** `frontend/script.js` line ~811

**Replace:**
```javascript
// STEP 7: Add blank line after lists (before non-list content)
fixed = fixed.replace(/(\n(?:\d+\.|-|\*)\s[^\n]+)\n([^\n\d\-\*#])/g, '$1\n\n$2');
```

**With:**
```javascript
// STEP 7: Add blank line after lists (before non-list content)
// Match the LAST item in a list followed by non-list content
fixed = fixed.replace(/((?:\d+\.|-|\*)\s[^\n]+)\n+([^#\d\-\*>\s\n])/g, '$1\n\n$2');

// STEP 7b: Remove double newlines BETWEEN consecutive list items (fix over-spacing)
// This ensures list items stay together as one list block
fixed = fixed.replace(/(\n\d+\.\s[^\n]+)\n\n+(\d+\.\s)/g, '$1\n$2');
fixed = fixed.replace(/(\n[-*]\s[^\n]+)\n\n+([-*]\s)/g, '$1\n$2');
```

---

## Complete Fixed Function

Here's the complete updated `fixMarkdownSpacing()` function:

```javascript
function fixMarkdownSpacing(markdown) {
    console.log('🔧 [Markdown] Fixing spacing...');
    console.log('🔍 [Markdown] Input has newlines:', markdown.includes('\n'));
    console.log('🔍 [Markdown] Input has blank lines:', markdown.includes('\n\n'));
    
    let fixed = markdown;
    
    // Handle closed headings: ## Heading ## -> ## Heading
    // Remove closing ## or ### from headings (marked.js will parse them anyway)
    fixed = fixed.replace(/(#{1,6})\s+(.+?)\s+#{1,6}\s*$/gm, '$1 $2');
    console.log('🔧 [Markdown] Removed closing ## from headings');
    
    // STEP 1: If there are NO newlines at all (everything on one line), add newlines before ## headings
    if (!markdown.includes('\n')) {
        console.log('⚠️ [Markdown] Text is all on ONE LINE - adding line breaks');
        
        // ... rest of STEP 1 code stays the same ...
    }
    
    // STEP 2-4: ... (stay the same)
    
    // STEP 5: Add blank lines before numbered lists (but NOT between consecutive list items)
    // Only add if previous line is NOT a list item
    fixed = fixed.replace(/([^\n\d.])\n(\d+\.\s)/g, '$1\n\n$2');
    // Also ensure blank line before first list item after heading
    fixed = fixed.replace(/(##[^\n]+)\n(\d+\.\s)/g, '$1\n\n$2');
    
    // STEP 6: Add blank lines before bullet lists (but NOT between consecutive list items)
    // Only add if previous line is NOT a list item or heading
    fixed = fixed.replace(/([^\n\-\*#])\n([-*]\s)/g, '$1\n\n$2');
    
    // STEP 7: Add blank line after lists (before non-list content)
    // Match the LAST item in a list followed by non-list content
    fixed = fixed.replace(/((?:\d+\.|-|\*)\s[^\n]+)\n+([^#\d\-\*>\s\n])/g, '$1\n\n$2');
    
    // STEP 7b: Remove double newlines BETWEEN consecutive list items (fix over-spacing)
    // This ensures list items stay together as one list block
    fixed = fixed.replace(/(\n\d+\.\s[^\n]+)\n\n+(\d+\.\s)/g, '$1\n$2');
    fixed = fixed.replace(/(\n[-*]\s[^\n]+)\n\n+([-*]\s)/g, '$1\n$2');
    
    // STEP 8-11: ... (stay the same)
    
    return fixed;
}
```

---

## Testing

### Before Fix:
```markdown
## Clinical Assessment ##

Patient presents with fever.

## Differential Diagnoses ##

1. Condition A

2. Condition B  ← Broken into separate lists
```

### After Fix:
```markdown
## Clinical Assessment

Patient presents with fever.

## Differential Diagnoses

1. Condition A
2. Condition B  ← Proper unified list
```

---

## Manual Fix Instructions

Since the file keeps getting corrupted when edited programmatically:

1. Open `frontend/script.js` in your editor
2. Find the `fixMarkdownSpacing()` function (around line 705)
3. Apply the three changes listed above
4. Save the file
5. Refresh your browser (Ctrl+F5 to clear cache)
6. Test with a query that returns lists and headings

---

## Key Points

✅ **Closed headings** (`## Heading ##`) are now stripped to (`## Heading`)

✅ **List items stay together** - no blank lines between consecutive items

✅ **Lists render as one block** instead of broken apart

✅ **Headings render properly** without confusion from closing ##

---

## Alternative: Quick JavaScript Console Fix

If you don't want to edit the file, you can run this in the browser console after the page loads:

```javascript
// Override the fixMarkdownSpacing function with the fixed version
window.fixMarkdownSpacing = function(markdown) {
    let fixed = markdown;
    
    // Handle closed headings
    fixed = fixed.replace(/(#{1,6})\s+(.+?)\s+#{1,6}\s*$/gm, '$1 $2');
    
    // Fix list spacing - remove blank lines between consecutive list items
    fixed = fixed.replace(/(\n\d+\.\s[^\n]+)\n\n+(\d+\.\s)/g, '$1\n$2');
    fixed = fixed.replace(/(\n[-*]\s[^\n]+)\n\n+([-*]\s)/g, '$1\n$2');
    
    return fixed;
};
console.log('✅ Markdown fixer updated!');
```

Then send your query and it should render properly.

---

> **Status:** ⚠️ Manual fix required - `script.js` file keeps getting corrupted during automated edits

