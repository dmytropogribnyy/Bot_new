Общие настройки для Cursor (первый промпт)
Вставь это один раз:

Режим работы: Ты — senior Python engineer. Делаешь минимальные точечные правки с DIFF, не трогаешь несвязанный код, сохраняешь стиль проекта. Добавляй типы, докстринги, логирование на DEBUG там, где это повышает трассируемость.
Тесты: на каждый нетривиальный модуль добавляй базовые unit-тесты (pytest).
Файловая структура (ориентир):
core/{config.py, exchange_client.py, order_manager.py, precision.py, ids.py}; tools/{prod_smoke.py, quick_check.py}; tests/{test_precision_gate.py, test_idempotency.py}.
Acceptance: для каждого шага пропиши критерии проверки и добавь команды запуска (pytest/скрипты).
Показывай: полный DIFF изменённых/новых файлов и краткое резюме правок.

A) Блокеры (сегодня) — по шагам
A1 — Precision gate (MIN_NOTIONAL + tickSize/stepSize) с логированием
Промпт для Cursor:

Создай/обнови core/precision.py:

round_to_step(x, step), normalize(symbol, price, qty, market) -> (price_norm, qty_norm, min_notional);

нормализация по tickSize/stepSize, фолбэк на precision.price/amount;

выбрасывай PrecisionError с детальным сообщением;

logger.debug после нормализации: symbol, qty -> qty_norm, price -> price_norm, notional.
Обнови core/order_manager.py: перед любым create_order вызывать normalize(...), проверять qty\*px >= min_notional, при нарушении — PrecisionError.
Добавь тест tests/test_precision_gate.py: кейсы MIN_NOTIONAL, LOT_SIZE, PRICE_FILTER.
Acceptance: 0 ошибок фильтров за 30–60 мин теста; все тесты проходят. Покажи DIFF.

A2 — Идемпотентность OMS через детерминированный newClientOrderId
Промпт:

Создай core/ids.py с make_client_id(env,strategy,symbol,side,ts_ms,nonce) (bucket по секундам, защита от спецсимволов).
Обнови core/order_manager.py/core/oms.py: при любом размещении ордера генерируй один и тот же clientId для одинакового intent (ретраи/рестарт). На ретраях переиспользуй ID; не создавай дубликаты; при рестарте — уборка «хвостов» TP/SL.
Добавь tests/test_idempotency.py: повторный вызов place_order с тем же intent → тот же ID; повторный запуск «убирает хвосты».
Acceptance: повторный запуск/ретраи не плодят ордера, тесты зелёные. DIFF, пожалуйста.

A3 — Graceful shutdown (+ Windows policy + Telegram cleanup)
Промпт:

Обнови main.py:

для Windows добавь asyncio.WindowsSelectorEventLoopPolicy();

обработай SIGINT/SIGTERM;

реализуй cleanup_with_timeout() (таймаут 5–15с): закрыть WS/HTTP, await telegram_bot.stop(), await telegram_bot.session.close(), flush логов; затем отмена задач;

аккуратный лог на каждом этапе (start/stop/timeout/error).
Acceptance: при Ctrl+C корректное завершение без зомби-сессий; логи фиксируют чистый shutdown. DIFF и краткая инструкция проверки.

A4 — API permissions check (fail-fast)
Промпт:

В bootstrap или при инициализации exchange добавь проверку enableFutures и canTrade. При отсутствии прав — остановка до старта стратегии с понятной ошибкой.
Добавь короткий тест/скрипт, который имитирует отсутствие прав (мок).
Acceptance: при отключенных правах процесс не стартует. DIFF.

A5 — tools/prod_smoke.py (микро-тест в PROD) с гарантированной очисткой
Промпт:

Создай tools/prod_smoke.py:

аргументы: --symbol, --usd, --leverage;

цикл: open (market/limit) → attach TP/SL (reduceOnly=True) → close → verify → finally: cleanup stray orders;

