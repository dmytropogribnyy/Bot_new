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

## Execution Order (Safety-first)

1. Stage A — Repo Hygiene
2. Stage D — Exchange Client (B-lite config: `tp_order_style`, `working_type`)
3. Stage F — Risk & Sizing (RiskGuard)
4. Testnet smoke-test
5. Stage B — Unified Config (full)
6. Stage C — Symbols & Markets (full)
7. Stage E — WebSocket
8. Stage P0–P5 — GPT Perspectives Integration
9. Stage G/H/I/J

---

## Stage D — Exchange Client (+ B-lite config) — Пример кода

**Задача:** добавить поля `working_type` и `tp_order_style` в `TradingConfig`, обновить функции создания SL/TP.

```python
class TradingConfig(BaseModel):
    working_type: Literal["MARK_PRICE","CONTRACT_PRICE"] = "MARK_PRICE"
    tp_order_style: Literal["limit","market"] = "limit"

def create_stop_loss_order(symbol, sl_price):
    params = {
        "reduceOnly": True,
        "workingType": config.working_type
    }
    return client.create_order(
        symbol=symbol,
        type="STOP_MARKET",
        side="SELL",
        stopPrice=sl_price,
        params=params
    )

def create_take_profit_order(symbol, tp_price):
    params = {
        "reduceOnly": True,
        "workingType": config.working_type,
        "stopPrice": tp_price
    }
    order_type = "TAKE_PROFIT_MARKET" if config.tp_order_style == "market" else "TAKE_PROFIT"
    price_arg = None if order_type == "TAKE_PROFIT_MARKET" else tp_price
    return client.create_order(
        symbol=symbol,
        type=order_type,
        side="SELL",
        price=price_arg,
        params=params
    )
```

**Acceptance:** интеграционный тест на testnet ставит SL и TP обоих стилей, логи содержат `workingType` и `reduceOnly`.

---

## Stage F — RiskGuard — Пример кода

```python
class RiskGuard:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.sl_streak = 0
        self.daily_loss = 0.0
        self.max_sl_streak = getattr(config, 'max_sl_streak', 3)

    def can_open_position(self):
        if self.sl_streak >= self.max_sl_streak:
            return False, "Max SL streak reached"
        if self.daily_loss >= self.config.daily_drawdown_pct:
            return False, "Daily drawdown limit reached"
        return True, "OK"
```

**Acceptance:** тесты на 3 подряд SL и превышение дневного лимита блокируют вход.

---

## Stage P0–P5 — GPT Perspectives Integration — Ключевые детали

-   P0: `strategy.tier`, секции risk/orders/execution/compliance в конфиге, audit.jsonl.
-   P1: Авто-rationale для действий, формат JSON.
-   P2: RiskGuard++ с tier-зависимыми лимитами.
-   P3: Автодеградация WS→REST при сбоях.
-   P4: Audit trail с цепочкой sha256.
-   P5: Playbooks для инцидентов (`/playbook`).

**Acceptance:** все пункты в тестах; при старте в логах карточка сборки (commit hash, tier, лимиты).

---

Остальные стадии (A, B, C, E, G, H, I, J) остаются без изменений, но с учётом кода и требований из Final Concept RC1.1.

---

# Appendix — Implementation details & code scaffolds

> Ниже — **конкретные заготовки кода** и команды для быстрых PR по Stage A/D/F и P‑блокам (Perspectives). Все сниппеты минимальны и предназначены для встраивания без ломки текущей структуры. Названия модулей можно адаптировать под фактические пути.

## Stage A — Repo Hygiene (команды)

```bash
# Стандартизация окружения
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt || true

# Изоляция легаси
mkdir -p core/legacy references_archive
mv core/trade_engine.py core/legacy/        2>/dev/null || true
mv core/binance_api.py core/legacy/         2>/dev/null || true
mv core/exchange_init.py core/legacy/       2>/dev/null || true
mv core/position_manager.py core/legacy/    2>/dev/null || true
mv core/order_utils.py core/legacy/         2>/dev/null || true
mv core/engine_controller.py core/legacy/   2>/dev/null || true
mv core/risk_adjuster.py core/legacy/       2>/dev/null || true
mv core/fail_stats_tracker.py core/legacy/  2>/dev/null || true
mv core/tp_utils.py core/legacy/            2>/dev/null || true

# Чистка кешей
find . -type d -name "__pycache__" -exec rm -rf {} +
rm -rf .ruff_cache .mypy_cache

echo "core/legacy/"        >> .gitignore
echo "references_archive/" >> .gitignore
```

