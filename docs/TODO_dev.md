# ✅ BinanceBot v1.6.2-dev — TODO Plan (Апрель 2025)

## 🟢 Глобальный статус
- Версия: `v1.6.2-dev`
- Архитектура: модульная, DRY_RUN изоляция, Telegram-обвязка, ML и HTF-оптимизация
- Текущий фокус: чистка стратегии, адаптивность и улучшение читаемости сигналов

---

## ✅ Уже реализовано

- ✅ TP/SL, TP1/TP2, trailing, break-even
- ✅ Smart Switching с лимитом и winrate
- ✅ Adaptive Score с весами и explain_score
- ✅ Aggressiveness EMA-система
- ✅ DRY_RUN-защита — все файлы и Telegram очищены
- ✅ HTF-фильтр: автоанализ, автовключение/выключение
- ✅ TP Logger: логируются HTF, ATR, ADX, BB
- ✅ Telegram команды + MarkdownV2 Guide
- ✅ Auto-ротация символов и кэш
- ✅ Auto ML TP Optimizer и статусы символов

---

## 🛠️ TODO: Что нужно доделать

### 1. 🔁 TP1/TP2 per symbol (`TP_THRESHOLDS`)
- [ ] Добавить `TP_THRESHOLDS = {symbol: {tp1, tp2}}` в `config.py`
- [ ] Обновить `trade_engine.py`:
  ```python
  tp1 = TP_THRESHOLDS.get(symbol, {}).get("tp1", TP1_PERCENT)
  tp2 = TP_THRESHOLDS.get(symbol, {}).get("tp2", TP2_PERCENT)
  ```
- [ ] Обновить `tp_optimizer_ml.py`, чтобы он писал значения в этот блок
- [ ] Добавить лог при использовании кастомного TP в Telegram

---

### 2. ⚙️ Adaptive MIN_TRADE_SCORE
- [ ] В `strategy.py` получить:
  ```python
  trade_count, winrate = get_stats_from_csv()
  min_required = get_adaptive_min_score(trade_count, winrate)
  ```
- [ ] Передавать `min_required` в сравнение с `score`
- [ ] Добавить лог адаптированного порога

---

### 3. 🧹 Централизация фильтров (ATR, ADX, BB)
- [ ] Вынести фильтрацию в функцию:
  ```python
  passes_filters(df, thresholds) -> bool
  ```
- [ ] Использовать `FILTER_THRESHOLDS[symbol]`
- [ ] Удалить дублирующую логику из `strategy.py`

---

### 4. 📉 PnL график
- [ ] Реализовать `generate_pnl_graph()` в `stats.py`
- [ ] Построить matplotlib-график по `tp_performance.csv`
- [ ] Отправлять в Telegram по команде или по расписанию

---

## 📦 Дополнительно (опционально)
- [ ] Перевести `strategy.py` в объектную структуру / класс
- [ ] Добавить лог `score` в REAL_RUN (если не отключено)

---

## 🗂️ Schedule loops (актуальны)
- Ежедневный отчёт: 21:00
- Еженедельный отчёт: вс, 21:00
- Месяц, квартал, полгода, год — по расписанию
- ML TP Optimizer: каждые 2 дня, 21:30
- HTF Optimizer: каждое воскресенье
- Score Heatmap: пятница

---

⚙️ Готов к внедрению. Чеклист синхронизирован с `v1.6.1-final` + HTF + ML TP.