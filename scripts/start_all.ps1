# Celery 可视化与一键启动脚本
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

Write-Host "启动 Celery Worker..."
Start-Process powershell -ArgumentList '-NoExit','-NoProfile','-Command',
    "Set-Location '$root'; uv run celery -A dbinstancemanagement worker -l info -P threads --logfile='logs/celery-worker.log'"

Start-Sleep -Seconds 2
Write-Host "启动 Celery Beat..."
Start-Process powershell -ArgumentList '-NoExit','-NoProfile','-Command',
    "Set-Location '$root'; uv run celery -A dbinstancemanagement beat -l info --logfile='logs/celery-beat.log'"

Start-Sleep -Seconds 2
Write-Host "启动 Flower (http://127.0.0.1:5555)..."
Start-Process powershell -ArgumentList '-NoExit','-NoProfile','-Command',
    "Set-Location '$root'; uv run flower --broker=redis://localhost:6379/0 --result-backend=redis://localhost:6379/1 --port=5555"

Write-Host "启动 Django dev server..."
uv run python manage.py runserver 0.0.0.0:8000
