#!/bin/bash
set -e

echo "🚀 Starting HealthNavi Production Deployment..."

# Step 1: Commit and push changes
echo "📝 Committing timeout configuration changes..."
git add frontend/nginx.conf docker-compose.yml frontend/src/main.tsx
git commit -m "fix: Add timeout configurations for long AI requests (180s)" || echo "No changes to commit"
git push origin develop

echo "✅ Code pushed to repository"

# Step 2: SSH into production server and deploy
echo "🔧 You need to SSH into your production server and run:"
echo ""
echo "ssh -i ~/.ssh/mamaopeai.pem ubuntu@<YOUR_EC2_IP>"
echo ""
echo "Then on the server, run:"
echo ""
echo "cd /path/to/healthnavy_v2"
echo "git pull origin develop"
echo "docker-compose down"
echo "docker-compose build --no-cache frontend api"
echo "docker-compose up -d"
echo ""
echo "# Check logs for any errors:"
echo "docker-compose logs -f api"
echo ""
echo "# If you have nginx on the EC2 host (outside Docker), update its config too:"
echo "sudo nano /etc/nginx/sites-available/healthnavi"
echo "# Add to the location block:"
echo "#   proxy_connect_timeout 180s;"
echo "#   proxy_send_timeout 180s;"
echo "#   proxy_read_timeout 180s;"
echo "sudo nginx -t && sudo systemctl reload nginx"

echo ""
echo "📋 Deployment steps prepared!"

