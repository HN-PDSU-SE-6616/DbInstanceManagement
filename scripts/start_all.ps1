$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

Write-Host "Syncing dependencies (uv sync)..."
uv sync

Write-Host "Starting Celery Worker..."
Start-Process powershell -ArgumentList '-NoExit','-NoProfile','-Command',
    "Set-Location '$root'; uv run celery -A dbinstancemanagement worker -l info -P threads --logfile='logs/celery-worker.log'"

Start-Sleep -Seconds 2
Write-Host "Starting Celery Beat..."
Start-Process powershell -ArgumentList '-NoExit','-NoProfile','-Command',
    "Set-Location '$root'; uv run celery -A dbinstancemanagement beat -l info --logfile='logs/celery-beat.log'"

Start-Sleep -Seconds 2
Write-Host "Starting Flower (http://127.0.0.1:5555)..."
Start-Process powershell -ArgumentList '-NoExit','-NoProfile','-Command',
    "Set-Location '$root'; uv run celery -A dbinstancemanagement flower --port=5555"

Write-Host "Starting Django dev server (http://127.0.0.1:8000)..."
uv run python manage.py runserver 127.0.0.1:8000