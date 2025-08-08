#!/bin/bash
# Ruff команды для BinanceBot_V2
# Использование: source scripts/ruff_commands.sh

# Алиасы для Ruff команд
alias ruff-check="./venv/Scripts/ruff check . --ignore UP035,UP006,F401,F841,I001"
alias ruff-fix="./venv/Scripts/ruff check . --fix --ignore UP035,UP006,F401,F841,I001"
alias ruff-format="./venv/Scripts/ruff format ."
alias ruff-full="./venv/Scripts/ruff check . --fix --ignore UP035,UP006,F401,F841,I001 && ./venv/Scripts/ruff format ."

# Функции для удобства
ruff_check() {
    echo "🔍 Running Ruff check..."
    ./venv/Scripts/ruff check . --ignore UP035,UP006,F401,F841,I001
}

ruff_fix() {
    echo "🔧 Running Ruff fix..."
    ./venv/Scripts/ruff check . --fix --ignore UP035,UP006,F401,F841,I001
}

ruff_format() {
    echo "📝 Running Ruff format..."
    ./venv/Scripts/ruff format .
}

ruff_full() {
    echo "🚀 Running full Ruff check, fix and format..."
    ./venv/Scripts/ruff check . --fix --ignore UP035,UP006,F401,F841,I001
    ./venv/Scripts/ruff format .
    echo "✅ Ruff full check completed!"
}

# Выводим доступные команды
echo "🐍 Ruff commands loaded for BinanceBot_V2:"
echo "  ruff_check    - Check code for issues"
echo "  ruff_fix      - Fix auto-fixable issues"
echo "  ruff_format   - Format code"
echo "  ruff_full     - Full check, fix and format"
echo "  ruff-check    - Alias for check"
echo "  ruff-fix      - Alias for fix"
echo "  ruff-format   - Alias for format"
echo "  ruff-full     - Alias for full"
