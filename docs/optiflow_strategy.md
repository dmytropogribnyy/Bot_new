# 📘 OptiFlow Strategy v2.9 — Полное Обновление (Core + Expansion)

## 🎯 Цель стратегии:

Создать стабильный и масштабируемый бот-движок, приносящий:

-   💵 \$10–25/день при депозите \$220–500
-   💰 \$50–130/день при \$1000+ через OptiFlow Core
-   ⚡ \$150–300/день при подключении скальпинг-модулей
-   🚀 До \$1000/день при мультибиржевой системе с параллельными ботами

---

## 🛡 Safety Tuning Layer (актуален для всех режимов: Core и Scalp)

### ✅ 1. Фильтры объёма и ATR (адаптивные)

```python
volume_filter = median_volume * 1.2
atr_filter = median_atr * 0.9
```

Цель: пропускать полезные сигналы, но исключать мёртвый рынок.

### ✅ 2. Anti-reentry: пауза между входами

```python
min_pause_between_trades = 300  # 5 минут
```

Цель: не входить повторно по той же паре во флете или откате.

### ✅ 3. Auto-pause после серии лоссов

```python
if last_3_results == ['loss', 'loss', 'loss']:
    pause_trading(symbol, duration=900)  # 15 минут
```

Цель: временно заблокировать символ после серии неудач.

### ✅ 4. Daily Max Loss (анти-слив)

```python
if daily_pnl < -5:
    pause_all_trading(duration=3600)  # стоп на 1 час
```

Цель: если дневной убыток превышен — стоп всей торговли.

### ✅ 5. Max trades per hour (анти-HFT-перегрев)

```python
max_trades_per_hour = 6
```

Цель: не допустить гиперактивности в боковике или пампе.

📌 Эти блоки встраиваются в runtime-логику (monitor_active_position, signal_utils, risk_guard).
📈 Результат — спокойный и безопасный бот даже на реальных деньгах с \$300–700.

---

## 🔁 OptiFlow Core Bot (v2.9 Final)

...

## Additional block

# 📘 OptiFlow Strategy v2.9 — Полное Обновление (Core + Expansion)

## 🎯 Цель стратегии:

Создать стабильный и масштабируемый бот-движок, приносящий:

-   💵 \$10–25/день при депозите \$220–500
-   💰 \$50–130/день при \$1000+ через OptiFlow Core
-   ⚡ \$150–300/день при подключении скальпинг-модулей
-   🚀 До \$1000/день при мультибиржевой системе с параллельными ботами

---

## 🛡 Safety Tuning Layer (актуален для всех режимов: Core и Scalp)

### ✅ 1. Фильтры объёма и ATR (адаптивные)

```python
volume_filter = median_volume * 1.2
atr_filter = median_atr * 0.9
```

Цель: пропускать полезные сигналы, но исключать мёртвый рынок.

### ✅ 2. Anti-reentry: пауза между входами

```python
min_pause_between_trades = 300  # 5 минут
```

Цель: не входить повторно по той же паре во флете или откате.

### ✅ 3. Auto-pause после серии лоссов

```python
if last_3_results == ['loss', 'loss', 'loss']:
    pause_trading(symbol, duration=900)  # 15 минут
```

Цель: временно заблокировать символ после серии неудач.

### ✅ 4. Daily Max Loss (анти-слив)

```python
if daily_pnl < -5:
    pause_all_trading(duration=3600)  # стоп на 1 час
```

Цель: если дневной убыток превышен — стоп всей торговли.

### ✅ 5. Max trades per hour (анти-HFT-перегрев)

```python
max_trades_per_hour = 6
```

Цель: не допустить гиперактивности в боковике или пампе.

📌 Эти блоки встраиваются в runtime-логику (monitor_active_position, signal_utils, risk_guard).
📈 Результат — спокойный и безопасный бот даже на реальных деньгах с \$300–700.

---

## 🔁 OptiFlow Core Bot (v2.9 Final)

...

## Signal implemenation explanation

# 📘 OptiFlow Strategy v2.9 — Полное Обновление (Core + Expansion)

## 🎯 Цель стратегии:

Создать стабильный и масштабируемый бот-движок, приносящий:

-   💵 \$10–25/день при депозите \$220–500
-   💰 \$50–130/день при \$1000+ через OptiFlow Core
-   ⚡ \$150–300/день при подключении скальпинг-модулей
-   🚀 До \$1000/день при мультибиржевой системе с параллельными ботами

---

## 🛡 Safety Tuning Layer (актуален для всех режимов: Core и Scalp)

### ✅ 1. Фильтры объёма и ATR (адаптивные)

```python
volume_filter = median_volume * 1.2
atr_filter = median_atr * 0.9
```

### ✅ 2. Anti-reentry: пауза между входами

```python
min_pause_between_trades = 300  # 5 минут
```

### ✅ 3. Auto-pause после серии лоссов

```python
if last_3_results == ['loss', 'loss', 'loss']:
    pause_trading(symbol, duration=900)
```

### ✅ 4. Daily Max Loss (анти-слив)

```python
if daily_pnl < -5:
    pause_all_trading(duration=3600)
```

### ✅ 5. Max trades per hour (анти-HFT-перегрев)

```python
max_trades_per_hour = 6
```

---

## 🔍 Сигнальная стратегия: как работает и когда даёт вход

Сигнальная система используется всеми ботами (Core + Scalp) и включает:

### 🔹 Компоненты сигнала:

-   `MACD`: основа определения направления
-   `EMA_CROSS`: подтверждение импульса
-   `RSI_15m`: сила текущего отклонения (по runtime порогу)
-   `Volume`, `PriceAction`, `HTF`: вторичные подтверждения

### 🔹 Определение направления:

```python
if macd > macd_signal and ema_cross → direction = 'buy'
elif macd < macd_signal and not ema_cross → 'sell'
```

### 🔹 passes_1plus1(): проверка наличия первичных и вторичных подтверждений

-   В `soft_mode`: достаточно PRIMARY ≥ 1 (например, MACD)
-   В `strict_mode`: необходимо PRIMARY ≥ X и SECONDARY ≥ Y
-   Значения настраиваются через `runtime_config`

### 🔹 Фильтры:

-   `rsi_15m >= threshold`
-   `atr_percent >= atr_threshold_percent`
-   `volume_usdt >= volume_threshold_usdc`
-   `rel_volume_15m >= threshold`

📌 Всё гибко: каждый бот может иметь свой `runtime_config.json`, с более мягкими или жёсткими фильтрами.

🧠 Результат: бот входит только при чётком подтверждении импульса и объёма, сигнал = точка с высокой вероятностью движения.

---

## 🔁 OptiFlow Core Bot (v2.9 Final)

...
