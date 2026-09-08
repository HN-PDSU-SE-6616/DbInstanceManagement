# 承载 和 压测
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "启动 waitress 多线程服务 (127.0.0.1:8000, threads=8)..."
Start-Process powershell -ArgumentList '-NoExit','-NoProfile','-Command',
    "Set-Location '$root'; uv run waitress-serve --listen=127.0.0.1:8000 --threads=8 dbinstancemanagement.wsgi:application"

Start-Sleep -Seconds 3
Write-Host "启动 locust Web UI: http://127.0.0.1:8089"
uv run locust -f locustfile.py --host http://127.0.0.1:8000 --web-port 8089