---

## Stage B — Unified Config (код)

`core/config.py`

```python
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Optional
import os

QuoteCoin = Literal["USDT", "USDC"]
WorkingType = Literal["MARK_PRICE", "CONTRACT_PRICE"]
TPStyle = Literal["limit", "market"]

class TradingConfig(BaseModel):
    TESTNET: bool = Field(default=True)
    QUOTE_COIN: Optional[QuoteCoin] = Field(default=None)
    SETTLE_COIN: str = Field(default="USDC")

    LEVERAGE_DEFAULT: int = 5
    RISK_PER_TRADE_PCT: float = 0.005
    DAILY_DRAWDOWN_PCT: float = 0.03
    MAX_CONCURRENT_POSITIONS: int = 2

    working_type: WorkingType = "MARK_PRICE"
    tp_order_style: TPStyle = "limit"

    max_sl_streak: int = 3

    @property
    def resolved_quote_coin(self) -> QuoteCoin:
        # Автоподстановка USDT для тестнета, иначе USDC
        if self.TESTNET and not self.QUOTE_COIN:
            return "USDT"
        return self.QUOTE_COIN or "USDC"

    @classmethod
    def from_env(cls) -> "TradingConfig":
        def getenv_bool(k: str, default: bool) -> bool:
            v = os.getenv(k)
            return default if v is None else v.lower() in {"1","true","yes","y"}
        return cls(
            TESTNET=getenv_bool("TESTNET", True),
            QUOTE_COIN=os.getenv("QUOTE_COIN") or None,
            SETTLE_COIN=os.getenv("SETTLE_COIN", "USDC"),
            LEVERAGE_DEFAULT=int(os.getenv("LEVERAGE_DEFAULT", 5)),
            RISK_PER_TRADE_PCT=float(os.getenv("RISK_PER_TRADE_PCT", 0.005)),
            DAILY_DRAWDOWN_PCT=float(os.getenv("DAILY_DRAWDOWN_PCT", 0.03)),
            MAX_CONCURRENT_POSITIONS=int(os.getenv("MAX_CONCURRENT_POSITIONS", 2)),
            working_type=(os.getenv("WORKING_TYPE") or "MARK_PRICE"),
            tp_order_style=(os.getenv("TP_ORDER_STYLE") or "limit"),
            max_sl_streak=int(os.getenv("MAX_SL_STREAK", 3)),
        )
```

`tests/test_config.py`

```python
from core.config import TradingConfig

def test_auto_quote_coin_testnet():
    cfg = TradingConfig(TESTNET=True, QUOTE_COIN=None)
    assert cfg.resolved_quote_coin == "USDT"

def test_auto_quote_coin_prod_default_usdc():
    cfg = TradingConfig(TESTNET=False, QUOTE_COIN=None)
    assert cfg.resolved_quote_coin == "USDC"
```

---

## Stage C — Symbols & Markets (код)

`core/symbol_utils.py`

```python
def perp_symbol(base: str, coin: str) -> str:
    base = base.upper(); coin = coin.upper()
    return f"{base}/{coin}:{coin}"
```

`core/symbol_manager.py`

```python
from typing import Iterable, Dict, Any, List

def filter_usdsm_contracts(markets: Dict[str, Any], settle_coin: str, quote_coin: str) -> List[str]:
    result = []
    for m in markets.values():
        if not m.get("contract"):
            continue
        if m.get("settle") == settle_coin or m.get("quote") == quote_coin:
            result.append(m["symbol"])  # формат CCXT, например "BTC/USDC:USDC"
    return sorted(set(result))

def default_symbols(coin: str) -> List[str]:
    bases = ["BTC", "ETH", "BNB", "SOL", "ADA"]
    return [f"{b}/{coin}:{coin}" for b in bases]
```