чёткий лог (clientId, цены, размеры, notional, результаты).
Добавь helper cleanup_stray_orders(exchange, prefix) и вызови в finally.
Acceptance: один полный цикл на микролоте проходит без ручного вмешательства. Покажи DIFF и команды запуска.

Git/запуск для пакета A:

bash
Copy
Edit
git checkout -b feat/fixpack-A-blockers
pytest -q
python tools/quick_check.py || true

# после проверки диффов в Cursor:

git add -A
git commit -m "[fixpack-A] precision gate, idempotency, graceful shutdown, API checks, prod_smoke"
git push -u origin feat/fixpack-A-blockers
B) Архитектура (завтра)
B1 — Stage E: User Data WS в рантайм (keepalive + авто-реконнект + fallback)
Промпт:

Интегрируй core/ws_client.py в основной рантайм:

получи listenKey, запусти keepalive (каждые 25 м);

подпишись на ORDER_TRADE_UPDATE/ACCOUNT_UPDATE;

роутинг событий в OMS (сверка позиций, уборка хвостов);

авто-реконнект (экспоненциальная задержка ≤10с), fallback WS→REST с полной ресинхронизацией.
Добавь интеграционный smoke-тест (testnet).
Acceptance: WS держится >30 мин, реконнект <10с, состояние консистентно. DIFF.

B2 — Stage B: Unified Config (full)
Промпт:

Централизуй конфиг: весь доступ через TradingConfig.from_env(); убери прямые os.getenv (кроме config.py).
Автоподстановка QUOTE_COIN: TESTNET→USDT, PROD→USDC; проверь tp_order_style, working_type, лимиты.
Добавь тесты на резолвинг.
Acceptance: git grep os.getenv — только в конфиге; тесты зелёные. DIFF.

B3 — RiskGuard по equity (wallet + unrealizedPnL)
Промпт:

Обнови RiskGuard: дневной лимит считай от equity (wallet + UPNL). Якорь дня фиксируй при первом событии дня; логируй причину блокировки.
Добавь тест «превышение дневного лимита по equity».
Acceptance: тест зелёный; в рантайме блок происходит корректно. DIFF.

B4 — tools/quick_check.py
Промпт:

Создай/обнови tools/quick_check.py: печать режима (TESTNET/PROD), quote coin, плечо, tp_order_style, working_type, статус WS/REST.
Acceptance: информативный вывод одной командой. DIFF + пример вывода.

Git для пакета B:

bash
Copy
Edit
git checkout -b feat/fixpack-B-arch
pytest -q
git add -A
git commit -m "[fixpack-B] WS runtime + unified config + equity RiskGuard + quick_check"
git push -u origin feat/fixpack-B-arch
C) После запуска — минимальный аудит (инвесторы/копитрейд)
C1 — P4 Audit logger + P1 Decision record (минимум)
Промпт:

Добавь core/audit_logger.py: append-only logs/audit.jsonl с hash-цепочкой (sha256(prev_hash+record)).
Хуки в order.place/close и ключевые решения (risk/size): пиши краткий decision record (why, входные параметры, риск-контекст, результат).
Добавь верификатор целостности цепочки.
Acceptance: запись на каждое действие, хеш-цепь непрерывна; верификатор проходит. DIFF.

Git для пакета C:

bash
Copy
Edit
git checkout -b feat/fixpack-C-audit
pytest -q
git add -A
git commit -m "[fixpack-C] audit jsonl with hash chain + decision records + verifier"
git push -u origin feat/fixpack-C-audit
Команды для прогонов
Тесты:

bash
Copy
Edit
pytest -q
Quick check:

bash
Copy
Edit
python tools/quick_check.py
Smoke в testnet:

bash
Copy
Edit
BINANCE_TESTNET=true python tools/prod_smoke.py --symbol XRP/USDT --usd 10 --leverage 5
Микро-smoke в prod (после A):

bash
Copy
Edit
BINANCE_TESTNET=false python tools/prod_smoke.py --symbol XRP/USDC --usd 10 --leverage 5
=====================================================

