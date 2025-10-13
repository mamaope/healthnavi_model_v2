@echo off
REM HealthNavi AI CDSS - Docker Run Script
REM This script builds and runs the HealthNavi application using Docker Compose

echo.
echo 🏥 HealthNavi AI CDSS - Starting Docker Environment
echo =================================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not installed or not in PATH
    echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

echo ✅ Docker found
echo.

REM Check if Docker Compose is available
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Compose is not available
    echo Please ensure Docker Compose is installed
    pause
    exit /b 1
)

echo ✅ Docker Compose found
echo.

echo 🔧 Building Docker images...
docker-compose build
if %errorlevel% neq 0 (
    echo ❌ Failed to build Docker images
    pause
    exit /b 1
)

echo.
echo 🚀 Starting services...
docker-compose up -d
if %errorlevel% neq 0 (
    echo ❌ Failed to start services
    pause
    exit /b 1
)

echo.
echo ⏳ Waiting for services to be ready...
timeout /t 10 /nobreak >nul

echo.
echo 📊 Service Status:
docker-compose ps

echo.
echo 🌐 Application URLs:
echo    Frontend: http://localhost:3000
echo    API: http://localhost:8050
echo    API Docs: http://localhost:8050/docs
echo    Database: localhost:5432

echo.
echo 📝 Useful Commands:
echo    View logs: docker-compose logs -f
echo    Stop services: docker-compose down
echo    Restart services: docker-compose restart
echo    View API logs: docker-compose logs -f api

echo.
echo ✅ HealthNavi AI CDSS is now running!
echo    Open http://localhost:3000 in your browser to access the application
echo.
pause




