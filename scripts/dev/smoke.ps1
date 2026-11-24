# Smoke-проверка v0.1.0 (см. docs/qa/MANUAL_TESTING_GUIDE.md § 2)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root

ruff check .
mypy packages apps/api
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q -p pytest_asyncio.plugin -m "not live"
pricescope init-db

$job = Start-Job -ScriptBlock { pricescope serve --local }
Start-Sleep -Seconds 3
try {
    $health = Invoke-RestMethod http://127.0.0.1:8775/health
    if ($health.status -ne 'ok') { throw "health: $($health | ConvertTo-Json)" }
    Write-Host "Smoke OK: $($health.version) / $($health.mode)"
} finally {
    Stop-Job $job
    Remove-Job $job
}
