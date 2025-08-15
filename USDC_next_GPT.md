окей — вот «финальный план» под одного бота: что именно меняем, зачем, и где правим код. Сразу даю готовые вставки. В конце — завершённый блок по fees (включая авто‑настройку).

1. Цели и принципы

Стабильность: без дублей исполнений, чистая уборка ордеров/позиций.

Прибыль: TP/SL после комиссий → net‑плюс; BE после TP1; адекватные TP‑пакеты.

Контроль входов: фильтры (спред/айсберг/импульс), «вселенная» символов.

Простота запуска: автоподстройка комиссий и порогов под testnet/prod/BNB.

2. .env — итоговая конфигурация (один бот)

# ================================

# MODES

# ================================

BINANCE_TESTNET=true
DRY_RUN=false
ENABLE_WEBSOCKET=true
LOG_LEVEL=INFO

# ================================

# EXECUTION

# ================================

WORKING_TYPE=CONTRACT_PRICE # или MARK_PRICE; единообразно на TP/SL
SL_ORDER_TYPE=STOP_MARKET
TP_ORDER_TYPE=TAKE_PROFIT_MARKET
TIME_IN_FORCE=GTC
REDUCE_ONLY=true

# ================================

# POSITIONS / RISK

# ================================

MAX_POSITIONS=1
MAX_CONCURRENT_POSITIONS=1
BASE_POSITION_SIZE_USDT=20.0
MIN_POSITION_SIZE_USDT=20.0
STOP_LOSS_PERCENT=0.8
TAKE_PROFIT_PERCENT=2.0
TRADING_DEPOSIT=400
BALANCE_PERCENTAGE=0.95
MAX_CAPITAL_UTILIZATION_PCT=0.50
MAX_MARGIN_PERCENT=0.40
MAX_SLIPPAGE_PCT=0.02

# ================================

# MULTI-TP (будет переопределено адаптивным пакетом)

# ================================

ENABLE_MULTIPLE_TP=true
TP_LEVELS='[{"percent":0.9,"size":0.4},{"percent":1.8,"size":0.3},{"percent":2.7,"size":0.3}]'
MIN_TICK_PCT=0.01 # минимум 1 тик между TP-уровнями

# ================================

# UNIVERSE & ENTRY FILTERS

# ================================

QUOTE_COIN=USDC
UNIVERSE_SIZE=10
STICKY_UNIVERSE=true
ENTRY_COOLDOWN_SECONDS=120
MAX_HOURLY_TRADE_LIMIT=0
SPREAD_MAX_PCT=0.03
BLOCK_IF_OPPOSITE_ICEBERG=true
ICEBERG_MIN_SIZE_USD=20000
ALLOWLIST=BTCUSDC,ETHUSDC,SOLUSDC,BNBUSDC,XRPUSDC,LTCUSDC,BCHUSDC,AVAXUSDC,LINKUSDC,DOTUSDC
BLOCKLIST=

# ================================

# FEE AUTO-TUNE (в долях)

# ================================

AUTO_FEES=true
DEFAULT_TAKER_FEE_PCT=0.0004 # prod базово; testnet используем те же
DEFAULT_MAKER_FEE_PCT=0.0000 # USDC-M promo = 0
BNB_DISCOUNT_PCT=0.10
BNB_MIN_BALANCE_FUT=0.10
FORCE_PAY_FEES_WITH_BNB=auto # auto|true|false

# Эти три можно оставить пустыми — бот рассчёт подставит сам

MIN_TP_PROFIT_USDT=
MIN_TP_PROFIT_PCT=
BE_PLUS_PCT=

# ================================

# WEBSOCKET

# ================================

WS_RECONNECT_INTERVAL=5
WS_HEARTBEAT_INTERVAL=30
ALLOW_SHORTS=true

# ================================

# LEGACY

# ================================

TP_ORDER_STYLE=market

3. Загрузка конфига (core/config.py)

Добавьте чтение новых ключей/опционалов:

# фрагменты внутри TradingConfig.from_env()

# universe & filters

