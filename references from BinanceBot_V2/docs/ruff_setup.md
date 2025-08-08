# Ruff Setup & Configuration

## Обзор

Настройка Ruff для проекта BinanceBot_V2 с отключением некритичных предупреждений и сохранением важных проверок.

## Конфигурация

### pyproject.toml
Основные настройки Ruff находятся в `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "B",  # flake8-bugbear
    "C4", # flake8-comprehensions
    # "UP", # pyupgrade - отключен для избежания предупреждений о typing
]
ignore = [
    "E501",  # line too long (handled by formatter)
    "B008",  # do not perform function calls in argument defaults
    "UP035", # typing.Dict deprecated - отключен
    "UP006", # Use 'dict' instead of 'Dict' - отключен
    "F401",  # unused imports - отключен для гибкости
    "F841",  # unused variables - отключен для отладочных переменных
    "I001",  # import sorting - отключен для гибкости
]
```

### VS Code Settings
Настройки в `.vscode/settings.json`:

```json
{
    "ruff.enable": true,
    "ruff.organizeImports": true,
    "ruff.fixAll": true,
    "ruff.lint.args": ["--ignore", "UP035,UP006,F401,F841,I001"],
    "ruff.showNotifications": "off"
}
```

## Команды

### Ручные команды
```bash
# Проверка кода
./venv/Scripts/ruff check . --ignore UP035,UP006,F401,F841,I001

# Исправление проблем
./venv/Scripts/ruff check . --fix --ignore UP035,UP006,F401,F841,I001

# Форматирование
./venv/Scripts/ruff format .

# Полная проверка и исправление
./venv/Scripts/ruff check . --fix --ignore UP035,UP006,F401,F841,I001 && ./venv/Scripts/ruff format .
```

### Алиасы (после source scripts/ruff_commands.sh)
```bash
ruff_check      # Проверка кода
ruff_fix        # Исправление проблем
ruff_format     # Форматирование
ruff_full       # Полная проверка и исправление

# Или короткие алиасы:
ruff-check
ruff-fix
ruff-format
ruff-full
```

### VS Code Tasks
Доступные задачи в VS Code (Ctrl+Shift+P → Tasks: Run Task):
- `Ruff: Check` - Проверка кода
- `Ruff: Fix` - Исправление проблем
- `Ruff: Format` - Форматирование
- `Ruff: Full Check & Fix` - Полная проверка и исправление

## Игнорируемые предупреждения

### UP035/UP006 - Typing Deprecation
- **UP035**: `typing.Dict` is deprecated, use `dict` instead
- **UP006**: Use 'dict' instead of 'Dict' for type annotation

**Причина отключения**: Эти предупреждения появляются при использовании `typing.Dict` и `typing.List`, которые все еще широко используются в коде. Отключаем для избежания ложных срабатываний.

### F401 - Unused Imports
**Причина отключения**: В некоторых случаях импорты могут быть неиспользуемыми временно (отладочные, будущие функции). Отключаем для гибкости разработки.

### F841 - Unused Variables
**Причина отключения**: Переменные могут быть неиспользуемыми в процессе разработки или отладки. Отключаем для удобства.

### I001 - Import Sorting
**Причина отключения**: Автоматическая сортировка импортов может нарушить логическую группировку. Отключаем для сохранения ручного контроля.

## Файлы с особыми правилами

### __init__.py
```toml
"__init__.py" = ["F401"]  # unused imports в __init__ файлах это нормально
```

### Тесты
```toml
"tests/*" = ["S101"]      # asserts в тестах разрешены
```

### Специфичные файлы
```toml
"core/monitoring.py" = ["F401", "F841", "I001", "UP035", "UP006"]
"strategies/*" = ["F401", "F841"]
"telegram/*" = ["F401", "F841"]
"utils/*" = ["F401", "F841"]
```

## Автоматическое форматирование

### При сохранении файла
VS Code автоматически:
- Форматирует код с помощью Ruff
- Исправляет автоматически исправляемые проблемы
- Организует импорты

### Pre-commit hooks
В `.pre-commit-config.yaml` настроены хуки для автоматической проверки при коммитах.

## Проверка статуса

Для проверки, что все настроено правильно:

```bash
# Загрузить алиасы
source scripts/ruff_commands.sh

# Запустить полную проверку
ruff_full
```

Ожидаемый результат: `All checks passed!`

## Troubleshooting

### Ruff не найден
```bash
# Проверить установку
which ruff
# или
./venv/Scripts/ruff --version
```

### Проблемы с путями в Windows
Используйте полный путь к ruff в venv:
```bash
./venv/Scripts/ruff check .
```

### Конфликт конфигураций
Если есть конфликт между `.ruff.toml` и `pyproject.toml`, удалите `.ruff.toml` и используйте только `pyproject.toml`.
