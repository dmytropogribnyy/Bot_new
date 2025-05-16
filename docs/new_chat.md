# BinanceBot — Phase 2: Signal Optimization

## ✅ Предыдущие фазы завершены

-   Phase 1: SymbolPriority, FailStats, PairSelector, ContinuousScanner — реализовано.
-   Phase 1.5: PostOnly Orders, Capital Utilization, ScoreRelax Boost — интегрировано.
    ✅ Что уже сделано:
    Phase 1: Symbol Management

symbol_priority_manager.py — реализовано и задействовано.

fail_stats_tracker.py — decay + прогрессивная блокировка добавлены.

pair_selector.py — адаптивный select_active_symbols_v2() интегрирован.

continuous_scanner.py — реализован и запущен в main.py.

Phase 1.5: Critical Optimizations

create_post_only_limit_order() — используется для TP1/TP2 в trade_engine.py.

check_capital_utilization() — заменил ручную проверку на 40–70% капитала.

adjust_score_relax_boost() — вызывается каждые 60 мин через APScheduler.

get_adaptive_min_score() — поддерживает score_relax_boost.

constants.py — создан, все пути централизованы.

main.py

Полностью синхронизирован: все нужные задачи планируются (включая Continuous Scanner, adjust_score_relax_boost, decay и др.).

Проверка конфигурации и логика запуска стабильны.

## 🔜 Phase 2: Signal Optimization

### Шаг 1 — `strategy.py`

-   [ ] Заменить fetch_data() на `fetch_data_optimized()`
-   [ ] Использовать только: RSI(9), EMA(9/21), MACD, VWAP, Volume, ATR
-   [ ] Удалить/закомментировать ADX, BB и прочее

### Шаг 2 — `score_evaluator.py`

-   [ ] Обновить `calculate_score(df, symbol)`

    -   Добавить лог `score_components`
    -   Привести шкалу к 0–5
    -   Обновить веса

-   [ ] Проверить `get_adaptive_min_score()`:
    -   Баланс
    -   Время
    -   Волатильность
    -   score_relax_boost (уже есть ✅)

## 🎯 Цель

-   Получить более точные, надёжные сигналы
-   Снизить перегрузку индикаторами
-   Сохранить адаптивность min_score

## 🧪 DRY_RUN тест после внедрения:

-   Следим за:
    -   Частотой сигналов
    -   Кол-вом активных пар
    -   Score распределением

## ⏭️ Далее (Phase 3)

-   Multi-Timeframe анализ
-   Smart Signal Confirmation
-   Визуализация Score Components (опц.)
