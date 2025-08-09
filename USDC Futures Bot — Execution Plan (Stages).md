# USDC Futures Bot — Execution Plan (Stages)

> **Source of Truth:** Execution / Delivery plan. Для архитектуры/спецификации см. _USDC Final Concept & Roadmap_. Для операторских инструкций — _README.md_.

**Role setup**

-   **Owner/Engineer (you)** — запускаешь команды, принимаешь диффы, мёрджишь.
-   **Architect/Lead (me)** — формулирую задачи, acceptance‑критерии, проверяю результаты.
-   **Review Assistant (Claude Opus 4.1)** — точечные аудиты сложных мест (Risk/OMS/WS), финальный текстовый аудит.
-   **Cursor (GPT‑5 family)** — основная рабочая лошадка для правок кода (BA/MAX точечно).

**Branching**

-   Main: `main`
-   Feature branches по стадиям: `feat/stage-<X>-<short>`
-   PR naming: `[stage-<X>] <verb>: <scope>`
-   Коммиты: Conventional (`feat:`, `fix:`, `refactor:`, `docs:`).

---

## Stage 0 — Alignment & Baseline (0.5д)

**Цель:** зафиксировать исходную точку и рабочий процесс.

-   [ ] Создать issue‑борд со стадиями A–J
-   [ ] Зафиксировать README + Final Concept (RC1) в репо
-   [ ] Настроить `.editorconfig`, `ruff`, `mypy` (строгий профиль)
        **Инструменты:** gpt‑5‑fast (без MAX)
        **Доказательства готовности:** PR `docs: rc1 docs landed`, зелёный `ruff/mypy` на корне.

---

## Stage A — Repo Hygiene (0.5д)

**Цель:** репозиторий без дублей/«references…» в рантайме, фикс версии Python.

-   [ ] Исключить `references ...` из PYTHONPATH и `.gitignore`
-   [ ] Очистить кеши (`__pycache__`, `.ruff_cache`)
-   [ ] `pyproject.toml`: Python 3.11; `ruff`, `mypy`
        **Инструменты:** gpt‑5‑fast (без MAX)
        **Acceptance:** `make lint`/`ruff`/`mypy` проходят, `python -m core.main --dry` не падает
        **Cursor BA промпт:** _Пройди repo, исключи `references...`, не трогай `core/_` кроме настроек. Покажи дифф.\*

---

## Stage B — Unified Config (0.5–1д)

**Цель:** единый конфиг с автопереключением USDT(Testnet)/USDC(Prod).

-   [ ] `core/config.py`: `TESTNET`, `QUOTE_COIN`, `SETTLE_COIN`, `LEVERAGE_DEFAULT`, риск‑поля
-   [ ] Автологика: `TESTNET=true` && пустой `QUOTE_COIN` → `USDT`, иначе `USDC`
-   [ ] `.env.example` обновлён
        **Инструменты:** gpt‑5‑high‑fast (BA, MAX=ON)
        **Acceptance:** юнит‑тесты конфигурации; лог старта печатает корректный режим
        **Проверка:** `python -m core.main --dry --log-level=info`

---

## Stage C — Symbols & Markets (0.5–1д)

**Цель:** нормализация символов и фильтр рынков.

-   [ ] `core/symbol_utils.py`: `perp_symbol(base, coin)` → `BASE/QUOTE:QUOTE`
-   [ ] `core/symbol_manager.py`: фильтр `contract==True` && `settle==SETTLE_COIN` (или `quote==QUOTE_COIN`)
-   [ ] `default_symbols(coin)` — BTC, ETH, BNB, SOL, ADA
        **Инструменты:** gpt‑5‑high‑fast (BA, MAX=ON)
        **Acceptance:** юнит‑тесты `perp_symbol`/фильтров; лог выводит корректные наборы для USDT/USDC
        **Проверка:** `python quick_check.py` (будет добавлен на Stage H)

---

## Stage D — Exchange Client (0.5–1д)

**Цель:** `ccxt.binanceusdm`, sandbox‑режим, плечо/маржа, ретраи.

-   [ ] `exchange.set_sandbox_mode(TESTNET)`; `await load_markets()`
-   [ ] `set_leverage(LEVERAGE_DEFAULT, symbol, {"marginMode":"isolated"})`
-   [ ] Тайм‑синхр `adjustForTimeDifference=True`, ретраи/бэкофф
-   [ ] OrderManager: идемпотентный `clientOrderId`, централизованные `create/replace/cancel`
        **Инструменты:** gpt‑5‑fast → gpt‑5‑high (на OMS), без MAX
        **Acceptance:** интеграционный тест (testnet): place/cancel успешно, логи чистые

