# 502 Bad Gateway Fix - Applied Changes

## Problem
Production was timing out on AI diagnosis requests with 502 Bad Gateway errors after ~60 seconds, while local development worked fine.

## Root Cause
**Local** uses Vite dev server (no timeout limits) → Backend  
**Production** uses nginx → Docker container → Backend (60s default timeout)

## Fixes Applied

### 1. Frontend nginx Timeout Configuration
**File**: `frontend/nginx.conf`
- Added `proxy_connect_timeout 180s`
- Added `proxy_send_timeout 180s`
- Added `proxy_read_timeout 180s`
- Added buffer settings for large responses

### 2. Backend Uvicorn Timeout  
**File**: `docker-compose.yml`
- Added `--timeout-keep-alive 180` to uvicorn command

### 3. Frontend Query Retry Fix
**File**: `frontend/src/main.tsx`
- Disabled React Query mutation retries (was causing duplicate requests on failure)
- Changed `retry: 1` to `retry: false` for mutations

## Deployment Steps

### Step 1: Commit and Push Changes
```bash
cd /Users/richkitibwa/Documents/mamaope/healthnavy_v2
git add frontend/nginx.conf docker-compose.yml frontend/src/main.tsx
git commit -m "fix: Add 180s timeout configurations for AI requests"
git push origin develop
```

### Step 2: Deploy to Production Server

SSH into your EC2 instance:
```bash
ssh -i ~/.ssh/mamaopeai.pem ubuntu@<YOUR_EC2_IP>
```

On the server, run:
```bash
# Navigate to project directory
cd /path/to/healthnavy_v2

# Pull latest changes
git pull origin develop

# Rebuild containers with new configs
docker-compose down
docker-compose build --no-cache frontend api
docker-compose up -d

# Check logs
docker-compose logs -f api
```

### Step 3: Check If EC2 Has Additional Nginx

If you have nginx running on the EC2 host (outside Docker), you'll also need to update it:

```bash
# Check if nginx is running on host
sudo systemctl status nginx

# If running, edit the config
sudo nano /etc/nginx/sites-available/healthnavi

# Add these lines inside the location block that proxies to Docker:
#   proxy_connect_timeout 180s;
#   proxy_send_timeout 180s;
#   proxy_read_timeout 180s;

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

## Verification

After deployment, test the diagnosis endpoint:
```bash
curl -X POST https://healthnavi.mamaope.com/api/v2/diagnosis/diagnose \
  -H "Content-Type: application/json" \
  -d '{"patient_data": "What are the treatment options for severe malnutrition in children under 5?", "chat_history": ""}' \
  --max-time 180 \
  -v
```

Response should return successfully within 60-120 seconds without 502 errors.

## Files Modified
1. `frontend/nginx.conf` - Added timeout settings
2. `docker-compose.yml` - Added uvicorn timeout flag  
3. `frontend/src/main.tsx` - Disabled mutation retries
4. `deploy-production.sh` - Created deployment helper script

## Why Local Worked
Vite's dev server proxy has no default timeout limits, so it waits indefinitely for the backend response. Production nginx had the standard 60-second timeout.

