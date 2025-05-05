# pair_selector.py
import json
import os
import time
from threading import Lock

import pandas as pd

from common.config_loader import (
    DRY_RUN,
    FIXED_PAIRS,
    MAX_DYNAMIC_PAIRS,
    MIN_DYNAMIC_PAIRS,
    SYMBOLS_ACTIVE,
    USDC_SYMBOLS,
    USDT_SYMBOLS,
    USE_TESTNET,
)
from core.binance_api import convert_symbol
from core.exchange_init import exchange
from telegram.telegram_utils import send_telegram_message
from utils_core import get_cached_balance, safe_call_retry
from utils_logging import log

SYMBOLS_FILE = "data/dynamic_symbols.json"
UPDATE_INTERVAL_SECONDS = 60 * 60
symbols_file_lock = Lock()

DRY_RUN_FALLBACK_SYMBOLS = USDT_SYMBOLS if USE_TESTNET else USDC_SYMBOLS

# Приоритетные пары для малых депозитов
PRIORITY_PAIRS_SMALL = ["XRP/USDC", "DOGE/USDC", "ADA/USDC"]


def fetch_all_symbols():
    try:
        markets = safe_call_retry(exchange.load_markets, label="load_markets")
        if not markets:
            log("No markets returned from API", level="ERROR")
            if DRY_RUN:
                log("Using fallback symbols in DRY_RUN", level="WARNING")
                send_telegram_message("⚠️ Using fallback symbols due to API failure", force=True)
                return DRY_RUN_FALLBACK_SYMBOLS
            log("No active symbols available and DRY_RUN is False, stopping", level="ERROR")
            send_telegram_message("⚠️ No active symbols available, stopping bot", force=True)
            return []
        log(f"Loaded markets: {len(markets)} total symbols", level="DEBUG")
        log(f"Sample markets: {list(markets.keys())[:5]}...", level="DEBUG")

        active_symbols = []
        for symbol in SYMBOLS_ACTIVE:
            api_symbol = convert_symbol(symbol)
            if api_symbol in markets and markets[api_symbol]["active"]:
                active_symbols.append(symbol)
                log(
                    f"Symbol: {symbol}, API: {api_symbol}, Type: {markets[api_symbol]['type']}, Active: {markets[api_symbol]['active']}",
                    level="DEBUG",
                )
            else:
                log(
                    f"Symbol {symbol} (API: {api_symbol}) not found or inactive on exchange",
                    level="WARNING",
                )

        log(f"Validated {len(active_symbols)} active symbols: {active_symbols[:5]}...", level="INFO")
        if not active_symbols and DRY_RUN:
            log("No symbols validated from API in DRY_RUN, using fallback symbols", level="WARNING")
            return DRY_RUN_FALLBACK_SYMBOLS
        return active_symbols
    except Exception as e:
        log(f"Error fetching all symbols: {str(e)}", level="ERROR")
        if DRY_RUN:
            log("API error in DRY_RUN, using fallback symbols", level="WARNING")
            return DRY_RUN_FALLBACK_SYMBOLS
        return []


def fetch_symbol_data(symbol, timeframe="15m", limit=100):
    try:
        api_symbol = convert_symbol(symbol)
        ohlcv = safe_call_retry(exchange.fetch_ohlcv, api_symbol, timeframe, limit=limit, label=f"fetch_ohlcv {symbol}")
        if not ohlcv:
            log(f"No OHLCV data returned for {symbol}", level="ERROR")
            return None
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df
    except Exception as e:
        log(f"Error fetching data for {symbol}: {e}", level="ERROR")
        return None


def calculate_volatility(df):
    """
    Рассчитывает волатильность на основе размаха цен.
    """
    if df is None or len(df) < 2:
        return 0
    df["range"] = df["high"] - df["low"]
    return df["range"].mean() / df["close"].mean()


def calculate_atr_volatility(df, period=14):
    """
    Рассчитывает волатильность на основе ATR.
    """
    if df is None or len(df) < period + 1:
        return 0

    # Расчет TR (True Range)
    df["tr1"] = abs(df["high"] - df["low"])
    df["tr2"] = abs(df["high"] - df["close"].shift(1))
    df["tr3"] = abs(df["low"] - df["close"].shift(1))
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)

    # Расчет ATR
    df["atr"] = df["tr"].rolling(period).mean()

    # Возвращаем среднее ATR в процентах от цены
    if len(df) > period and not pd.isna(df["atr"].iloc[-1]):
        return df["atr"].iloc[-1] / df["close"].iloc[-1]
    else:
        return 0