self.quote_coin = env.get("QUOTE_COIN", "USDC")
self.universe_size = env.get_int("UNIVERSE_SIZE", 10)
self.sticky_universe = env.get_bool("STICKY_UNIVERSE", True)
self.spread_max_pct = env.get_float("SPREAD_MAX_PCT", 0.03)
self.block_if_opposite_iceberg = env.get_bool("BLOCK_IF_OPPOSITE_ICEBERG", True)
self.iceberg_min_size_usd = env.get_float("ICEBERG_MIN_SIZE_USD", 20000)
self.allowlist = [s for s in env.get("ALLOWLIST","").split(",") if s]
self.blocklist = [s for s in env.get("BLOCKLIST","").split(",") if s]
self.entry_cooldown_seconds = env.get_int("ENTRY_COOLDOWN_SECONDS", 120)

# multi-TP / ticks

self.enable_multiple_tp = env.get_bool("ENABLE_MULTIPLE_TP", True)
self.tp_levels = env.get_json("TP_LEVELS", default=[{"percent":0.9,"size":0.4},{"percent":1.8,"size":0.3},{"percent":2.7,"size":0.3}])
self.min_tick_pct = env.get_float("MIN_TICK_PCT", 0.01)

# fees autotune

self.auto_fees = env.get_bool("AUTO_FEES", True)
self.default_taker_fee_pct = env.get_float("DEFAULT_TAKER_FEE_PCT", 0.0004)
self.default_maker_fee_pct = env.get_float("DEFAULT_MAKER_FEE_PCT", 0.0)
self.bnb_discount_pct = env.get_float("BNB_DISCOUNT_PCT", 0.10)
self.bnb_min_balance_fut = env.get_float("BNB_MIN_BALANCE_FUT", 0.10)
fb = env.get("FORCE_PAY_FEES_WITH_BNB", "auto").lower()
self.force_pay_fees_with_bnb = fb if fb in {"auto","true","false"} else "auto"

# thresholds (optional)

self.min_tp_profit_usdt = env.get_optional_float("MIN_TP_PROFIT_USDT")
self.min_tp_profit_pct = env.get_optional_float("MIN_TP_PROFIT_PCT")
self.be_plus_pct = env.get_optional_float("BE_PLUS_PCT")

4. Построение «вселенной» символов (core/symbol_universe.py)

Мини‑модуль для выбора 8–10 лучших тикеров на сессию.

# core/symbol_universe.py

class SymbolUniverse:
def **init**(self, exchange, cfg, logger):
self.ex = exchange
self.cfg = cfg
self.log = logger
self.\_sticky = None

    async def build(self):
        if self.cfg.sticky_universe and self._sticky:
            return self._sticky

        # 1) получить все фьючерсы под quote (USDC)
        markets = await self.ex.load_markets()
        syms = [m for m in markets if markets[m].get("type")=="future" and m.endswith(self.cfg.quote_coin)]
        # 2) allow/block
        if self.cfg.allowlist:
            syms = [s for s in syms if s in self.cfg.allowlist]
        syms = [s for s in syms if s not in self.cfg.blocklist]

        # 3) простейший скор: ликвидность/спред (можно расширить ATR/импульс)
        scored = []
        for s in syms:
            try:
                ob = await self.ex.fetch_order_book(s, limit=10)
                best_bid = ob["bids"][0][0]; best_ask = ob["asks"][0][0]
                spread = (best_ask - best_bid) / ((best_ask + best_bid)/2)
                if spread > self.cfg.spread_max_pct/100.0:
                    continue
                scored.append((s, 1.0/spread))  # меньше спред → выше скор
            except Exception:
                continue

        scored.sort(key=lambda x: x[1], reverse=True)
        universe = [s for s,_ in scored[:self.cfg.universe_size]]
        self.log.info(f"[UNIVERSE] selected={universe}")
        if self.cfg.sticky_universe:
            self._sticky = universe
        return universe

Интеграция: в OrderManager.**init** создать self.universe = SymbolUniverse(exchange, config, logger), а в торговом цикле опрашивать await self.universe.build() и работать только с этим списком.

5. Входные фильтры (спред / айсберг / кулдауны)

Спред: уже в SymbolUniverse.build() (отбраковка широкого спреда).

Айсберг: при получении depth‑обновлений — если против направления стоит крупный пассивный объём (>= ICEBERG_MIN_SIZE_USD) и не «съедается» — пропускаем вход.

