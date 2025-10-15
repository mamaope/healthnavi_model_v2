# Cache Fix Instructions - Functions Not Defined Error

## Problem

You're seeing these errors in the browser console:
```
Uncaught ReferenceError: useSamplePrompt is not defined
Uncaught ReferenceError: showAuthModal is not defined
```

This means your browser cached a corrupted version of `script.js`.

---

## Quick Fix (Choose One Method)

### Method 1: Hard Refresh (FASTEST) ⚡

**Windows/Linux:**
1. Press `Ctrl + F5`
2. Or `Ctrl + Shift + R`

**Mac:**
1. Press `Cmd + Shift + R`

**This forces the browser to reload everything from scratch, bypassing cache.**

---

### Method 2: Clear Browser Cache

**Chrome/Edge:**
1. Press `Ctrl + Shift + Delete` (Windows) or `Cmd + Shift + Delete` (Mac)
2. Select **"Cached images and files"**
3. Select **"Last hour"** or **"All time"**
4. Click **"Clear data"**

**Firefox:**
1. Press `Ctrl + Shift + Delete` (Windows) or `Cmd + Shift + Delete` (Mac)
2. Select **"Cache"**
3. Click **"Clear Now"**

**Safari:**
1. Go to Safari menu → Preferences → Advanced
2. Enable "Show Develop menu in menu bar"
3. Develop menu → Empty Caches
4. Or `Cmd + Option + E`

---

### Method 3: Open in Incognito/Private Window

**Chrome/Edge:**
- `Ctrl + Shift + N` (Windows) or `Cmd + Shift + N` (Mac)

**Firefox:**
- `Ctrl + Shift + P` (Windows) or `Cmd + Shift + P` (Mac)

**Safari:**
- `Cmd + Shift + N`

Then navigate to your site. Private mode doesn't use cache.

---

### Method 4: Disable Cache in DevTools

1. Open DevTools (`F12`)
2. Go to **Network tab**
3. Check **"Disable cache"** checkbox
4. Keep DevTools open
5. Refresh the page (`F5`)

---

## Verification

After clearing cache, open the browser console (`F12`) and type:

```javascript
typeof useSamplePrompt
```

**Should show:** `"function"`

If it shows `"undefined"`, the cache is still old. Try Method 1 or 2 again.

---

## What I Fixed

1. ✅ **Restored script.js** - File now has 1895 lines with all functions
2. ✅ **Added cache-busting** - `index.html` now loads `script.js?v=20241014-fix`
3. ✅ **Verified functions exist**:
   - `showAuthModal` at line 235
   - `useSamplePrompt` at line 1566

---

## Manual Verification

If you want to double-check the file is correct:

```bash
# Check file size
cd frontend
ls -lh script.js

# Should show ~70-80 KB

# Check line count  
wc -l script.js
# Should show: 1895 lines

# Check functions exist
grep -n "function showAuthModal" script.js
grep -n "function useSamplePrompt" script.js
```

---

## Test After Fix

1. Clear cache using **Method 1** (hard refresh)
2. Open DevTools Console (`F12`)
3. You should see:
   ```
   🚀 HealthNavi AI initialized
   📝 [Markdown] marked.js version: ...
   ✅ Functions loaded successfully
   ```
4. Click "Log In" button - should work
5. Click sample prompt buttons - should work

---

## If Still Not Working

If after clearing cache you still see errors:

### Quick JavaScript Patch

Open browser console (`F12`) and paste this:

```javascript
// Temporary fix - defines functions globally if missing
if (typeof showAuthModal === 'undefined') {
    window.showAuthModal = function(mode) {
        console.log('Auth modal:', mode);
        alert('Please refresh the page with Ctrl+F5 to clear cache');
    };
}

if (typeof useSamplePrompt === 'undefined') {
    window.useSamplePrompt = function(type) {
        console.log('Sample prompt:', type);
        alert('Please refresh the page with Ctrl+F5 to clear cache');
    };
}

console.log('✅ Temporary functions loaded - now do a hard refresh (Ctrl+F5)');
```

This creates temporary functions that tell you to refresh. Then do a **hard refresh** (`Ctrl + F5`).

---

## Root Cause

The `script.js` file was getting corrupted during automated edits (reducing to 1 line). I've restored it from the git repository. The cache issue prevents the fixed version from loading.

---

## Prevention

To prevent this in the future:

1. **Always use hard refresh** when developing: `Ctrl + F5`
2. **Keep DevTools open** with "Disable cache" checked
3. **Use incognito mode** for testing changes
4. **Check file size** before refreshing if you suspect corruption

---

> **Status:** ✅ Fixed - `script.js` restored with all functions. Just need to clear browser cache!