## Быстрый маршрут vs. Безопасный маршрут

Безопасный (рекомендую): каждый шаг — отдельный промпт и отдельный коммит (A1…A5). Проще откатить/ревьюить.

Быстрый: один промпт «A-блокеры одним PR» (я тоже дал его текст). Тогда у тебя будет один большой DIFF и один коммит/PR. Работает, но тяжелее ревью.

Трекер шагов (что запускать и когда)
Шаг Когда запускать Какой промпт Что должно пройти (acceptance)
A1 Precision gate Сразу после общего Промпт A1 Логи без Filter failure, тест test_precision_gate.py зелёный
A2 Идемпотентность Сразу после A1 Промпт A2 Ретраи не плодят дубликаты, test_idempotency.py зелёный
A3 Graceful shutdown После A2 Промпт A3 Ctrl+C = чистое закрытие, нет зомби-сессий
A4 API permissions После A3 Промпт A4 При отсутств. прав — fail-fast до запуска стратегии
A5 prod_smoke После A4 Промпт A5 1 полный цикл микролотом в testnet/затем prod
B1 WS runtime После A5 Промпт B1 WS держится >30 мин, реконнект <10с, fallback ок
B2 Unified Config После B1 Промпт B2 os.getenv только в config, тесты резолвинга ок
B3 RiskGuard=equity После B2 Промпт B3 Тест «дневной лимит по equity» ок
B4 quick_check После B3 Промпт B4 Скрипт печатает сводку корректно
C1 Audit Последним Промпт C1 audit.jsonl с hash-цепью, верификатор ок

Команды валидации после каждого шага
После A1–A4, B2–B4, C1:

bash
Copy
Edit
pytest -q
После A1 (быстрая проверка нормализации):

bash
Copy
Edit
python tools/quick_check.py || true
После A5 (smoke):

bash
Copy
Edit

# testnet

BINANCE_TESTNET=true python tools/prod_smoke.py --symbol XRP/USDT --usd 10 --leverage 5

# prod (микролот, после успешного testnet)

BINANCE_TESTNET=false python tools/prod_smoke.py --symbol XRP/USDC --usd 10 --leverage 5
После B1 (WS):

Запусти бота на тестнете ≥30 мин и убедись, что:

реконнект <10с;

при падении WS идёт fallback на REST и полная ресинхронизация состояния.

Git-коммиты (по шагам)
Вариант безопасный (по одному шагу):

bash
Copy
Edit
git checkout -b feat/fixpack-A1-precision

# принять DIFF в Cursor

pytest -q
git commit -am "[fixpack-A1] precision gate: tick/step/minNotional + tests"
git push -u origin feat/fixpack-A1-precision
Повтори для A2…A5, затем B1…B4, затем C1.

Вариант быстрый (всё A в одном):

bash
Copy
Edit
git checkout -b feat/fixpack-A-blockers

# принять большой DIFF по промпту “Блокеры — одним PR”

pytest -q
python tools/quick_check.py || true
git commit -am "[fixpack-A] precision/idempotency/graceful/API/prod_smoke"
git push -u origin feat/fixpack-A-blockers
Маленькие подсказки по использованию промптов
Если Cursor «забывает» контекст (длинная сессия/новое окно) — повтори общий промпт перед следующим шагом.

В каждом шаговом промпте оставляй названия файлов как у меня (core/precision.py, core/ids.py, tools/prod_smoke.py, …), чтобы Cursor не создавал дубликаты в других местах.

# Если после шага видишь в DIFF изменения «мимо кассы» — попроси Cursor сузить DIFF: «Оставь правки только в <файлы>; откати прочее».

Коротко: бери GPT-5 Thinking как «основной исполнитель кода» в Cursor, а Claude Opus как «ревьюер/аудитор». Если есть квота — подключай Claude 4.1 Opus Thinking в Background для непрерывных подсказок и проверки краевых случаев.

