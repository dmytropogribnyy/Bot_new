# Ruff: lint + fix + format
alias ruff='ruff check . --fix && ruff format .'
# Pyright type-checking
alias pycheck='pyright . --warnings'

# Бот запуск (основной и dry-run)
alias runbot='python main.py'
alias dryrun='python main.py --dry-run'

# Логи, кэш, параметры
alias logs='tail -f logs/bot.log'
alias clean='python scripts/clean_cache.py'
alias config='python -c "from core.config import config; print(config.get_trading_params_summary())"'

# Быстрая проверка версий
alias checkenv='which python && python --version && pip --version'
