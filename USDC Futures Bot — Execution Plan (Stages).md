USDC Futures Bot — Execution Plan (RC1.2): Итог по состоянию на сегодня

Снимок состояния: CI зелёный; 51 тест пройден; валидатор структуры проходит; репозиторий очищен и приведён к стандартной макет-структуре. Ниже — детальный итог «что сделали» и «что осталось» в формате обновлённого ExecutionDocument.

1. Статус по стадиям

Stage A — Repo Hygiene — ✅ выполнено

Наведён порядок в структуре: все тесты собраны под tests/, мусор/артефакты вынесены/очищены.

Добавлены служебные инструменты:

cleanup_project.py — кроссплатформенный клинер (кэши Python, логи, архивы, перенос “заблудившихся” тестов).

validate_project.py — проверка структуры, импортов, обязательных файлов.

Обновлён .gitignore и guard-маски.

Stage B — Unified Config (full) — ✅ выполнено

Унифицированная конфигурация (env → модель), корректная загрузка/сохранение, валидация.

Тесты конфигурации зелёные (в т.ч. валидация и миграция).

Stage C — Symbols & Markets (full) — ✅ выполнено

Нормализация символов/фильтров для USDT/USDC без хардкодов.

Санитарная проверка (grep) на запрет USDC→dapi/dstream проходит.

Stage D — Exchange Client (B-lite) — ✅ выполнено

Имплементированы параметры исполнения: working_type и tp_order_style, все TP/SL — reduceOnly=True.

Поддержаны оба TP-режима: TAKE_PROFIT и TAKE_PROFIT_MARKET.

Интеграционные async-тесты (listenKey/UM и эндпоинты) зелёные в CI.

Stage E — WebSocket → OMS — ⏳ осталось завершить

Скелет WS есть (keepalive, слушатели). Необходимо формально оформить acceptance-тесты на события:

ORDER_TRADE_UPDATE → маршрутизация в OMS, корректное изменение состояния ордеров/позиций.

ACCOUNT_UPDATE → обновление кэшей балансов/маржи/позиций.

Зафиксировать fallback WS→REST в документации/коде (поведение при разрывах).

Stage F — Risk & Sizing — ✅ выполнено

RiskGuard: ограничения дневных потерь, SL-стрик, precision/notional-гейты — покрыто тестами.

Проверки корректных лимитов перед размещением ордеров.

P-block — Audit & Decisions — ✅ выполнено

Тампер-устойчивый аудит (hash-цепочка), UTC-метки, редактирование секретов.

Тесты аудита зелёные, поток записей стабилен.

2. CI/CD — итоговая конфигурация (base line)

Python: 3.12.x, включён кэш pip (actions/setup-python@v5 с cache: "pip").

Установка зависимостей: всегда ставим prod + dev:

requirements.txt (прод),

requirements-dev.txt (dev; минимум pytest, pytest-asyncio, pytest-mock).

Fallback: если dev-файла нет, ставим тестовые плагины напрямую.

PYTHONPATH: на уровне job задан PYTHONPATH=${{ github.workspace }} — импорты core.\* из тестов и валидатора работают без инсталляции пакетом.

pytest.ini: активирован asyncio_mode = auto, зарегистрирован маркер asyncio.

Выполняемые шаги CI:

python -m pip install --upgrade pip

Установка прод/дев зависимостей

(Sanity) вывод версий pytest и установленных плагинов

python validate_project.py

pytest -v (или таргетные тесты)

Санитарный ripgrep — запрет жёстких USDC→dapi/dstream привязок

Управление гонками: включён concurrency (группа по ветке, отмена параллельных дубликатов).

Ручной запуск: workflow_dispatch — кнопка Run workflow.

3. Тестовый контур — что покрыто

Unit / Integration: стратегии, risk-guard, unified-config, precision/notional-гейты, listenKey/UM и эндпоинты.

Async: плагин pytest-asyncio установлен, asyncio_mode = auto задействован (зелёный CI).

Валидатор: ловит тесты вне tests/, недостающие обязательные файлы, запрещённые импорты (core.legacy/archive) и smoke-импорты базовых модулей.

Санитарные проверки: grep-правило исключает попадание неподходящих USDC→dapi/dstream связок.

4. Репозиторий и сервисные инструменты

cleanup_project.py

Удаление Python-кэшей (**pycache**, .pyc/.pyo, .pytest_cache/.ruff_cache/.mypy_cache).

Опциональная чистка архивов/бинарей (флаг), перенос тестов в tests/.

Пронормированные маски/пропуски (.git, venv/.venv, env/.tox, node_modules, site-packages).

Генерация requirements-dev.txt при отсутствии.

Dry-run режим и сводка reclaimed space.

validate_project.py

Обязательные файлы/директории (main.py, requirements.txt, .env|.env.example, tests/).

Отсутствие «заблудившихся» тестов/запрещённых импортов.

Smoke-импорты: core.config, core.exchange_client.

5. Что осталось добить (минимум для RC-завершения)

(E) WS → OMS — acceptance

Добавить тесты (моки):

ORDER_TRADE_UPDATE → вызов OrderManager.handle_ws_event(...), корректное отражение статусов/позиции.

ACCOUNT_UPDATE → обновление кэшей балансов/маржи/позиции.

Задокументировать поведение при разрывах и подтвердить fallback WS→REST в тесте.

(Hygiene) Зачистка предупреждений в своём коде (не блокер, но желательна)

datetime.utcnow() → from datetime import datetime, UTC; datetime.now(UTC).

Pydantic v2: .dict() → .model_dump() (и в тестах).

Тесты, где возвращается True/False → заменить на assert ….

Закрытие клиентов aiohttp/ccxt: фикстура с await exchange.close() в finally.

6. Операционный чеклист (pre-testnet)

Конфиг и ключи: .env содержит только тестнет-ключи; config.testnet = true; лимиты риска/размеры позиций адекватны.

Сети и сессии: keepalive listenKey включён; при разрывах есть автоперезапуск; fallback на REST понятен.

Логи: ротация включена; audit-лог активен (тампер-цепочка).

Смок-прогоны:

python main.py --dry-run — ок.

python main.py --once — ок.

CI: зелёный на main; sanity-grep чистый.

7. Контрольные ворота (Acceptance gates)

✅ CI полностью зелёный (включая async-тесты и валидатор).

✅ Stage A/B/C/D/F/P закрыты; у Stage E — есть e2e-прохождение мок-событий и маршрутизация в OMS.

✅ Отсутствуют жёсткие привязки USDC→dapi/dstream.

✅ RiskGuard стабильно отсекает вход по лимитам; precision/notional-гейты работают.

8. Предлагаемый следующий PR (маленький и «закрывочный»)

WS→OMS acceptance: 2 теста с мок-событиями (ORDER_TRADE_UPDATE, ACCOUNT_UPDATE) + минимальные адаптеры, если требуются.

Hygiene-фикс де-прекаций: utcnow() → now(UTC), .dict() → .model_dump(), фикстура await exchange.close(), замена return → assert в тестах.

README/Docs: короткая заметка «Как запускать тестнет» и итог RC1.2.

Резюме: база готова — чистая структура, консистентный конфиг/рынки, корректный exchange-клиент (B-lite), risk-контур и аудит, зелёный CI. Для полного закрытия RC1.2 осталось только оформить WS→OMS acceptance и (по желанию) пригладить ворнинги. После этого — смело на тестнет.
