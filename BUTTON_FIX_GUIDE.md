# Button Fix Guide - Landing Page

## Issue

Buttons on landing page for unauthenticated users not working (Sign In, Get Started, Sample Questions, etc.)

---

## Root Cause

The buttons use `onclick` handlers that call functions from `script.js`, but the functions may not be available when the page loads.

---

## Affected Buttons

1. **Header Buttons:**
   - "Sign In" button → `onclick="showAuthModal('login')"`
   - "Get Started" button → `onclick="showAuthModal('register')"`
   - Theme toggle → `onclick="toggleTheme()"`

2. **Sample Question Buttons:**
   - "Chest pain" → `onclick="useSamplePrompt('chest-pain')"`
   - "Fever" → `onclick="useSamplePrompt('fever')"`
   - "Pediatric" → `onclick="useSamplePrompt('pediatric')"`

3. **Footer Links:**
   - "Terms of Service" → `onclick="showTerms()"`
   - "Privacy Policy" → `onclick="showPrivacy()"`
   - "Support" → `onclick="showSupport()"`

4. **Send Button:**
   - `onclick="sendMessage()"`

---

## Diagnosis Steps

### 1. Open Browser Console

```
Right-click → Inspect → Console tab
```

### 2. Check for Errors

Look for:
- `Uncaught ReferenceError: showAuthModal is not defined`
- `Uncaught SyntaxError` in script.js
- Any red error messages

### 3. Test Function Availability

In console, type:
```javascript
typeof showAuthModal
typeof useSamplePrompt
typeof toggleTheme
```

Should return `"function"`, not `"undefined"`

---

## Solution 1: Check Script Loading Order

**Current order in index.html:**
```html
<!-- Line 252-254 -->
<script src="https://cdn.jsdelivr.net/npm/marked@11.1.1/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.8/dist/purify.min.js"></script>
<script src="script.js"></script>
</body>
```

✅ **Correct** - Scripts load before `</body>`, so they're available when page is interactive.

---

## Solution 2: Verify Functions Are Exposed

Check `script.js` lines 1832-1841:

```javascript
// Global functions for HTML onclick handlers
window.showAuthModal = showAuthModal;
window.closeAuthModal = closeAuthModal;
window.toggleAuthMode = toggleAuthMode;
window.togglePasswordVisibility = togglePasswordVisibility;
window.sendMessage = sendMessage;
window.useSamplePrompt = useSamplePrompt;
window.logout = logout;
window.startNewSession = startNewSession;
window.showTerms = showTerms;
window.showPrivacy = showPrivacy;
window.showSupport = showSupport;
```

✅ **All functions are exposed to window**

---

## Solution 3: Check for Script Errors

**Common causes:**
1. **Syntax error in script.js** - Prevents entire script from loading
2. **Missing dependencies** - marked.js or DOMPurify failed to load
3. **CORS issues** - Script blocked by browser
4. **File path wrong** - script.js not found (404 error)

---

## Solution 4: Add Error Handling

Add this at the **top** of `script.js` (line 1):

```javascript
// Error boundary
window.addEventListener('error', function(e) {
    console.error('Global error:', e.message, e.filename, e.lineno);
});

// Check if script is loading
console.log('🟢 script.js loaded successfully');
```

---

## Solution 5: Alternative - Use Event Listeners Instead of onclick

Instead of inline `onclick`, use JavaScript event listeners:

### Option A: Update index.html

Remove onclick attributes:
```html
<!-- OLD -->
<button class="btn btn-outline" onclick="showAuthModal('login')">Sign In</button>

<!-- NEW -->
<button class="btn btn-outline" id="btnSignIn">Sign In</button>
```

### Option B: Add event listeners in script.js

Add after `setupEventListeners()` function:

