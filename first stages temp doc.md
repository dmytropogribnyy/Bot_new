ок, вижу структуру (BinanceBot_OLD_migration, .env/.env.example, .editorconfig, pyproject.toml уже есть). Ниже — финальный, сшитый под Windows + Git Bash план для первых этапов и готовые промпты для Cursor, плюс выбор моделей.

Stage 0 — Alignment & Baseline (30–45 мин)
Что делаем
venv + инструменты

bash
Copy
Edit
cd BinanceBot_OLD_migration
python -m venv .venv && source .venv/Scripts/activate
python -m pip install -r requirements.txt
python -m pip install ruff mypy pre-commit python-dotenv
pre-commit install
pyproject.toml — оставляем твой, добавь исключения (если их нет):

toml
Copy
Edit
[tool.ruff]
line-length = 120
target-version = "py312"
exclude = ["core/legacy/","references_archive/",".venv/","venv/"]

[tool.mypy]
python_version = "3.12"
strict = true
exclude = '(^(core/legacy|references_archive|\.venv|venv)/)'
.editorconfig — уже есть (ничего не меняем, если базовые правила в порядке).

Быстрый sanity:

bash
Copy
Edit
ruff check . && mypy .
DoD Stage 0: ruff/mypy проходят локально, pre-commit установлен.

Cursor — какой моделью
Док/конфиг правки: GPT-5-fast (быстро и стабильно).

Ничего “умного” тут не нужно. Агентов и команды не запускаем.

Готовый промпт для Cursor (если хочешь, чтобы он сам поправил pyproject.toml)
sql
Copy
Edit
SYSTEM (one-shot):
Ты — Python toolchain инженер. Цель: настроить ruff/mypy под Windows-проект, исключив архивы и venv из проверки.

TASK:
Открой pyproject.toml и:

1. Для [tool.ruff]: добавь exclude = ["core/legacy/","references_archive/",".venv/","venv/"] при сохранении имеющихся настроек.
2. Для [tool.mypy]: добавь strict=true (если нет) и exclude='(^(core/legacy|references_archive|\.venv|venv)/)'.
   Сделай минимальный дифф. Никаких других изменений.
   Stage A — Repo Hygiene (45–60 мин)
   Что делаем
   Папка "references from BinanceBot_V2" в рантайме не нужна. Оставляем как архив: переносим в references_archive/ и исключаем из проверок.

Архивы и переносы

bash
Copy
Edit
mkdir -p core/legacy references_archive

# перенести справочные исходники из V2

mv "references from BinanceBot_V2"/\* references_archive/ 2>/dev/null || true
rmdir "references from BinanceBot_V2" 2>/dev/null || true

# перенести легаси-модули из core (список можно расширять по месту)

for f in trade_engine binance_api exchange_init position_manager order_utils \
 engine_controller risk_adjuster risk_utils fail_stats_tracker \
 failure_logger entry_logger component_tracker signal_utils \
 scalping_mode tp_sl_logger missed_signal_logger notifier \
 balance_watcher runtime_state runtime_stats strategy \
 symbol_processor tp_utils; do
test -f "core/${f}.py" && mv "core/${f}.py" core/legacy/
done

# запрет на пакетный импорт архивов

find core/legacy references_archive -name "**init**.py" -delete
.gitignore без дублей

bash
Copy
Edit
grep -qxF "core/legacy/" .gitignore || echo "core/legacy/" >> .gitignore
grep -qxF "references_archive/" .gitignore || echo "references_archive/" >> .gitignore
Чистка кешей

bash
Copy
Edit
find . -type d -name "**pycache**" -exec rm -rf {} +
rm -rf .ruff_cache .mypy_cache .pytest_cache
Проверка на нежелательные импорты из легаси

bash
Copy
Edit
echo "🔍 Проверка импортов из core.legacy..."
grep -R --line-number -E 'from core\.(trade_engine|binance_api|exchange_init|position_manager|order_utils|engine_controller|risk_adjuster|fail_stats_tracker|tp_utils|symbol_processor|strategy|scalping_mode)\b|import core\.(trade_engine|binance_api)\b' --include="\*.py" . \
 || echo "✅ Легаси импортов не найдено"
Линт/тайп → smoke

bash
Copy
Edit
ruff check . && mypy .

# Минимальная среда для смоука

export TESTNET=true
python main.py --dry
Коммит

bash
Copy
Edit
git add -A
git commit -m "[stage-A] chore: repo hygiene & legacy isolation"
git push
DoD Stage A: ruff/mypy зелёные, python main.py --dry не падает, архивные каталоги есть и исключены.

Cursor — какой моделью
Файловые массовые правки/переезды: делай руками (bash) — так надёжнее.

Автопоиск импортов/подсказки: GPT-5-fast.

Если нужно автоматически переписать отдельные импорты: GPT-5-fast, но с чётким списком файлов.

Промпты для Cursor
А) Проверить, что нигде не тянем архивные модули

makefile
Copy
Edit
SYSTEM:
Ты — Python code auditor. Отвечай кратко, только списком находок.

