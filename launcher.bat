@echo off
set REGISTRY=%REGISTRY%

echo Starting Preciso on-prem stack...
if not "%REGISTRY%"=="" (
  echo Checking for updates from %REGISTRY%...
  docker pull %REGISTRY%/preciso-frontend:latest
  docker pull %REGISTRY%/preciso-backend:latest
  docker pull %REGISTRY%/preciso-worker:latest
)

docker compose -f docker-compose.onprem.yml up -d

timeout /t 5 /nobreak > nul
curl -fsS http://localhost:3000/health > nul
if %errorlevel% == 0 (
  echo Preciso is running on http://localhost:3000
) else (
  echo Startup check failed. Use: docker compose -f docker-compose.onprem.yml logs
  exit /b 1
)