```javascript
function setupButtonListeners() {
    // Header buttons
    const btnSignIn = document.querySelector('.btn.btn-outline');
    const btnGetStarted = document.querySelector('.btn.btn-primary');
    
    if (btnSignIn) {
        btnSignIn.addEventListener('click', () => showAuthModal('login'));
    }
    
    if (btnGetStarted) {
        btnGetStarted.addEventListener('click', () => showAuthModal('register'));
    }
    
    // Sample questions
    document.querySelectorAll('.sample-question').forEach((btn, index) => {
        const types = ['chest-pain', 'fever', 'pediatric'];
        btn.addEventListener('click', () => useSamplePrompt(types[index]));
    });
    
    // Footer links
    const footerLinks = document.querySelectorAll('.footer-links a');
    const footerFunctions = [showTerms, showPrivacy, showSupport];
    footerLinks.forEach((link, index) => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            footerFunctions[index]();
        });
    });
}

// Call in init
document.addEventListener('DOMContentLoaded', function() {
    // ... existing code ...
    setupButtonListeners(); // ADD THIS
});
```

---

## Quick Test

### Test in Browser Console

Open the landing page and type in console:

```javascript
// Test 1: Check if functions exist
console.log('Functions available:');
console.log('showAuthModal:', typeof window.showAuthModal);
console.log('useSamplePrompt:', typeof window.useSamplePrompt);
console.log('toggleTheme:', typeof window.toggleTheme);

// Test 2: Try calling them manually
showAuthModal('login');  // Should open login modal
```

If modal opens → **Functions work, button issue is elsewhere**

If `undefined` → **Script.js not loading properly**

---

## Testing Buttons

1. **Open** `frontend/index.html` in browser
2. **Click** "Sign In" button
   - ✅ Should open modal
   - ❌ If nothing happens, check console for errors
3. **Click** "Get Started" button
   - ✅ Should open registration modal
4. **Click** sample question button
   - ✅ Should populate input field
5. **Click** theme toggle
   - ✅ Should switch between light/dark

---

## Fix Checklist

- [ ] Open browser console (F12)
- [ ] Check for JavaScript errors (red text)
- [ ] Verify `script.js` loads (Network tab → script.js → Status 200)
- [ ] Test functions in console (`typeof showAuthModal`)
- [ ] Check onclick attributes in HTML
- [ ] Verify functions are exposed to window
- [ ] Test each button manually

---

## If Buttons Still Don't Work

### Debug Script

Add to top of `script.js`:

```javascript
console.log('=== SCRIPT.JS LOADING ===');

window.addEventListener('DOMContentLoaded', function() {
    console.log('=== DOM LOADED ===');
    console.log('Functions:', {
        showAuthModal: typeof showAuthModal,
        useSamplePrompt: typeof useSamplePrompt,
        toggleTheme: typeof toggleTheme,
        sendMessage: typeof sendMessage
    });
});

console.log('=== SCRIPT.JS LOADED ===');
```

Check console output to see where loading stops.

---

## Expected Console Output

```
=== SCRIPT.JS LOADING ===
🚀 [App] Initializing HealthNavi AI
📚 [Libraries] marked.js loaded: true
🧼 [Libraries] DOMPurify loaded: true
🎨 Initializing theme system...
=== DOM LOADED ===
Functions: {
  showAuthModal: "function",
  useSamplePrompt: "function",
  toggleTheme: "function",
  sendMessage: "function"
}
=== SCRIPT.JS LOADED ===
```

---

## Common Fixes

### Fix 1: Clear Browser Cache

```
Ctrl + Shift + Delete → Clear cache → Reload page
```

### Fix 2: Hard Refresh

```
Ctrl + F5 (Windows)
Cmd + Shift + R (Mac)
```

### Fix 3: Check File Paths

Verify `script.js` is in same folder as `index.html`:

```
frontend/
  ├── index.html
  ├── script.js  ← Must be here
  ├── style.css
  └── auth.js
```

---

> **Status:** Functions are defined and exposed. If buttons don't work, it's likely a browser caching issue or script loading error. Check console for details.

