# Docker Network Connectivity Fix

## Issue
Docker cannot reach Docker Hub (`auth.docker.io`) to pull images. This is a network/DNS connectivity issue.

## Solutions

### Solution 1: Check Docker Desktop Network Settings

1. Open **Docker Desktop**
2. Go to **Settings** (gear icon)
3. Navigate to **Resources** > **Network**
4. Check if there are any proxy settings that might be blocking
5. Try disabling the proxy temporarily to test

### Solution 2: Restart Docker Desktop

1. Right-click Docker Desktop icon in system tray
2. Select **Quit Docker Desktop**
3. Wait a few seconds
4. Restart Docker Desktop
5. Wait for it to fully start (whale icon stops animating)
6. Try building again

### Solution 3: Check DNS Settings

If you're behind a corporate firewall or VPN:

1. Open **Docker Desktop** > **Settings**
2. Go to **Docker Engine**
3. Add DNS servers to the JSON configuration:
```json
{
  "dns": ["8.8.8.8", "8.8.4.4"]
}
```
4. Click **Apply & Restart**

### Solution 4: Check Internet Connection

1. Verify your internet connection is working
2. Try accessing https://auth.docker.io in a browser
3. If it doesn't load, there might be a firewall blocking Docker Hub

### Solution 5: Use Docker Build with --network=host (Linux/WSL)

If you're using WSL2, try:
```bash
docker build --network=host -t your-image .
```

### Solution 6: Clear Docker Build Cache

Sometimes cached layers can cause issues:
```bash
docker builder prune -a
```

### Solution 7: Check Proxy Settings

If you're using a proxy, make sure Docker Desktop is configured correctly:
1. Docker Desktop > Settings > Resources > Proxies
2. Configure your proxy settings if needed
3. Or disable proxy if not needed

### Solution 8: Restart WSL (if using WSL2)

```powershell
wsl --shutdown
# Then restart Docker Desktop
```

## Quick Test

After applying fixes, test connectivity:
```bash
docker pull hello-world
```

If this works, try building your project again.