Кулдаун: словарь last_entry_at[symbol] → запрещаем новый вход, пока не прошло ENTRY_COOLDOWN_SECONDS.

6. Protective orders: TP‑уровни и тик‑разводка

В place_protective_orders() перед расчётом цен:

def \_round_to_tick_pct(pct: float, tick: float) -> float:
return round(pct / tick) \* tick

def \_separate_ticks(tp_pack, tick):
rounded = []
last = -1e9
for lvl in tp_pack:
p = \_round_to_tick_pct(lvl["percent"], tick)
if p <= last:
p = \_round_to_tick_pct(last + tick, tick)
rounded.append({"percent": p, "size": lvl["size"]})
last = p
return rounded

tp_pack = \_separate_ticks(tp_pack, self.config.min_tick_pct)

Создание TP/SL — обязательно stopPrice, reduceOnly=True, params={"workingType": self.config.working_type}.

await self.create_order(
symbol=symbol,
side=exit_side, # противоположно позиции
order_type=self.config.tp_order_type, # TAKE_PROFIT_MARKET
qty=qty_tp1,
stop_price=tp1_price, # ВАЖНО: stopPrice
working_type=self.config.working_type, # MARK_PRICE/CONTRACT_PRICE
reduce_only=True,
time_in_force=self.config.time_in_force
)

7. BE после TP1

В обработчике fill TP1:

be_plus = float(self.config.be_plus_pct or 0.001) # 0.10% если автотюн не задал
entry = pos.entry_avg_price
new_sl = entry*(1+be_plus) if pos.side=="buy" else entry*(1-be_plus)

await self.cancel_symbol_orders(symbol, kinds=["SL"])
await self.create_order(
symbol=symbol,
side=("sell" if pos.side=="buy" else "buy"),
order_type=self.config.sl_order_type, # STOP_MARKET
qty=pos.remaining_qty(),
stop_price=new_sl,
working_type=self.config.working_type,
reduce_only=True,
time_in_force=self.config.time_in_force
)
self.logger.info(f"[BE] Reset SL to BE+{be_plus\*100:.2f}% -> {new_sl:.6f}")

8. Дедупликация исполнений (WS events)
   from collections import deque

# **init**

self.\_processed_events = deque(maxlen=500)

def \_dedupe_event(self, event) -> bool:
key = f"{event.orderId}|{event.clientOrderId}|{event.lastFilledQty}|{event.lastFilledPrice}"
if key in self.\_processed_events:
return True
self.\_processed_events.append(key)
return False

# в обработчике ORDER_TRADE_UPDATE:

if self.\_dedupe_event(evt):
return

9. PnL‑Guard (чистая прибыль после комиссий)

Файл core/pnl_guard.py (как мы уже давали ранее — вставьте без изменений).
В обработчике любого закрытия/частичного закрытия:

ctx = CloseContext(
symbol=symbol,
side=pos.side,
entry_avg_price=pos.entry_avg_price,
exit_price=fill_price, # из события сделки (не entry!)
qty=fill_qty,
used_margin_usdt=pos.initial_margin_usdt \* (fill_qty / max(pos.total_qty, 1e-9)),
was_tp=is_tp, was_sl=is_sl, was_autoprofit=is_bonus,
baseline_exit_price=pos.autoprofit_baseline_exit_price if is_bonus else None
)
if is_tp: self.pnl_guard.check_tp(ctx)
if is_sl:
expected_loss = pos.expected_sl_loss_usdt_for(fill_qty)
self.pnl_guard.check_sl(ctx, expected_loss)
if is_bonus: self.pnl_guard.check_autoprofit(ctx)

10. Логирование (core/unified_logger.py)

Исправьте шаблоны, чтобы не было «@ market» для TP/SL. Логируйте тип и trigger:

Created order: ETHUSDC buy 0.042 @ TAKE_PROFIT_MARKET trigger=MARK_PRICE stopPrice=4351.56 reduceOnly=True
Fill: ETHUSDC TP1 0.021 @ 4351.60 (netPnL=$0.12, fees=$0.03)

11. Мини‑тесты (pytest)

Tick separation — TP1/TP2 после округления не совпадают.

Dedup — второй идентичный fill подавляется.

