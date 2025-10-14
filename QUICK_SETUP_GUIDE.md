# Quick Setup Guide - Fix Login Error

## Issue

Getting "Failed to fetch" error when trying to login.

---

## Root Cause

1. Backend `.env` file missing
2. Frontend `auth.js` had wrong API URL (✅ **FIXED**)

---

## Solution

### Step 1: Create Backend .env File

From project root, run in PowerShell:

```powershell
@"
# Application Settings
ENV=development
DEBUG=true

# Security Keys
SECRET_KEY=dev-secret-key-for-development-only-min-32-characters-long-12345
ENCRYPTION_KEY=dev-encryption-key-for-development-only-32-characters-long

# Database (SQLite for development)
DB_USER=dev
DB_PASSWORD=devpassword123456
DB_HOST=localhost
DB_PORT=5432
DB_NAME=healthnavi_cdss
DATABASE_URL=sqlite:///./test_database.db

# API Settings
API_HOST=0.0.0.0
API_PORT=8050
API_ROOT_PATH=/api/v2

# JWT Settings
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Password Settings
MIN_PASSWORD_LENGTH=12
MAX_PASSWORD_LENGTH=128

# Email (Optional - not required for login)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@healthnavi.ai
FROM_NAME=HealthNavi AI CDSS
BASE_URL=http://localhost:8050
"@ | Set-Content backend\.env
```

---

### Step 2: Install Backend Dependencies

```powershell
cd backend
pip install -r requirements.txt
```

---

### Step 3: Start Backend Server

```powershell
cd backend
python -m uvicorn healthnavi.main:app --host 0.0.0.0 --port 8050 --reload
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8050 (Press CTRL+C to quit)
INFO:     Started reloader process
```

---

### Step 4: Test Backend Health

Open new PowerShell window:

```powershell
Invoke-WebRequest -Uri http://localhost:8050/api/v2/health -UseBasicParsing
```

Should return:
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "2.0.0"
  }
}
```

---

### Step 5: Open Frontend

Open `frontend/auth.html` in your browser or use Live Server.

---

### Step 6: Register Account

1. Click "Sign Up" tab
2. Fill in:
   - First Name
   - Last Name  
   - Email
   - Password (min 12 characters)
3. Click "Create Account"

---

### Step 7: Verify Email (Development Only)

Since email isn't configured, manually verify:

```powershell
# Replace test@example.com with your email
Invoke-WebRequest -Uri "http://localhost:8050/api/v2/auth/manual-verify?email=test@example.com" -Method POST
```

Should return:
```json
{
  "success": true,
  "data": {
    "message": "Email test@example.com manually verified for development"
  }
}
```

---

### Step 8: Login

1. Go back to auth page
2. Click "Sign In" tab
3. Enter email and password
4. Click "Sign In"

✅ **Success!** You should be redirected to the main application.

---

## Changes Made

### ✅ Fixed Files

1. **frontend/auth.js** (Line 4)
   - Changed: `this.API_URL = '/api'`
   - To: `this.API_URL = 'http://localhost:8050/api/v2'`

2. **backend/.env** (Created)
   - Added all required environment variables
   - Configured for development with SQLite

3. **All Prompts** (Updated)
   - Added concise Markdown formatting rules
   - Optimized for token efficiency

---

## Troubleshooting

### Backend Won't Start

**Error: "ModuleNotFoundError: No module named 'healthnavi'"**

Solution:
```powershell
cd backend
pip install -e .
```

---

### Backend Configuration Error

**Error: "Configuration validation failed"**

Check `.env` file has:
- SECRET_KEY (min 32 characters)
- ENCRYPTION_KEY (min 32 characters)
- DB_PASSWORD (min 8 characters)

---

### Login Still Fails

1. **Check backend is running:**
   ```powershell
   netstat -ano | findstr :8050
   ```

2. **Check backend logs** for errors

3. **Open browser console** (F12) to see frontend errors

4. **Verify API URL:**
   - Open `frontend/auth.js`
   - Line 4 should be: `this.API_URL = 'http://localhost:8050/api/v2'`

---

### Email Not Verified

Use manual verification endpoint:
```powershell
Invoke-WebRequest -Uri "http://localhost:8050/api/v2/auth/manual-verify?email=YOUR_EMAIL" -Method POST
```

---

## Production Deployment

For production, update `.env`:

1. Generate secure keys:
   ```python
   import secrets
   print(secrets.token_urlsafe(32))  # SECRET_KEY
   print(secrets.token_urlsafe(32))  # ENCRYPTION_KEY
   ```

2. Use PostgreSQL instead of SQLite

3. Configure SMTP for email verification

4. Update CORS settings in `backend/src/healthnavi/main.py`

5. Change `DEBUG=false`

---

## Next Steps

- ✅ Backend running on port 8050
- ✅ Frontend auth.js updated
- ✅ Prompts optimized for concise output
- ✅ Markdown renderer configured
- 📝 Test login functionality
- 📝 Configure email service (optional)
- 📝 Deploy to production (when ready)

---

> **Support:** For issues, check logs in `backend/logs/` or console output.