---

## Stage E — User Data / WebSocket (1–2д)

**Цель:** устойчивый WS‑контур в проде, пока в RC1 может быть выключен.

-   [ ] Создание `listenKey`, keepalive \~30мин
-   [ ] Подписки: `ORDER_TRADE_UPDATE`, `ACCOUNT_UPDATE`
-   [ ] Реконнект + полная REST‑сверка после восстановления
        **Инструменты:** gpt‑5‑high; точечный аудит **Opus 4.1** (MAX=ON один проход)
        **Acceptance:** длительный прогон на тестнете (2–4ч) без рассинхронизаций; журнал событий без потерь

---

## Stage F — Risk & Sizing (0.5–1д)

**Цель:** строгие лимиты и детерминированный сайзинг.

-   [ ] Обязательный SL; дневной стоп; запрет мартингейла
-   [ ] Сайзинг от эквити в `QUOTE_COIN` с учётом `stepSize/tickSize`
        **Инструменты:** gpt‑5‑high; аудит **Opus 4.1** точечно
        **Acceptance:** юниты на граничные случаи; ручной тест просадки/блокировки входов

---

## Stage G — Strategy Integration (0.5д)

**Цель:** чистая интеграция `scalping_v1` с кулдауном.

-   [ ] Интерфейс Strategy; переключатели по символам
        **Инструменты:** gpt‑5‑fast
        **Acceptance:** dry‑run/тестнет‑прогон без ошибок, ожидаемые входы/выходы в логах

---

## Stage H — Utilities & Quick Check (0.5д)

**Цель:** операционная готовность.

-   [ ] Обновить `check_orders.py`, `check_positions.py`, `close_position.py`, `main.py`
-   [ ] Добавить `quick_check.py` (рынки/плечо/доступы; ping REST/WS)
        **Инструменты:** gpt‑5‑fast
        **Acceptance:** `python quick_check.py` проходит, выдаёт стройный отчёт

---

## Stage I — Tests & CI (0.5–1д)

**Цель:** воспроизводимость.

-   [ ] Юнит‑тесты: symbols, filters, sizing, risk
-   [ ] Интеграция: testnet place/cancel, WS поток, реконнект
-   [ ] CI: два конфигурационных прогона (USDT testnet / USDC prod‑mock)
        **Инструменты:** gpt‑5‑fast + gpt‑5‑high
        **Acceptance:** зелёный CI, стабильные тайминги

---

## Stage J — Deploy & Observability (0.5–1д)

**Цель:** пред‑прод.

-   [ ] Dockerfile (+ compose), ротация логов
-   [ ] Алерты (Telegram/Email/Slack) на критические события
        **Инструменты:** gpt‑5‑fast
        **Acceptance:** запуск контейнера в testnet, телеграм‑оповещения работают

---

## Параллельные потоки

-   **Docs polish (при необходимости):** Opus 4.1 — финальный текстовый аудит (README/Final Concept). _Не обязателен сейчас; целесообразен после Stage E/F._
-   **Perf pass:** профилирование задержек, оптимизация ретраев (gpt‑5‑fast), после Stage D/E.

---

## Решения по моделям

-   По умолчанию: **gpt‑5‑fast**
-   Большие/многофайловые задачи: **gpt‑5‑high‑fast** + **BA** + **MAX ON** (Stage B/C)
-   Глубокая логика/риск/WS: **gpt‑5‑high**; аудит: **Opus 4.1** (разово, MAX ON)

---

## Контроль качества (каждой стадии)

-   **Definition of Done**: список acceptance + тесты + обновлённые логи/README при необходимости
-   **Evidence pack**: дифф PR, пример лога запуска, скрин/артефакт теста
-   **Roll‑back**: feature branch, atomic commits, метки `rc1.stageX`

---

## Что делаем прямо сейчас (Next 24h)

**Связанные документы:** [USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md](USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md) · _README.md_

1. Stage A (Repo Hygiene) → BA off, gpt‑5‑fast → PR.
2. Stage B (Unified Config) → BA on, gpt‑5‑high‑fast, MAX on → PR.
3. Stage C (Symbols & Markets) → BA on, gpt‑5‑high‑fast, MAX on → PR.
4. После мёрджа — короткий smoke: `python main.py --dry`, затем testnet‑инициализация без ордеров.

---

## Когда звать Opus 4.1

-   После Stage E (WS) и Stage F (Risk) — **точечный аудит**: гонки в OMS/WS, консистентность статусов, блокировки при дневном стопе, корректность сайзинга.
-   (Опционально) Финальный **docs‑polish** на RC1.1: ясность README, гайды, чек‑листы.
