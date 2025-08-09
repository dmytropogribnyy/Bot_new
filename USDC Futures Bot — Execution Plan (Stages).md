# USDC Futures Bot — Execution Plan (Stages) — RC1.1

> **Source of Truth:** Execution / Delivery plan. Для архитектуры/спецификации см. _USDC Final Concept & Roadmap (RC1.1)_. Для операторских инструкций — _README.md_.

**Role setup**

-   **Owner/Engineer (you)** — запускаешь команды, принимаешь диффы, мёрджишь.
-   **Architect/Lead (me)** — формулирую задачи, acceptance-критерии, проверяю результаты.
-   **Review Assistant (Claude Opus 4.1)** — точечные аудиты сложных мест (Risk/OMS/WS), финальный текстовый аудит.
-   **Cursor (GPT-5 family)** — основная рабочая лошадка для правок кода (BA/MAX точечно).

**Branching**

-   Main: `main`
-   Feature branches: `feat/stage-<X>-<short>`
-   PR naming: `[stage-<X>] <verb>: <scope>`
-   Коммиты: Conventional (`feat:`, `fix:`, `refactor:`, `docs:`)

---

## Delta (что изменилось vs RC1)

1. **TP параметризуется**: `tp_order_style = "limit"|"market"` (по умолчанию — `"limit"`).
2. **SL/TP всегда с `reduceOnly=True` и `workingType`** (по умолчанию `"MARK_PRICE"`).
3. **RiskGuard**: единая точка блокировки входов (SL-streak и дневной стоп).
4. **Hygiene**: формализован перенос легаси в `core/legacy/` и `references_archive/`.
   Порядок приоритетов: A → D → F → (тестнет) → E.

## Авторитетный порядок выполнения (Safety‑first)

1. **Stage A — Repo Hygiene**
2. **Stage D — Exchange Client** _(содержит B‑lite конфиг: `tp_order_style`, `working_type`)_
3. **Stage F — Risk & Sizing (RiskGuard)**
4. **Testnet smoke** _(dry‑run → micro lot)_
5. **Stage B — Unified Config (full)**
6. **Stage C — Symbols & Markets (full)**
7. **Stage E — WebSocket**
8. **Stage G/H/I/J** по плану

---

## Stage 0 — Alignment & Baseline (0.5д)

**Цель:** зафиксировать исходную точку и рабочий процесс.

-   [ ] Issue-борд со стадиями A–J
-   [ ] Зафиксировать README + Final Concept (RC1.1) в репо
-   [ ] `.editorconfig`, `ruff`, `mypy` (строгий профиль)

**Инструменты:** gpt-5-fast (без MAX)
**DoD:** PR `docs: rc1.1 docs landed`, зелёный `ruff/mypy`.

---

## Stage A — Repo Hygiene (0.5д)

**Цель:** репозиторий без дублей/«references…» в рантайме; фикс Python; чистые кеши.

**Tasks**

-   [ ] Увести легаси в архив: `core/legacy/` и `references_archive/` (не импортируются).
-   [ ] Исключить `references …` из PYTHONPATH и `.gitignore`.
-   [ ] Очистить кеши (`__pycache__`, `.ruff_cache`, `.mypy_cache`).
-   [ ] `pyproject.toml`: Python 3.12; профили `ruff/mypy`; `make lint|fmt|type|all`.

**Пример команд**

```bash
mkdir -p core/legacy references_archive
mv core/trade_engine.py core/legacy/ || true
mv core/binance_api.py core/legacy/ || true
mv "references from BinanceBot_V2"/* references_archive/ 2>/dev/null || true

find . -type d -name "__pycache__" -exec rm -rf {} +
rm -rf .ruff_cache .mypy_cache

echo "core/legacy/"           >> .gitignore
echo "references_archive/"    >> .gitignore
```

**Инструменты:** gpt-5-fast (BA=off)
**Acceptance:** `make fmt && make lint && make type` ок; `python main.py --dry` не падает.

---

## Stage B — Unified Config (после D+F) (0.5–1д)

**Цель:** единый конфиг + автопереключение USDT(Testnet)/USDC(Prod).

**Tasks**

-   [ ] `core/config.py`: `TESTNET`, `QUOTE_COIN`, `SETTLE_COIN`, `LEVERAGE_DEFAULT` и риск-поля.
-   [ ] Автологика: `TESTNET=true` & пустой `QUOTE_COIN` → `USDT`, иначе → `USDC`.
-   [ ] `.env.example` обновлён.

**Инструменты:** gpt-5-high-fast (BA, MAX=ON)
**Acceptance:** юнит-тесты конфигурации; лог старта печатает режим (USDT testnet / USDC prod).

---

## Stage C — Symbols & Markets (после D+F) (0.5–1д)

**Цель:** нормализация символов и фильтр рынков.

**Tasks**

-   [ ] `core/symbol_utils.py`: `perp_symbol(base, coin)` → `BASE/QUOTE:QUOTE`.
-   [ ] `core/symbol_manager.py`: фильтр `contract==True` и `settle==SETTLE_COIN` (или `quote==QUOTE_COIN`).
-   [ ] `default_symbols(coin)` → BTC, ETH, BNB, SOL, ADA.

