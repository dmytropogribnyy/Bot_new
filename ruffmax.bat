@echo off
REM Ruff Maximum Fix - простая команда для полного исправления

echo [RUFF MAX FIX]
echo ==============

echo Step 1: Format code...
ruff format . --quiet

echo Step 2: Fix all issues...
ruff check . --fix --quiet

echo Step 3: Fix unsafe issues...
ruff check . --fix --unsafe-fixes --quiet

echo.
echo Final check:
ruff check . --statistics

echo.
echo Done! Use 'ruffmax' anytime to fix all issues.
