# HealthNavi AI CDSS - Docker Run Script
# This script builds and runs the HealthNavi application using Docker Compose

Write-Host "🏥 HealthNavi AI CDSS - Starting Docker Environment" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green

# Check if Docker is installed
try {
    $dockerVersion = docker --version
    Write-Host "✅ Docker found: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# Check if Docker Compose is available
try {
    $composeVersion = docker-compose --version
    Write-Host "✅ Docker Compose found: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Compose is not available" -ForegroundColor Red
    Write-Host "Please ensure Docker Compose is installed" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "🔧 Building Docker images..." -ForegroundColor Blue
docker-compose build

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to build Docker images" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🚀 Starting services..." -ForegroundColor Blue
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to start services" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "⏳ Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "📊 Service Status:" -ForegroundColor Blue
docker-compose ps

Write-Host ""
Write-Host "🌐 Application URLs:" -ForegroundColor Green
Write-Host "   Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "   API: http://localhost:8050" -ForegroundColor Cyan
Write-Host "   API Docs: http://localhost:8050/docs" -ForegroundColor Cyan
Write-Host "   Database: localhost:5432" -ForegroundColor Cyan

Write-Host ""
Write-Host "📝 Useful Commands:" -ForegroundColor Blue
Write-Host "   View logs: docker-compose logs -f" -ForegroundColor White
Write-Host "   Stop services: docker-compose down" -ForegroundColor White
Write-Host "   Restart services: docker-compose restart" -ForegroundColor White
Write-Host "   View API logs: docker-compose logs -f api" -ForegroundColor White

Write-Host ""
Write-Host "✅ HealthNavi AI CDSS is now running!" -ForegroundColor Green
Write-Host "   Open http://localhost:3000 in your browser to access the application" -ForegroundColor Yellow