**Инструменты:** gpt-5-high-fast (BA, MAX=ON)
**Acceptance:** юнит-тесты `perp_symbol`/фильтров; лог корректно выводит набор символов.

---

## Stage D — Exchange Client (+ TP/SL параметризация, + B-lite конфиг) (0.5–1д)

**Цель:** устойчивый Exchange Layer + гибкая логика TP/SL.

_Примечание (B‑lite): на этом этапе из Stage B добавляем только 2 поля конфигурации — `tp_order_style` и `working_type`; остальная унификация конфигурации будет выполнена позже (Stage B full)._

**Tasks**

-   [ ] `ccxt.binanceusdm`, `set_sandbox_mode(TESTNET)`, `await load_markets()`.
-   [ ] `set_leverage(LEVERAGE_DEFAULT, symbol, {"marginMode": "isolated"})`.
-   [ ] **Config**: добавить

    -   `working_type: Literal["MARK_PRICE","CONTRACT_PRICE"]="MARK_PRICE"`
    -   `tp_order_style: Literal["limit","market"]="limit"`

-   [ ] **SL**: `STOP_MARKET` + `reduceOnly=True` + `params["workingType"]=config.working_type`.
-   [ ] **TP**: если `tp_order_style=="market"` → `TAKE_PROFIT_MARKET` (`price=None`, `stopPrice=tp`); иначе `TAKE_PROFIT` (`price=tp`, `stopPrice=tp`), всегда `reduceOnly=True` и `workingType` из конфига.
-   [ ] OMS: идемпотентный `clientOrderId`, ретраи/бэкофф, чистые логи.

**Cursor prompt (кусок)**

```
Задача: доработка Exchange Client.
1) В TradingConfig добавь поля:
   - working_type: Literal["MARK_PRICE","CONTRACT_PRICE"]="MARK_PRICE"
   - tp_order_style: Literal["limit","market"]="limit"
2) В create_stop_loss_order / create_take_profit_order:
   - всегда params["reduceOnly"]=True и params["workingType"]=config.working_type
   - TP: "market" → TAKE_PROFIT_MARKET (price=None, stopPrice=tp);
         иначе → TAKE_PROFIT (price=tp, stopPrice=tp)
3) Покажи DIFF, не трогай бизнес-логику вне этих функций.
```

**Инструменты:** gpt-5-fast → gpt-5-high (на OMS)
**Acceptance:** интеграционный тест на testnet ставит SL и TP обоих стилей; логи содержат `workingType` и `reduceOnly`.

---

## Stage E — User Data / WebSocket (1–2д)

**Цель:** устойчивый WS-контур; включать после стабилизации REST.

**Tasks**

-   [ ] `listenKey` + keepalive \~30 мин
-   [ ] Подписки: `ORDER_TRADE_UPDATE`, `ACCOUNT_UPDATE`
-   [ ] Реконнект + пост-рестарт **полная REST-сверка**

**Инструменты:** gpt-5-high; аудит **Opus 4.1** (MAX=ON, один проход)
**Acceptance:** длительный прогон на тестнете (2–4ч) без потери событий/рассинхронизаций.

---

## Stage F — Risk & Sizing (0.5–1д)

**Цель:** строгие лимиты и детерминированный сайзинг; **RiskGuard**.

**Tasks**

-   [ ] `core/risk_guard.py`: класс `RiskGuard(config, logger)` с `sl_streak`, `daily_loss`, `max_sl_streak`, `can_open_position()->(bool,str)`.
-   [ ] Интеграция: перед открытием позиций спрашивать guard; блокировать по streak/day-loss.
-   [ ] Сайзинг от эквити в `QUOTE_COIN` c учётом `stepSize/tickSize`.
-   [ ] Тесты на граничные кейсы (3 подряд SL, дневной предел).

**Инструменты:** gpt-5-high; аудит **Opus 4.1** точечно
**Acceptance:** юниты зелёные; ручной тест: при превышении лимитов вход блокируется.

---

## Stage G — Strategy Integration (0.5д)

**Цель:** чистая интеграция `scalping_v1` с кулдауном.

**Инструменты:** gpt-5-fast
**Acceptance:** dry-run/тестнет-прогон, ожидаемые входы/выходы в логах.

---

## Stage H — Utilities & Quick Check (0.5д)

**Цель:** операционная готовность.

**Tasks**

-   [ ] Обновить `check_orders.py`, `check_positions.py`, `close_position.py`, `main.py`.
-   [ ] `quick_check.py`: режим, рынки, плечо, доступы; по возможности ping WS; вывод стройного отчёта.

**Инструменты:** gpt-5-fast
**Acceptance:** `python quick_check.py` проходит.

---

## Stage I — Tests & CI (0.5–1д)

**Цель:** воспроизводимость.

**Tasks**

-   [ ] Юниты: symbols, filters, sizing, risk
-   [ ] Интеграция: testnet place/cancel, WS поток, реконнект
-   [ ] CI: 2 прогона (USDT testnet / USDC prod-mock)