PnL guard TP — нет‑прибыль ≥ порога.

(Скелеты тестов я уже кидал; подстройте импорты под ваш проект.)

12. Симулятор (опционально)

Мы уже прогоняли мини‑сим и получили ориентиры:
~$0.06–0.07 / сделка, ~5–6 сделок/час → $0.30–0.42/час для одного бота без агрессивных фильтров.
С динамической «вселенной» и фильтрами ожидаем $0.45–0.65/час (консервативно).

13. Авто‑настройка комиссий и порогов (fees) — финальный блок
    13.1 Новый модуль core/fees_autotune.py
    from dataclasses import dataclass

@dataclass
class FeeResult:
taker_fee_pct: float
maker_fee_pct: float
pay_fees_with_bnb: bool
min_tp_profit_usdt: float
min_tp_profit_pct: float
be_plus_pct: float
reason: str

async def detect_bnb_on_futures(exchange, min_bnb: float) -> bool:
try:
bal = await exchange.fetch_balance(params={"type": "future"})
bnb = bal.get("BNB") or {}
total = float(bnb.get("total") or 0.0)
return total >= min_bnb
except Exception:
return False

def compute*thresholds(notional_usdt: float, taker_fee_pct: float) -> tuple[float,float,float]:
roundtrip_fee = notional_usdt * (taker*fee_pct * 2.0)
min_tp_usd = max(0.18, round(roundtrip_fee \* 1.10, 2)) # +10% буфер
min_tp_pct = 0.002 # 0.20% от маржи по умолчанию
be_plus_pct = 0.001 # 0.10%
return min_tp_usd, min_tp_pct, be_plus_pct

async def fees_autotune(exchange, cfg, logger, \*, base_position_usdt: float, leverage: float) -> FeeResult:
taker = float(cfg.default_taker_fee_pct)
maker = float(cfg.default_maker_fee_pct)

    # Определяем оплату BNB
    if cfg.force_pay_fees_with_bnb == "true":
        pay_bnb = True; reason = "FORCED_TRUE"
    elif cfg.force_pay_fees_with_bnb == "false":
        pay_bnb = False; reason = "FORCED_FALSE"
    else:
        if cfg.testnet:
            pay_bnb = False; reason = "AUTO(TESTNET)"
        else:
            pay_bnb = await detect_bnb_on_futures(exchange, cfg.bnb_min_balance_fut)
            reason = f"AUTO({'BNB_OK' if pay_bnb else 'NO_BNB'})"

    if pay_bnb:
        taker *= (1.0 - float(cfg.bnb_discount_pct))  # -10% на taker

    notional = float(base_position_usdt) * float(leverage)
    min_tp_usd, min_tp_pct, be_plus_pct = compute_thresholds(notional, taker)

    # ручные overrides из .env (если заданы)
    if cfg.min_tp_profit_usdt is not None: min_tp_usd = float(cfg.min_tp_profit_usdt)
    if cfg.min_tp_profit_pct  is not None: min_tp_pct = float(cfg.min_tp_profit_pct)
    if cfg.be_plus_pct        is not None: be_plus_pct = float(cfg.be_plus_pct)

    logger.info(
        f"[FEES] taker={taker:.6f} maker={maker:.6f} pay_bnb={pay_bnb} "
        f"min_tp_usd={min_tp_usd:.2f} min_tp_pct={min_tp_pct*100:.3f}% be_plus={be_plus_pct*100:.3f}% ({reason})"
    )
    return FeeResult(taker, maker, pay_bnb, min_tp_usd, min_tp_pct, be_plus_pct, reason)

13.2 Вызов в main.py (или при init бота)
from core.fees_autotune import fees_autotune

# после создания exchange и загрузки config:

if config.auto_fees:
fr = await fees_autotune(exchange, config, logger,
base_position_usdt=config.base_position_size_usdt,
leverage=config.leverage_default) # Применяем
config.taker_fee_pct = fr.taker_fee_pct
config.maker_fee_pct = fr.maker_fee_pct
config.pay_fees_with_bnb = fr.pay_fees_with_bnb
config.min_tp_profit_usdt = fr.min_tp_profit_usdt
config.min_tp_profit_pct = fr.min_tp_profit_pct
config.be_plus_pct = fr.be_plus_pct
else:
logger.info("[FEES] Auto-fees disabled; using .env")