USER:
Пробегись логикой по репозиторию и укажи любые места, где код мог бы подтянуть модули из core/legacy или references_archive; предложи безопасные альтернативы (если это реально рабочий код), но не пиши патчи.
Контекст: архаивируем старые файлы, рантайм не должен их импортировать.
Б) Если надо точечно поправить импорты в конкретных файлах

makefile
Copy
Edit
SYSTEM:
Ты — Python refactoring assistant. Делаешь минимальные диффы.

USER:
Открой файлы:

-   core/XXX.py
-   tools/YYY.py
    Если там есть импорты из core.trade_engine или core.binance_api — удали их, не заменяй. Если код без них ломается, оставь TODO-комментарий `# TODO: rewire after Stage D`.
    Сделай минимальный дифф и ничего больше.
    Stage D — Exchange Client (B-lite) (1–2 ч)
    Цель: только добавить параметры и безопасность исполнения ордеров, без большой перестройки.

Что делаем
Конфиг: добавить поля (если их нет)
core/config.py:

python
Copy
Edit
WORKING_TYPE: str = "MARK_PRICE" # или "CONTRACT_PRICE" по желанию
TP_ORDER_STYLE: str = "limit" # "limit" | "market"
В слое создания ордеров (твой актуальный модуль — где сейчас формируется SL/TP) обеспечить:

SL/TP всегда с reduceOnly=True

Прокидывать workingType=WORKING_TYPE

Для TP:

если TP_ORDER_STYLE == "limit" → TAKE_PROFIT (или STOP/TAKE_PROFIT в терминах биржи) с лимит-ценой

если "market" → TAKE_PROFIT_MARKET

Добавить небольшой “self-check” для dry-run:

Функции, которые только печатают сформированный payload ордера (без отправки).

Юнит или скрипт test-output/preview_orders.py, который подставляет фиктивные параметры и выводит payload.

Smoke (testnet + dry):

bash
Copy
Edit
export TESTNET=true
python test-output/preview_orders.py
python main.py --dry
DoD Stage D (B-lite): при dry-run видно, что SL/TP создаются только с reduceOnly=True, TP соответствует стилю, workingType проходит сквозь все пласты.

Cursor — какой моделью
Небольшие правки в ордерном слое, добавление констант: GPT-5-fast.

Если нужно аккуратно врезаться в “центральный” OMS слой: GPT-5-max (или “Opus/Max” эквивалент в Cursor) — точность выше.

Промпт для Cursor (B-lite патч)
arduino
Copy
Edit
SYSTEM:
Ты — Python developer с опытом Binance Futures. Делай минимальные, безопасные изменения, с подробными комментариями внутри кода.

TASK:

1. В core/config.py добавь константы:
   WORKING_TYPE="MARK_PRICE"
   TP_ORDER_STYLE="limit" # "limit"|"market"
2. В модуле, где формируются SL/TP (укажи актуальные файлы, например core/orders.py или utils_core.py):
    - Убедись, что для всех SL/TP выставляется reduceOnly=True.
    - Прокидывай workingType из config.WORKING_TYPE.
    - Для TP: если config.TP_ORDER_STYLE=="limit" — используй лимитный тип (TAKE_PROFIT), если "market" — TAKE_PROFIT_MARKET.
3. Добавь скрипт test-output/preview_orders.py, который создает фиктивный ордерный payload для long/short и печатает его (без сети).
4. Не меняй бизнес-логику входа/выхода, только параметры ордеров.
   Выведи минимальный дифф.
   (Опционально) Stage F — RiskGuard (скелет, 1 ч)
   Если хочешь сразу проложить “крючок”:

core/risk/risk_guard.py: класс с методами
check_daily_stop(), check_sl_streak(), should_block_entry()
(возвращает bool + причину).

В месте входа в позицию: одна строка, которая вызовет should_block_entry() и прервёт вход, логируя причину. Вся остальная логика Risk останется на полноценный Stage F.

Cursor — промпт для скелета
python
Copy
Edit
SYSTEM:
Ты — Python architect. Создаёшь минимальный подключаемый модуль без побочных эффектов.

TASK:
Создай core/risk/risk_guard.py со скелетом класса RiskGuard:

-   init принимает today_pnl_provider, sl_streak_provider и конфиг.
-   методы: check_daily_stop()->tuple[bool,str], check_sl_streak()->tuple[bool,str], should_block_entry()->tuple[bool,str].
-   никаких внешних импортов из архивов.
    Добавь вызов should_block_entry() в месте инициации входов (укажи файл/функцию) с логом причины, если блок.
    Минимальные тестовые вызовы в test-output/preview_risk.py.
    Выведи дифф.
    Быстрый итог и кто какую модель
    Stage 0: ручные команды + GPT-5-fast (правки конфигов/доков).

Stage A: ручные команды (перенос/архив) + GPT-5-fast (аудит импортов/микроправки).

Stage D (B-lite): GPT-5-fast для простых вставок; если правка затрагивает центральный OMS — переключайся на GPT-5-max.

RiskGuard (скелет): GPT-5-fast ок; интеграцию в entry-пайплайн — GPT-5-max, если код сложный
