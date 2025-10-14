# .env File Encoding Fix

## Issue

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte
```

When running Alembic migrations or any Python script that reads the `.env` file.

---

## Root Cause

The `backend/.env` file was saved with **UTF-16 LE encoding** with BOM (Byte Order Mark: `FF FE`).

Python's `dotenv` library expects **UTF-8 encoding without BOM**.

---

## Detection

Check file encoding:
```powershell
Get-Content backend\.env -Raw -Encoding Byte | Select-Object -First 10 | Format-Hex
```

**Bad encoding (UTF-16 LE):**
```
00000000   FF FE 23 00 20 00 48 00 65 00 61 00 6C 00 74 00  ._#. .H.e.a.l.t.
```
Starts with `FF FE` (UTF-16 LE BOM)

**Good encoding (UTF-8 no BOM):**
```
00000000   23 20 48 65 61 6C 74 68 4E 61 76 69 20 41 49 20  # HealthNavi AI 
```
Starts with `23 20` (`# ` text)

---

## Fix Applied

✅ Converted `backend/.env` from UTF-16 LE to UTF-8 without BOM

```powershell
$content = Get-Content backend\.env -Raw -Encoding UTF8
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText("$PWD\backend\.env", $content, $utf8NoBom)
```

---

## Verification

Run this to verify encoding:
```powershell
Get-Content backend\.env -Raw -Encoding Byte | Select-Object -First 4 | Format-Hex
```

Should show:
```
00000000   23 20 48 65  # He
```

**NOT:**
```
00000000   FF FE ...    (UTF-16)
00000000   EF BB BF ... (UTF-8 with BOM)
```

---

## Prevention

When creating or editing `.env` files:

### VS Code
1. Open file
2. Bottom right → Click encoding (e.g., "UTF-16 LE")
3. Select "Save with Encoding"
4. Choose **"UTF-8"** (not "UTF-8 with BOM")

### Notepad++
1. Open file
2. **Encoding** menu → **Convert to UTF-8** (not "UTF-8-BOM")
3. Save

### PowerShell
```powershell
# Always use UTF8Encoding without BOM
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText("path\to\.env", $content, $utf8)
```

---

## Test Fix

Now Alembic should work:

```bash
cd backend
alembic upgrade head
```

Should no longer show encoding error.

---

## Why This Happened

When you copy-pasted the `.env` content using PowerShell's `Set-Content` with `-Force`, it likely defaulted to UTF-16 encoding on Windows.

**Solution:** Always specify encoding when creating config files:
```powershell
$content | Set-Content file.txt -Encoding UTF8
```

---

## Status

✅ **Fixed** - `.env` file now UTF-8 without BOM

✅ **Ready** - Alembic migrations should now work

✅ **Backend** - Can now start properly

---

> **Note:** This same issue can affect other config files. Always use UTF-8 without BOM for Python projects.

