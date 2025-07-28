Финальный анализ и план исправлений BinanceBot (27 июля 2025)
🎯 Главные выводы
После анализа трех независимых источников (мой анализ Claude, анализ GPT и проверка по логам), ВСЕ критические проблемы подтверждены. Самая опасная — это условная установка Stop Loss, которая оставляет позиции без защиты.
🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ (исправить немедленно)

1. Stop Loss не ставится при провале TP ⚡️
   Проблема: Если TP не удалось установить, SL тоже пропускается
   Доказательства: SUI/USDC, ENA/USDC остались без защиты
   Решение:
   python# tp_utils.py - place_take_profit_and_stop_loss_orders()

# БЫЛО: if success_tp > 0: place_sl()

# ДОЛЖНО БЫТЬ:

def place_take_profit_and_stop_loss_orders(...): # ШАГ 1: ВСЕГДА ставим SL первым!
try:
sl_order = exchange.create_order(
api_symbol,
type="STOP_MARKET",
side="sell" if side == "buy" else "buy",
amount=qty,
params={"stopPrice": sl_price, "reduceOnly": True}
)
success_sl = True
trade_manager.update_trade(symbol, "sl_price", sl_price)
except Exception as e:
log(f"❌ CRITICAL: SL failed for {symbol}: {e}")
send_telegram_message(f"🚨 SL FAILED! Closing {symbol} immediately!")
close_real_trade(symbol)
return False

    # ШАГ 2: Пытаемся поставить TP (необязательно)
    if success_sl:  # Только если SL успешен
        # ... код установки TP ...

2.  Микро-позиции без TP/SL
    Проблема: При qty < 0.003 функция safe_round_and_validate возвращает None
    Доказательства: 4 из 10 сделок с tp_total_qty = 0
    Решение:
    python# tp_utils.py
    def handle_micro_position_tp(symbol, qty, entry_price, direction):
    """Специальная логика для позиций < $10"""
    min_notional = 5.0
    current_notional = qty \* entry_price

        if current_notional < min_notional * 2:  # < $10
            # Ставим ТОЛЬКО Stop Loss на всю позицию
            sl_price = calculate_sl_price(entry_price, direction)
            place_sl_only(symbol, qty, sl_price)
            send_telegram_message(f"⚠️ {symbol}: Position too small for TP, SL only")
            return

        # Иначе объединяем все TP в один ордер
        tp1_price = calculate_tp1_price(entry_price, direction)
        place_single_tp(symbol, qty, tp1_price)

3.  Зависшие позиции блокируют новые сделки
    Проблема: WIF и XRP остались в pending_exit = True после закрытия
    Доказательства: После 17:15 новые сделки не открывались при 3/6 позициях
    Решение:
    python# position_manager.py - check_entry_allowed()
    def count_real_positions():
    """Считаем только реальные позиции на бирже"""
    positions = exchange.fetch_positions()
    active = [p for p in positions if float(p['positionAmt']) != 0]

        # Синхронизируем с trade_manager
        for symbol in list(trade_manager.trades.keys()):
            if symbol not in [p['symbol'] for p in active]:
                # Позиция закрыта на бирже но висит локально
                trade_manager.remove_trade(symbol)
                log(f"[Sync] Removed ghost position {symbol}")

        return len(active)

4.  Расхождение конфигураций TP
    Проблема: Бот использовал 0.7%/1.4% вместо 0.25%/0.4% из runtime_config
    Решение:
    python# tp_utils.py - calculate_tp_levels()
    def calculate_tp_levels(entry_price, direction, ...): # ВСЕГДА берем из runtime_config
    cfg = get_runtime_config()
    tp_levels = cfg.get('step_tp_levels', [0.007, 0.014])
    tp_shares = cfg.get('step_tp_sizes', [0.8, 0.2])

        # НЕ из config_loader!

    🟡 ВАЖНЫЕ ПРОБЛЕМЫ (исправить на этой неделе)

5.  Нет повторных попыток TP/SL
    python# trade_engine.py - enter_trade()
    async def place_orders_with_retry(symbol, orders, max_retries=3):
    for attempt in range(max_retries):
    try:
    result = await place_order(...)
    if result['success']:
    return result
    except Exception as e:
    if "MIN_NOTIONAL" in str(e) and attempt < max_retries-1:
    await asyncio.sleep(1)
    continue
    raise
6.  Monitor не проверяет пропавшие ордера
    python# monitor_active_position()
    async def check_and_restore_protection(symbol, trade):
    open_orders = exchange.fetch_open_orders(symbol)
    has_sl = any(o['type'] == 'STOP_MARKET' for o in open_orders)

        if not has_sl and trade.get('sl_price'):
            log(f"🚨 Missing SL for {symbol}, restoring...")
            place_emergency_sl(symbol, trade['qty'], trade['sl_price'])

    📋 Приоритетный чек-лист исправлений
    Сегодня (критично):

FIX #1: SL ВСЕГДА ставится первым в place_take_profit_and_stop_loss_orders()
FIX #2: Добавить handle_micro_position_tp() для qty < 0.003
FIX #3: В check_entry_allowed() использовать count_real_positions()
FIX #4: Заменить TP1_PERCENT на get_runtime_config()['step_tp_levels']

Завтра:

FIX #5: Добавить retry логику в place_order()
FIX #6: В monitor_active_position() добавить проверку пропавших SL
FIX #7: Очистка pending_exit через 5 минут автоматически
FIX #8: Telegram алерт при tp_total_qty == 0

На неделе:

Логирование причин закрытия (timeout/auto_profit/sl)
Учет комиссий в расчете прибыли
Проверка "would trigger immediately" перед SL

🎯 Проверка после исправлений

Запустить с 1-2 позициями на малых суммах
Проверить:

Все позиции имеют SL? ✓
Микро-позиции защищены? ✓
После закрытия открываются новые? ✓
TP уровни соответствуют runtime_config? ✓

Итог
Все три анализа (Claude + GPT + логи) сходятся: главная проблема — условная установка SL. Это нарушение базовой безопасности трейдинга. После исправления первых 4 пунктов бот станет безопасным, остальное — улучшения.
Рекомендация по настройкам: После фиксов изменить SL: 0.8% → 1.2%, чтобы улучшить risk/reward ratio.
