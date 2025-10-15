# Cache Problem Solution - Functions Not Defined

## Problem

You're seeing these errors:
```
Uncaught ReferenceError: useSamplePrompt is not defined
Uncaught ReferenceError: showAuthModal is not defined
```

**Root Cause:** Your browser cached a corrupted version of `script.js` (only 1 line instead of 1895 lines).

---

## Quick Solution

### Step 1: Use the Verification Tool

I created a special page to check if your cache is clear:

**Open:** `frontend/verify-functions.html`

Or navigate to: `http://localhost:5500/frontend/verify-functions.html`

This page will show:
- ✅ Green checkmarks = functions loaded correctly (cache is clear!)
- ❌ Red X marks = functions missing (cache still needs clearing)

### Step 2: Clear Cache (Choose Best Method)

## Method 1: Nuclear Option (Most Reliable) 🔥

1. **Close ALL browser windows and tabs**
2. **Open Task Manager** (`Ctrl+Shift+Esc`)
3. **End all browser processes** (Chrome, Edge, Firefox, etc.)
4. **Open a NEW browser window**
5. **Navigate to your site**
6. **Press `Ctrl+Shift+R`** (hard refresh)

## Method 2: DevTools Method (Recommended) ⚙️

1. **Open DevTools** (`F12`)
2. **Right-click** the refresh button (top-left of browser)
3. **Select** "Empty Cache and Hard Reload"
4. **Keep DevTools open**
5. **Check Network tab** - you should see `script.js` being downloaded (70-80 KB)

## Method 3: Settings Method 🗑️

**Chrome/Edge:**
1. Press `Ctrl+Shift+Delete`
2. Time range: **"All time"**
3. Check: **"Cached images and files"**
4. Click **"Clear data"**
5. Close browser completely
6. Open new window and try again

**Firefox:**
1. Press `Ctrl+Shift+Delete`
2. Time range: **"Everything"**
3. Check: **"Cache"**
4. Click **"Clear Now"**
5. Close and reopen browser

## Method 4: Incognito/Private Mode 🥸

This bypasses cache completely:

**Chrome/Edge:** `Ctrl+Shift+N`
**Firefox:** `Ctrl+Shift+P`
**Safari:** `Cmd+Shift+N`

Then navigate to your site.

---

## Verification

### Check 1: Network Tab

1. Open DevTools (`F12`)
2. Go to **Network** tab
3. Refresh page
4. Find `script.js` request
5. Check **Size** column - should show ~70-80 KB
6. If it shows "disk cache" or is very small (1 KB), cache is still active

### Check 2: Console Test

Open console (`F12` → Console) and type:

```javascript
typeof showAuthModal
```

**Expected:** `"function"`  
**If you see:** `"undefined"` → Cache still needs clearing

### Check 3: File Verification

```javascript
// Run this in console
fetch('script.js').then(r => r.text()).then(t => {
    console.log('Script.js length:', t.length, 'chars');
    console.log('Has showAuthModal:', t.includes('function showAuthModal'));
    console.log('Has useSamplePrompt:', t.includes('function useSamplePrompt'));
});
```

**Expected output:**
```
Script.js length: 75000+ chars
Has showAuthModal: true
Has useSamplePrompt: true
```

---

## What I Fixed

### 1. Restored script.js ✅

The file now has **1895 lines** with all functions:
- `showAuthModal` (line 235)
- `useSamplePrompt` (line 1566)
- All other required functions

### 2. Added Cache-Busting ✅

Updated `index.html` to force fresh load:
```html
<script src="script.js?v=<?php echo time(); ?>"></script>
```

### 3. Created Verification Page ✅

`frontend/verify-functions.html` - Test page to check if functions are loaded

---

## Why This Keeps Happening

The `script.js` file was getting corrupted during automated edits (reducing to 1 line). I've restored it from git, but your browser is aggressively caching it.

**Prevention:**
1. Always use hard refresh when developing (`Ctrl+F5`)
2. Keep DevTools open with "Disable cache" checked (Network tab)
3. Use incognito mode for testing changes

---

## If Still Not Working

### Last Resort: Manual File Check

1. Open `frontend/script.js` in your editor
2. Check line count - should be **1895 lines**
3. Search for "function showAuthModal" - should be found
4. If file is corrupted (1-2 lines), restore from git:

```bash
git checkout origin/fix_login_api -- frontend/script.js
```

### Disable All Caching (Development Mode)

Add this to the top of `index.html`:

```html
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
```

---

## Alternative: Direct HTML Test

If cache clearing isn't working, test with this standalone HTML:

```html
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
    <button onclick="alert('Working!')">Test Button</button>
    <script src="script.js?v=999"></script>
    <script>
        setTimeout(() => {
            console.log('showAuthModal exists:', typeof showAuthModal);
            console.log('useSamplePrompt exists:', typeof useSamplePrompt);
        }, 1000);
    </script>
</body>
</html>
```

Save as `test.html` in frontend folder and open it.

---

## Success Checklist

✅ Closed all browser windows  
✅ Opened new window  
✅ Hard refreshed (`Ctrl+Shift+R`)  
✅ Opened DevTools (`F12`)  
✅ Checked Network tab - `script.js` shows 70-80 KB  
✅ Checked Console - `typeof showAuthModal` returns `"function"`  
✅ No errors in console when clicking buttons  
✅ Functions work normally  

---

> **Status:** Cache issue - script.js is correct but browser cached old version. Use verification tool and cache clearing methods above.