**Инструменты:** gpt-5-fast + gpt-5-high
**Acceptance:** зелёный CI, стабильные тайминги.

---

## Stage J — Deploy & Observability (0.5–1д)

**Цель:** пред-прод.

**Tasks**

-   [ ] Dockerfile/compose, лог-ротация
-   [ ] Алерты (Telegram/Email/Slack)

**Инструменты:** gpt-5-fast
**Acceptance:** запуск контейнера (testnet), алерты работают.

---

## Параллельные потоки

-   **Docs polish (опционально):** Opus 4.1 — финальный аудит README/Concept после E/F.
-   **Perf pass:** профилирование задержек, оптимизация ретраев (после D/E).

---

## Решения по моделям

-   По умолчанию: **gpt-5-fast**
-   Большие/многофайловые задачи: **gpt-5-high-fast** + **BA** + **MAX ON** (B/C)
-   Глубокая логика/риск/WS: **gpt-5-high**; аудит: **Opus 4.1** (разово, MAX ON)

---

## Контроль качества

-   **Definition of Done**: acceptance + тесты + обновлённые логи/README при необходимости
-   **Evidence pack**: дифф PR, пример лога запуска, артефакты тестов
-   **Roll-back**: feature branches, atomic commits, метки `rc1.1.stageX`

---

## What to do Now (Next 24h)

1. **Stage A (Repo Hygiene)** → BA off, gpt-5-fast → PR.
2. **Stage D (Exchange Client + TP/SL + B-lite config)** → gpt-5-high, BA on → PR.
3. **Stage F (RiskGuard)** → gpt-5-high → PR.
4. **Smoke test**: `--dry` → короткий testnet с микролотом.
5. Затем: **Stage B (full) → Stage C (full) → Stage E (WS)**.

---

## Сегодня — оперативный чек‑лист

### Stage A — Hygiene (≈30 мин)

```bash
cd BinanceBot_OLD_migration
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

mkdir -p core/legacy references_archive
mv core/trade_engine.py core/legacy/        || true
mv core/binance_api.py core/legacy/         || true
mv core/exchange_init.py core/legacy/       || true
mv core/position_manager.py core/legacy/    || true
mv core/order_utils.py core/legacy/         || true
mv core/engine_controller.py core/legacy/   || true
mv core/risk_adjuster.py core/legacy/       || true
mv core/fail_stats_tracker.py core/legacy/  || true
mv core/tp_utils.py core/legacy/            || true
mv "references from BinanceBot_V2"/* references_archive/ 2>/dev/null || true

find . -type d -name "__pycache__" -exec rm -rf {} +
rm -rf .ruff_cache .mypy_cache
echo "core/legacy/" >> .gitignore
echo "references_archive/" >> .gitignore

python main.py --dry
git add -A && git commit -m "[stage-A] chore: repo hygiene & legacy isolation" && git push
```

### Stage D — Exchange Client (+ B-lite config) (≈1 час)

**Cursor → промпт:**

```
Задача: доработка Exchange Client (Stage D) + B-lite конфиг.
1) В TradingConfig добавь поля:
   - working_type: Literal["MARK_PRICE","CONTRACT_PRICE"] = "MARK_PRICE"
   - tp_order_style: Literal["limit","market"] = "limit"
2) В create_stop_loss_order / create_take_profit_order:
   - всегда добавляй params["reduceOnly"]=True
   - всегда добавляй params["workingType"]=config.working_type
   - TP: если tp_order_style=="market" → type="TAKE_PROFIT_MARKET", price=None, params["stopPrice"]=tp
         иначе → type="TAKE_PROFIT", price=tp, params["stopPrice"]=tp
3) Ничего вне этих функций не трогать. Покажи DIFF и обнови docstring.
Acceptance: интеграционный тест (testnet) ставит SL и TP обоих стилей без ошибок;
в логах видны workingType и reduceOnly.
```

**Терминал:**

```bash
git checkout -b feat/stage-d-exchange
pytest -q || true
git add -A && git commit -m "[stage-D] feat: TP/SL parametrization + workingType" && git push
```

### Stage F — RiskGuard (≈1 час)

**Cursor → промпт:**

```
Создай core/risk_guard.py и внедри RiskGuard.
Требования:
- class RiskGuard(config, logger) c полями sl_streak, daily_loss, max_sl_streak(getattr(config, 'max_sl_streak',3))
- can_open_position() -> tuple[bool,str]: блок по streak и по daily_drawdown_pct
- В точке входа перед открытием позиции: спросить guard, при False — лог и отказ от входа
- Юнит-тесты: 3 подряд SL → блок; превышение daily_drawdown_pct → блок
Покажи DIFF.
```

**Терминал:**

```bash
git checkout -b feat/stage-f-riskguard
pytest -q
git add -A && git commit -m "[stage-F] feat: RiskGuard + integration & tests" && git push
```

### Smoke test (сегодня)

```bash
# DRY
python main.py --dry --log-level=info
# затем короткий testnet прогон с микролотом; убедиться, что SL/TP ставятся по конфигурации
```
