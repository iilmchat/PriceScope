# Локальный запуск: БД -> импорт Ленты -> API + viewer
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root

pricescope init-db
pricescope parse --store lenta --lat 55.3925 --lon 36.7323
pricescope serve --local