def select_active_symbols():
    """
    Отбирает активные символы для торговли с учетом размера депозита.
    """
    # Определяем количество пар в зависимости от размера депозита
    balance = get_cached_balance()

    if balance < 120:
        min_dyn = min(MIN_DYNAMIC_PAIRS, 3)  # Максимум 3 динамические пары для < 120 USDC
        max_dyn = min(MAX_DYNAMIC_PAIRS, 5)  # Максимум 5 динамических пар для < 120 USDC
    elif balance < 200:
        min_dyn = min(MIN_DYNAMIC_PAIRS, 5)
        max_dyn = min(MAX_DYNAMIC_PAIRS, 8)
    else:
        min_dyn = MIN_DYNAMIC_PAIRS
        max_dyn = MAX_DYNAMIC_PAIRS

    # Получаем все доступные символы
    all_symbols = fetch_all_symbols()
    fixed = FIXED_PAIRS

    # Приоритетные пары для малых депозитов
    priority_pairs = PRIORITY_PAIRS_SMALL if balance < 150 else []

    # Собираем данные по всем символам
    dynamic_data = {}
    for s in all_symbols:
        if s in fixed:
            continue

        df = fetch_symbol_data(s)
        if df is not None:
            vol = calculate_volatility(df)
            atr_vol = calculate_atr_volatility(df)
            vol_avg = df["volume"].mean()

            # Рассчитываем показатель качества пары
            volatility_score = vol * 0.5 + atr_vol * 0.5  # Совмещаем разные метрики волатильности

            dynamic_data[s] = {
                "volatility": volatility_score,
                "volume": vol_avg,
                "vol_to_volatility": vol_avg / (volatility_score + 0.00001),  # Предотвращаем деление на ноль
                "price": df["close"].iloc[-1],  # Текущая цена актива
                "symbol": s,
            }

    # Разная стратегия сортировки в зависимости от размера счета
    if balance < 150:
        # Для малых депозитов предпочитаем умеренную волатильность с хорошим объемом
        # и низкой номинальной ценой
        sorted_dyn = sorted(
            dynamic_data.items(),
            key=lambda x: x[1]["vol_to_volatility"] * (1 / (x[1]["price"] + 0.01)),  # Предпочитаем низкие цены
            reverse=True,
        )[:30]

        # Создаем итоговый список с учетом приоритетных пар
        final_pairs = []

        # Добавляем приоритетные пары сначала, если они есть в данных
        for pair in priority_pairs:
            if pair in dynamic_data:
                final_pairs.append(pair)
                log(f"Added priority pair for small account: {pair}", level="INFO")

        # Затем добавляем другие пары до лимита
        remaining_slots = min(min_dyn, max_dyn) - len(final_pairs)
        if remaining_slots > 0:
            for pair, _ in sorted_dyn:
                if pair not in final_pairs and pair not in fixed:
                    final_pairs.append(pair)
                    remaining_slots -= 1
                    if remaining_slots <= 0:
                        break

        selected_dyn = final_pairs

        # Обеспечиваем минимальное количество пар
        if len(selected_dyn) < min_dyn:
            for pair, _ in sorted_dyn:
                if pair not in selected_dyn and pair not in fixed:
                    selected_dyn.append(pair)
                    if len(selected_dyn) >= min_dyn:
                        break
    else:
        # Стандартный алгоритм для больших депозитов
        # Предпочитаем комбинацию высокой волатильности и объема
        sorted_dyn = sorted(dynamic_data.items(), key=lambda x: x[1]["volatility"] * x[1]["volume"], reverse=True)[:30]

        # Ограничиваем количество пар
        dyn_count = max(min_dyn, min(max_dyn, len(sorted_dyn)))
        selected_dyn = [s for s, _ in sorted_dyn[:dyn_count]]

    # Объединяем фиксированные и динамические пары
    active_symbols = fixed + selected_dyn

    # Логируем и сохраняем результаты
    log(f"Selected {len(active_symbols)} active symbols: {active_symbols}", level="INFO")

    try:
        os.makedirs(os.path.dirname(SYMBOLS_FILE), exist_ok=True)
        with symbols_file_lock, open(SYMBOLS_FILE, "w") as f:
            json.dump(active_symbols, f)
        log(f"Saved active symbols to {SYMBOLS_FILE}", level="INFO")
    except Exception as e:
        log(f"Error saving active symbols to {SYMBOLS_FILE}: {e}", level="ERROR")

    # Отправляем уведомление
    msg = f"🔄 Symbol rotation completed:\n" f"Total pairs: {len(active_symbols)}\n" f"Fixed: {len(fixed)}, Dynamic: {len(selected_dyn)}\n" f"Balance: {balance:.2f} USDC"
    if balance < 150 and priority_pairs:
        priority_in_selection = [p for p in priority_pairs if p in active_symbols]
        if priority_in_selection:
            msg += f"\nPriority pairs included: {', '.join(priority_in_selection)}"

    send_telegram_message(msg, force=True)
    return active_symbols


def start_symbol_rotation(stop_event):
    """
    Запускает периодическую ротацию символов.
    """
    while not stop_event.is_set():
        try:
            select_active_symbols()
        except Exception as e:
            log(f"Symbol rotation error: {e}", level="ERROR")
            send_telegram_message(f"⚠️ Symbol rotation failed: {e}", force=True)
        time.sleep(UPDATE_INTERVAL_SECONDS)