`tests/test_symbols.py`

```python
from core.symbol_utils import perp_symbol

def test_perp_symbol():
    assert perp_symbol("btc","usdc") == "BTC/USDC:USDC"
```

---

## Stage D — Exchange Client (+ TP/SL параметризация)

`core/exchange_client.py` (фрагменты)

```python
from typing import Optional, Dict, Any

async def create_stop_loss_order(exchange, symbol: str, side: str, qty: float, stop_price: float, cfg) -> Dict[str, Any]:
    params = {
        "reduceOnly": True,
        "workingType": cfg.working_type,
        "stopPrice": float(stop_price),
    }
    order_type = "STOP_MARKET"
    price = None
    return await exchange.create_order(symbol, order_type, side, qty, price, params)

async def create_take_profit_order(exchange, symbol: str, side: str, qty: float, tp_price: float, cfg) -> Dict[str, Any]:
    params = {
        "reduceOnly": True,
        "workingType": cfg.working_type,
        "stopPrice": float(tp_price),
    }
    if cfg.tp_order_style == "market":
        order_type = "TAKE_PROFIT_MARKET"; price = None
    else:
        order_type = "TAKE_PROFIT"; price = float(tp_price)
    return await exchange.create_order(symbol, order_type, side, qty, price, params)
```

`tests/test_tp_sl.py`

```python
import types
import pytest
from core.config import TradingConfig
from core.exchange_client import create_stop_loss_order, create_take_profit_order

class DummyEx:
    async def create_order(self, symbol, order_type, side, amount, price, params):
        return {"symbol": symbol, "type": order_type, "side": side, "amount": amount, "price": price, "params": params}

@pytest.mark.asyncio
async def test_tp_styles():
    ex = DummyEx(); cfg = TradingConfig()
    o1 = await create_take_profit_order(ex, "BTC/USDC:USDC", "sell", 0.01, 50000, cfg)
    assert o1["type"] == "TAKE_PROFIT" and o1["price"] == 50000
    cfg.tp_order_style = "market"
    o2 = await create_take_profit_order(ex, "BTC/USDC:USDC", "sell", 0.01, 50000, cfg)
    assert o2["type"] == "TAKE_PROFIT_MARKET" and o2["price"] is None

@pytest.mark.asyncio
async def test_sl_params():
    ex = DummyEx(); cfg = TradingConfig(working_type="MARK_PRICE")
    o = await create_stop_loss_order(ex, "BTC/USDC:USDC", "sell", 0.01, 49000, cfg)
    assert o["params"]["reduceOnly"] is True
    assert o["params"]["workingType"] == "MARK_PRICE"
```

---

## Stage F — Risk & Sizing (код)

`core/risk_guard.py`

```python
from dataclasses import dataclass

@dataclass
class RiskState:
    sl_streak: int = 0
    daily_loss: float = 0.0  # в quote-коине

class RiskGuard:
    def __init__(self, config, logger):
        self.cfg = config
        self.log = logger
        self.s = RiskState()

    def record_sl(self, loss_quote: float) -> None:
        self.s.sl_streak += 1
        self.s.daily_loss += abs(loss_quote)

    def record_tp(self, profit_quote: float) -> None:
        # сбрасываем серию при профите
        self.s.sl_streak = 0
        self.s.daily_loss = max(0.0, self.s.daily_loss - abs(profit_quote) * 0.0)

    def can_open_position(self) -> tuple[bool, str]:
        if self.s.sl_streak >= self.cfg.max_sl_streak:
            return False, f"SL streak reached: {self.s.sl_streak}/{self.cfg.max_sl_streak}"
        # daily_loss проверяется относительно эквити — передайте сюда актуальный баланс при вызове, если нужно
        # Можно вынести в отдельный метод с dependency на Portfolio/Account
        return True, "ok"
```

`tests/test_risk_guard.py`

