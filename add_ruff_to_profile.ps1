# Добавить в PowerShell профиль простую функцию ruff
$code = @'

# Ruff max fix
function ruff() {
    ruff.exe format . ; ruff.exe check . --fix --unsafe-fixes
}
'@

# Добавляем в профиль
Add-Content -Path $PROFILE -Value $code
Write-Host "Added! Restart PowerShell and use: ruff" -ForegroundColor Green