13.3 Где это «замыкается»

PnL‑Guard берёт taker*fee_pct/maker_fee_pct и пороги MIN_TP_PROFIT*\* из config.

BE опирается на be_plus_pct.

При наличии BNB в проде — автоматически снижается taker (экономия до 10%).

14. Последовательность включения (шаги)

Обновить .env (как в §2).

Внести правки в core/config.py (§3).

Добавить core/symbol_universe.py (§4) и подключить в OrderManager.

Правки OrderManager: фильтры входа (§5), тик‑разводка + правильные TP/SL параметры (§6), BE после TP1 (§7), дедуп событий (§8), PnL‑Guard вызовы (§9).

Обновить unified_logger (§10).

Добавить core/pnl_guard.py (если ещё не добавлен).

Добавить core/fees_autotune.py и вызвать автотюн в main.py (§13).

Прогнать тесты и один прогон --once на testnet; сверить логи:

TP/SL создаются как \*\_MARKET со stopPrice, reduceOnly=True, workingType — ОК

после TP1 срабатывает перенос SL → BE+

дублей «Take profit executed» нет

PnL‑guard выводит net значения и пороги

Если где‑то упрёшься в конкретную функцию/импорт, скинь файл — подгоню патч точечно под твою структуру. После стабилизации этого варианта на одном боте уже просто наращиваем: больше символов (через «вселенную»), потом несколько ботов — раздавая им разные группы тикеров.

You said:
а код от клда ниченго не надо разве ?
ChatGPT said:

Да, часть кода от Клода стоит взять, но только те пункты, которые мы уже включили в этот финальный план — остальное у нас либо уже реализовано, либо лучше сделать по-другому.

Если сравнить с его заметками, у нас в плане уже есть:

Из списка Клода, что мы уже включили:

Исправление единиц комиссий — мы сделали в AUTO_FEES (TAKER_FEE_PCT / MAKER_FEE_PCT в долях).

Правильные параметры Binance API для TP/SL (stopPrice, reduceOnly=True, workingType) — у нас в пункте 6.

PnL-Guard — добавлен в пункте 9, с порогами из авто-тюна комиссий.

Дедупликация WebSocket событий — пункт 8.

Разводка TP уровней по тикам — пункт 6 (функция \_separate_ticks).

BE упрощённый — пункт 7 (BE+ фиксированный процент).

Что у Клода ещё было, но мы решили отложить/изменить:

Пирамидинг — он хотел добавить сразу, но мы это убрали на вторую очередь, чтобы не усложнять тесты.

Упрощение BE — мы всё равно оставили чуть гибче, с возможностью задать be_plus_pct в .env или через авто-тюн.

Его SignalEngine — мы пока используем твой текущий набор сигналов, а фильтры усилили через «вселенную» и айсберги.

То есть весь полезный «код Клода» мы в этот финальный план встроили, но в более структурированном виде и с пояснениями.

## Если хочешь, я могу прямо выписать краткий diff «Клод → наш финал» по файлам, чтобы при желании быстро проверить, что ни один его важный кусок не пропущен.

## окей — добавляю «хуки» под ATR‑адаптацию и импульсный фильтр + показываю, как их подружить с текущей логикой. Всё компактно и готово к вставке.

1. Новый модуль: core/signal_engine.py

# core/signal_engine.py

from **future** import annotations
from dataclasses import dataclass
from typing import Literal, Optional, Dict, Any, List
import math

AtrMode = Literal["low", "base", "high"]

@dataclass
class AtrConfig:
len_atr: int = 14
tf: str = "1m" # таймфрейм для ATR
low_thr_pct: float = 0.6 # границы режимов как % от базового ATR
high_thr_pct: float = 1.4

@dataclass
class ImpulseConfig:
tf: str = "1m"
lookback: int = 12 # последние N баров
min_accel: float = 1.5 # минимальный коэффициент ускорения
min_body_pct: float = 0.05 # % тела свечи (от цены) для «импульса»