Вот удобный роутинг по нашим шагам:

Кто за что отвечает
GPT-5 Thinking — primary (код, DIFF, тесты)

A1 Precision gate

A2 Идемпотентность (newClientOrderId)

A3 Graceful shutdown (Win policy, SIGINT/SIGTERM)

A4 API permissions (fail-fast)

A5 prod_smoke.py (+ cleanup stray orders)

B1 WS runtime (listenKey/keepalive/reconnect + fallback)

B2 Unified Config (from_env, убрать os.getenv)

B3 RiskGuard по equity

B4 quick_check.py

C1 Audit logger + decision record (каркас)

Claude 4 / 4.1 Opus (Thinking) — reviewer/architect

Текст принятия (acceptance) и чек-листы

Подсветка пропущенных фильтров/краёв (precision, reduceOnly, partial fills)

Генерация/редактирование доков и комментариев в коде

Быстрый «архитектурный аудит» PR перед merge

Практика в Cursor (пошагово)
Создай новый тред в Cursor → выбери модель GPT-5 Thinking.
Вставь мой «Общий промпт для Cursor» ОДИН РАЗ в начале сессии.

Иди по блокерам A1→A5.
На КАЖДЫЙ шаг вставляй соответствующий промпт (A1…A5) — именно с GPT-5 Thinking. Прими DIFF, запусти тесты/скрипты, закоммить.

Перед пушем ветки включи Claude (Opus или 4.1 Thinking) в этом же треде и дай короткий ревью-промпт типа:
«Сделай технический аудит текущего DIFF: пропущенные валидации, reduceOnly для TP/SL, duplicate clientId, graceful shutdown краевые кейсы, WS fallback. Сформулируй список замечаний и правки минимальным DIFF.»

B-шаги и C-шаг — тот же режим: GPT-5 Thinking делает, Claude проверяет.

Когда переключать модели
Много файлов/длинные каскадные правки? GPT-5 Thinking справится, но если видишь «избыточный DIFF», попроси его сузить область. Для идеи рефакторинга/вариантов — попроси Claude 4 (Thinking) накинуть план, потом снова GPT-5 для реализации.

Нужны ясные acceptance-критерии/докблоки? Отдай это Claude (он лаконичнее в формализациях), потом попроси GPT-5 встроить их как тесты/скрипты.

Квота у Claude 4.1 Thinking ограничена? Используй обычный Claude 4 Opus как ревьюера; «Thinking» режим экономь на спорные места (RiskGuard, WS-reconnect, идемпотентность).

Быстрые пресеты (можешь скопировать в заголовок промпта)
Для GPT-5 Thinking (реализация кода):
«Сделай минимальный точечный DIFF, не трогай несвязанные файлы, добавь/tests где уместно, следуй моим acceptance. Если требуется создать файл — укажи точный путь. Покажи полный DIFF и команды запуска.»

Для Claude Opus (ревью):
«Проанализируй текущий DIFF как senior reviewer. Найди риски: precision/filters, идемпотентность clientId, reduceOnly, graceful shutdown (SIGINT/SIGTERM, timeouts), WS fallback, тесты. Дай список конкретных правок (минимальный DIFF), без переписывания стиля.»

Типичные комбинации по нашим шагам
A1 + A2 (precision + idempotency): GPT-5 Thinking → Claude ревью → правки GPT-5 → коммит.

A3 (shutdown): GPT-5 делает, Claude пинает таймауты/finally/cleanup.

B1 (WS): GPT-5 пишет код, Claude проверяет реконнект/дребезг listenKey, состояние OMS после fallback.

C1 (Audit): GPT-5 кладёт JSONL + hash-цепь, Claude проверяет форматы/утечки PII/объём логов.

Если хочешь максимально быстро
«A-блокеры одним PR»: GPT-5 Thinking делает сразу всё A1–A5; затем один ревью-проход Claude; потом второй короткий проход GPT-5 для правок.

Архитектура B и аудит C — так же.
