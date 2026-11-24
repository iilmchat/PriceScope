# Проверка относительных ссылок Markdown (RULES § 2.12)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$docs = Join-Path $root 'docs'
$errors = 0

Get-ChildItem -Path $root -Filter *.md -Recurse |
  Where-Object { $_.FullName -notmatch '\\(\.venv|data|datasets|build)\\' } |
  ForEach-Object {
    $file = $_.FullName
    $content = Get-Content $file -Raw -Encoding UTF8
    foreach ($match in [regex]::Matches($content, '\]\(([^)]+)\)')) {
      $link = $match.Groups[1].Value -replace '#.*$',''
      if (-not $link -or $link -match '^(https?://|mailto:)') { continue }
      $target = [System.IO.Path]::GetFullPath((Join-Path (Split-Path $file) $link))
      if (-not (Test-Path $target)) {
        Write-Host "BROKEN: $($_.FullName): $link"
        $errors++
      }
    }
  }

if ($errors -gt 0) { throw "Найдено битых ссылок: $errors" }
Write-Host "Ссылки документации OK"