class SignalEngine:
def **init**(self, exchange, cfg, logger):
self.ex = exchange
self.cfg = cfg
self.log = logger
self.atr_cfg = AtrConfig()
self.imp_cfg = ImpulseConfig()

    # ---------- utils ----------
    @staticmethod
    def _true_range(h: float, l: float, pc: float) -> float:
        return max(h - l, abs(h - pc), abs(l - pc))

    @staticmethod
    def _ema(seq: List[float], n: int) -> float:
        if not seq: return 0.0
        k = 2 / (n + 1)
        ema = seq[0]
        for x in seq[1:]:
            ema = x * k + ema * (1 - k)
        return ema

    # ---------- ATR mode ----------
    async def get_atr_value(self, symbol: str, tf: Optional[str] = None, n: Optional[int] = None) -> float:
        tf = tf or self.atr_cfg.tf
        n = n or self.atr_cfg.len_atr
        # ccxt: fetch_ohlcv(symbol, timeframe, since=None, limit)
        ohlcv = await self.ex.fetch_ohlcv(symbol, timeframe=tf, limit=n+1)
        trs = []
        prev_close = ohlcv[0][4]
        for ts, o, h, l, c, v in ohlcv[1:]:
            trs.append(self._true_range(h, l, prev_close))
            prev_close = c
        atr = sum(trs) / len(trs) if trs else 0.0
        return atr

    async def get_atr_mode(self, symbol: str) -> AtrMode:
        # Базовый ATR берём из «скользящей базы» по 1м, затем сравниваем текущий ATR с базой
        atr_curr = await self.get_atr_value(symbol, tf=self.atr_cfg.tf, n=self.atr_cfg.len_atr)
        # Можно хранить базу в КХ или взять EMA(TR) как базу
        ohlcv = await self.ex.fetch_ohlcv(symbol, timeframe=self.atr_cfg.tf, limit=self.atr_cfg.len_atr + 25)
        trs = []
        prev_close = ohlcv[0][4]
        for _, o, h, l, c, v in ohlcv[1:]:
            trs.append(self._true_range(h, l, prev_close))
            prev_close = c
        base = self._ema(trs, max(10, self.atr_cfg.len_atr)) or 1e-9
        ratio = atr_curr / base

        if ratio <= self.atr_cfg.low_thr_pct:
            return "low"
        if ratio >= self.atr_cfg.high_thr_pct:
            return "high"
        return "base"

    # ---------- импульсный фильтр ----------
    async def pass_impulse_filter(self, symbol: str, side: Literal["buy","sell"]) -> bool:
        tf = self.imp_cfg.tf
        lb = self.imp_cfg.lookback
        ohlcv = await self.ex.fetch_ohlcv(symbol, timeframe=tf, limit=lb)
        if len(ohlcv) < lb: return False

        closes = [c[4] for c in ohlcv]
        rets = [ (closes[i]/closes[i-1] - 1.0) for i in range(1, len(closes)) ]
        # «ускорение» = средняя доходность последних k баров / средняя по всему окну
        k = max(3, lb // 4)
        tail = sum(rets[-k:]) / k
        avg  = (sum(rets) / len(rets)) if rets else 0.0
        accel = (abs(tail) / (abs(avg) + 1e-9)) if avg != 0 else (abs(tail) / 1e-6)

        # фильтр «тело свечи» на последней свече
        o, h, l, c = ohlcv[-1][1:5]
        body_pct = abs(c - o) / max((h + l) / 2, 1e-9)

        # направление: для buy ждём положительное ускорение; для sell — отрицательное
        dir_ok = (tail > 0) if side == "buy" else (tail < 0)
        accel_ok = accel >= self.imp_cfg.min_accel
        body_ok  = body_pct >= (self.imp_cfg.min_body_pct / 100.0)

        self.log.debug(f"[IMPULSE] {symbol} side={side} accel={accel:.2f} tail={tail:.5f} avg={avg:.5f} body%={body_pct*100:.3f}")
        return dir_ok and accel_ok and body_ok

    # ---------- адаптивный пакет TP/SL ----------
    async def get_adaptive_tp_sl(self, symbol: str) -> Dict[str, Any]:
        mode = await self.get_atr_mode(symbol)
        if mode == "low":
            sl_pct = self.cfg.sl_pct_low
            tp_pack = self.cfg.tp_pack_low
        elif mode == "high":
            sl_pct = self.cfg.sl_pct_high
            tp_pack = self.cfg.tp_pack_high
        else:
            sl_pct = self.cfg.sl_pct_base
            tp_pack = self.cfg.tp_pack_base
        return {"mode": mode, "sl_pct": sl_pct, "tp_pack": tp_pack}

2. Интеграция в твой менеджер ордеров
   2.1 Создаём движок сигналов

# в OrderManager.**init**

from core.signal_engine import SignalEngine
self.signal_engine = SignalEngine(self.exchange, self.config, self.logger)

2.2 Перед входом — импульсный фильтр

# там, где у тебя принимается решение о входе

side = "buy" if signal.is_long else "sell"

# импульсный фильтр (мягко: если не проходит — пропускаем вход)

ok_impulse = await self.signal_engine.pass_impulse_filter(symbol, side)
if not ok_impulse:
self.logger.debug(f"[ENTRY-BLOCK] {symbol} impulse filter failed, side={side}")
return # или понизить приоритет/скажет очереди «пропустить»

2.3 Адаптивные TP/SL (подменяем пакет)

# до place_protective_orders()

ad = await self.signal_engine.get_adaptive_tp_sl(symbol)
tp_pack = ad["tp_pack"]
sl_pct = ad["sl_pct"]
mode = ad["mode"]

# твой существующий код расчёта уровней:

# 1) развести tp_pack по тикам (мы уже добавили \_separate_ticks)

tp_pack = \_separate_ticks(tp_pack, self.config.min_tick_pct)

# 2) из sl_pct сделать stopPrice

if pos.side == "buy":
sl_price = pos.entry_avg_price _ (1 - sl_pct/100.0)
else:
sl_price = pos.entry_avg_price _ (1 + sl_pct/100.0)

self.logger.info(f"[ADAPTIVE] {symbol} mode={mode} SL%={sl_pct} TP={tp_pack}")

# дальше — выставляешь TP/SL как обычно (TAKE_PROFIT_MARKET / STOP_MARKET со stopPrice)

3. Мини‑тест быстрым чек‑листом

При спокойном рынке (низкая вола) get_atr_mode чаще выдаёт "low" → SL/TP сужаются согласно sl_pct_low / tp_pack_low.

При прыжках — "high" → SL шире, TP дальше.

При входе против импульса pass_impulse_filter ~ложит вход (должно снижать число «пустых» сделок).

4. Параметры в .env для этих хуков (если хочешь тонко настроить)

(Опционально; значения по умолчанию захардкожены в классе, но можно вынести в ENV.)

# --- ATR hooks (опционально) ---

ATR_TF=1m
ATR_LEN=14
ATR_LOW_THR_PCT=0.6
ATR_HIGH_THR_PCT=1.4

# --- Impulse hooks (опционально) ---

IMPULSE_TF=1m
IMPULSE_LOOKBACK=12
IMPULSE_MIN_ACCEL=1.5
IMPULSE_MIN_BODY_PCT=0.05

И чтение в SignalEngine.**init**, если вынесешь:

self.atr_cfg = AtrConfig(
len_atr=int(cfg.get("ATR_LEN", 14)),
tf=cfg.get("ATR_TF","1m"),
low_thr_pct=float(cfg.get("ATR_LOW_THR_PCT",0.6)),
high_thr_pct=float(cfg.get("ATR_HIGH_THR_PCT",1.4)),
)
self.imp_cfg = ImpulseConfig(
tf=cfg.get("IMPULSE_TF","1m"),
lookback=int(cfg.get("IMPULSE_LOOKBACK",12)),
min_accel=float(cfg.get("IMPULSE_MIN_ACCEL",1.5)),
min_body_pct=float(cfg.get("IMPULSE_MIN_BODY_PCT",0.05)),
)

5. Где это стыкуется с fees (финал)

fees*autotune остаётся как есть (он задаёт taker_fee_pct, maker_fee_pct, MIN_TP_PROFIT*\*, BE_PLUS_PCT).

Наш PnL‑guard уже считает net‑прибыль с учётом комиссий и валидирует TP/SL/Autoprofit.

Хуки ATR/Impulse лишь улучшают качество входов/размещение TP/SL; на блок про комиссии они не влияют.