```python
from core.config import TradingConfig
from core.risk_guard import RiskGuard

class DummyLogger:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass

def test_streak_blocks_after_3():
    g = RiskGuard(TradingConfig(max_sl_streak=3), DummyLogger())
    for _ in range(3):
        g.record_sl(10)
    ok, reason = g.can_open_position()
    assert not ok and "SL streak" in reason
```

---

## Stage E — WebSocket/User Data (скелет)

`core/ws_client.py`

```python
import asyncio, aiohttp, time, json

# Примерный скелет: получение listenKey и keepalive через REST, события — через сокет
async def get_listen_key(http, api_base, headers) -> str:
    async with http.post(f"{api_base}/fapi/v1/listenKey", headers=headers) as r:
        data = await r.json()
        return data["listenKey"]

async def keepalive(http, api_base, headers, listen_key):
    while True:
        await asyncio.sleep(25*60)
        await http.put(f"{api_base}/fapi/v1/listenKey?listenKey={listen_key}", headers=headers)

async def stream_user_data(ws_url, listen_key, on_event):
    url = f"{ws_url}/ws/{listen_key}"
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(url, heartbeat=30) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await on_event(json.loads(msg.data))
```

---

## P4 — Compliance/Audit (append-only JSONL с хеш-цепочкой)

`core/audit_logger.py`

```python
import json, hashlib, os, time
from typing import Optional

class AuditLogger:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def _last_hash(self) -> str:
        try:
            with open(self.path, "rb") as f:
                last = None
                for line in f: last = line
                if not last: return "0"*64
                obj = json.loads(last)
                return obj.get("hash", "0"*64)
        except FileNotFoundError:
            return "0"*64

    def write(self, payload: dict) -> None:
        prev = self._last_hash()
        body = {"ts": time.time(), "prev_hash": prev, **payload}
        raw = json.dumps(body, sort_keys=True).encode()
        h = hashlib.sha256(raw).hexdigest()
        body["hash"] = h
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(body, ensure_ascii=False) + "
")
```

Пример использования:

```python
from core.audit_logger import AuditLogger

audit = AuditLogger("logs/audit.jsonl")
audit.write({"action":"order.place", "symbol":"BTC/USDC:USDC", "why":"signal=breakout; rr>=1.8"})
```

---

## P1 — Decision Rationale (структура записи)

```json
{
    "ts": 1723286400.123,
    "action": "order.place",
    "lens": ["Trader", "Risk"],
    "symbol": "BTC/USDC:USDC",
    "side": "buy",
    "size": 0.01,
    "why": "breakout>ATR; trend=up; risk_ok",
    "config": {
        "tp_style": "limit",
        "working_type": "MARK_PRICE",
        "risk": { "per_trade_pct": 0.5, "daily_dd_pct": 3 }
    }
}
```

---

## Stage H — quick_check (скелет)

`tools/quick_check.py`

```python
from core.config import TradingConfig

def main():
    cfg = TradingConfig.from_env()
    print("Mode:", "TESTNET" if cfg.TESTNET else "PROD", cfg.resolved_quote_coin)
    print("Leverage:", cfg.LEVERAGE_DEFAULT)
    print("TP style:", cfg.tp_order_style, "WorkingType:", cfg.working_type)

if __name__ == "__main__":
    main()
```

---

## Cursor промпты (готовые блоки для Stage D/F)

**Stage D**

```
Задача: доработка Exchange Client.
1) В TradingConfig добавь поля working_type и tp_order_style (дефолты, как в docs).
2) В create_stop_loss_order / create_take_profit_order всегда проставляй reduceOnly и workingType; TP: market → TAKE_PROFIT_MARKET.
3) Покажи DIFF, не трогать остальной код.
```

**Stage F**

```
Создай core/risk_guard.py с классом RiskGuard(config, logger): поля sl_streak, daily_loss; методы record_sl/record_tp/can_open_position.
Интегрируй проверку в точке входа, добавь юнит-тесты.
```

---

> Готов подключить дополнительные сниппеты (sizing формула, расчёт qty от эквити/ATR, graceful shutdown-хендлер) — скажи, куда именно встроить в текущем дереве проекта.
