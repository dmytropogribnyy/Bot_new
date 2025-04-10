# 📊 Adaptive Score Threshold & Signal Strength — Предварительный анализ

Версия: BinanceBot v1.6.2-dev  
Цель: Углублённая оценка логики `min_required` и `score` в REAL_RUN + рекомендации по улучшению

---

## ✅ Текущая логика `min_required`

Формируется через:

```python
def get_adaptive_min_score(trade_count, winrate):
    base = 3.0
    if trade_count < 20:
        return base + 0.5
    return base - (winrate - 0.5) * 0.5
```

- 🔹 Если мало сделок (trade_count < 20): порог = 3.5
- 🔹 Иначе: адаптация от winrate:
    - winrate = 60% → min_required = 2.95
    - winrate = 30% → min_required = 3.1
    - Диапазон: ~2.75 – 3.25

---

## ✅ Источник данных

Порог зависит от данных в `tp_performance.csv`:

```python
def get_trade_stats():
    df = pd.read_csv(EXPORT_PATH)
    total = len(df[df["Result"].isin(["TP1", "TP2", "SL"])])
    win = len(df[df["Result"].isin(["TP1", "TP2"])])
    return total, win / total
```

---

## ✅ Текущий расчёт `score`

Реализуется в `calculate_score(df, symbol)` — модель:

- 🔹 RSI: +1 если в зоне (например, <30 или >70)
- 🔹 MACD подтверждает RSI
- 🔹 MACD подтверждает EMA
- 🔹 HTF тренд подтверждён
- 🔹 ADX > 25 → +1

Максимум: `score = 5.0`  
В логах часто встречаются значения `1.2 – 1.5`

---

## 📌 Преимущества текущей модели

- 👍 Простота и интерпретируемость
- 👍 Надёжная защита на старте: min_required = 3.5
- 👍 Возможность снижения порога при хорошем winrate

---

## ⚠️ Недостатки и возможности улучшения

### 1. 🔧 Слабое влияние winrate

- Текущая формула изменяет порог лишь на ±0.25
- 🔄 Рекомендация: повысить коэффициент влияния winrate:

```python
return base - (winrate - 0.5) * 1.0  # вместо * 0.5
```

---

### 2. 🔧 Жёсткий фиксированный base = 3.0

- Может быть слишком строгим при спокойном рынке
- 💡 Рекомендация: вынести `BASE_SCORE_THRESHOLD` в `config.py`:

```python
BASE_SCORE_THRESHOLD = 3.0  # или 2.8
```

---

### 3. 🔧 Нет учёта волатильности

- Рынок может быть вялым, но логика не адаптируется
- 💡 Рекомендация: добавить `atr_factor` как множитель:

```python
atr_factor = df["atr"].iloc[-1] / df["close"].iloc[-1]
min_required = get_adaptive_min_score(trade_count, winrate, atr_factor)
```

```python
def get_adaptive_min_score(trade_count, winrate, atr_factor=1.0):
    base = BASE_SCORE_THRESHOLD * atr_factor
    ...
```

---

### 4. 🔍 Почему score низкий?

- Не все компоненты работают одновременно:
    - RSI не на границе
    - MACD не подтверждает EMA
    - HTF отключён
    - ADX слабый
- 💡 Рекомендации:
    - Ослабить RSI зоны до 35/65
    - Ввести Volume как фактор
    - Проверить нормировку весов и их вклад

---

## 🧠 Итог

| Аспект                   | Статус    | Комментарий |
|--------------------------|-----------|-------------|
| trade_count/winrate      | ✅        | Логика работает, нужно усилить влияние |
| DRY_RUN модификация      | ✅        | Мягкий порог через `* 0.3` |
| Base Threshold           | ⚠️        | Сделать настраиваемым |
| Volatility адаптация     | ❌        | Пока не учитывается |
| Поведение score          | ⚠️        | Часто низкий, можно пересмотреть условия |

---

## ✅ Следующие шаги

1. Вынести `BASE_SCORE_THRESHOLD` в `config.py`
2. Добавить `atr_factor` как аргумент в get_adaptive_min_score
3. Повысить влияние winrate
4. Ослабить условия в calculate_score (опционально)
---

## 🧩 Расширение: Адаптация порога по депозиту

### 🔄 Предложенная логика

```python
from utils_core import get_cached_balance

def get_adaptive_min_score(trade_count, winrate):
    balance = get_cached_balance()
    
    if balance < 50:
        base = 3.0
    elif 50 <= balance < 100:
        base = 2.75
    elif balance < 1000:
        base = 2.5
    else:
        base = 2.0

    if trade_count < 20:
        return base + 0.5

    adjusted_threshold = base - (winrate - 0.5) * 1.0
    return max(adjusted_threshold, base - 0.5)
```

### 📊 Поведение

| Баланс   | Порог (если < 20 сделок) | Порог (trade_count ≥ 20, winrate = 60%) |
|----------|---------------------------|------------------------------------------|
| < $50    | 3.5                       | 2.5 – 3.0                                |
| $50–100  | 3.25                      | 2.25 – 2.75                              |
| $100–1000| 3.0                       | 2.0 – 2.5                                |
| ≥ $1000  | 2.5                       | 1.5 – 2.0                                |

---

## 🧠 Почему это важно

- 💡 Позволяет гибко управлять рисками
- 💡 Повышает активность торговли на крупном депозите
- 💡 Защищает мелкий депозит от слабых сигналов
- 💡 Добавляет адаптивности без избыточной сложности

---

## 🛠 Roadmap внедрения

### 🥇 Этап 1: Базовое внедрение

- [x] Вставить улучшенный `get_adaptive_min_score(...)` в `score_evaluator.py`
- [x] Использовать в `strategy.py` без изменений (только вызов)

### 🥈 Этап 2: Тестирование

- [ ] DRY_RUN:
  - Проверка порога при балансе 40, 80, 500, 1500 USDC
  - Лог `Final Score: {score}/5 (Required: {min_required})`

- [ ] REAL_RUN:
  - Проверка активности сделок при разных балансах
  - Анализ результатов через `tp_performance.csv`

### 🥉 Этап 3: Калибровка

- [ ] При необходимости:
  - Ослабить/усилить base
  - Изменить winrate-множитель
  - Добавить `BASE_SCORE_THRESHOLDS` в `config.py`

### 🧪 Этап 4 (позже): Волатильность (ATR)

- [ ] Добавить `atr_factor` как параметр
- [ ] Применять как множитель base
- [ ] Активировать при накоплении статистики