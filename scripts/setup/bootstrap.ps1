# Однократная настройка окружения разработки PriceScope (Windows/PowerShell)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Создан .env — при необходимости отредактируйте координаты/пути."
}
Write-Host "Готово: pricescope --version"
