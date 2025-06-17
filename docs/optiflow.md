## 🤖 Финальный план внедрения ботов (OptiFlow System)

Этот документ описывает пошаговый план внедрения твоей мультибот-системы на базе основного бота (OptiScalp A / версия 1.1), включая тюнинг, структуру и запуск до 9 параллельных ботов.

---

## 🧱 Этап 0 — База: OptiScalp A (основной бот 1.1)

**Статус:** почти готов, но требует доработки

### Что доработать:

-   [ ] Логирование по символам (что фильтруется, что не проходит)
-   [ ] Отправка Telegram-уведомлений при TP1/TP2/SL
-   [ ] Проверка работы сигналов: действительно ли доходит до входа
-   [ ] Улучшение логики фильтров (не переотсеивать всё подряд)

📈 Цель: стабильная, умеренно активная версия для оценки поведения рынка и фильтров

---

## 🪜 Этап 1 — Поэтапный запуск скальп-ботов (OptiScalp A / B / C)

### ✅ OptiScalp_A

-   Пары: BTC, ETH, ADA
-   TP1: 0.003, SL: 0.006
-   Интервал: 20 сек
-   Макс 2 позиции
-   Цель: \$15–25/день

### ⏩ OptiScalp_B (через 2–3 дня)

-   Пары: SOL, DOGE, LTC
-   TP1: 0.0025, SL: 0.005
-   Интервал: 15 сек
-   Активнее по частоте
-   Цель: \$20–30/день

### 🔥 OptiScalp_C (через 3–5 дней)

-   Пары: XRP, AVAX, MATIC
-   TP1: 0.002, SL: 0.004
-   Интервал: 10 сек
-   До 3 одновременных позиций
-   Цель: \$30–40/день, но выше шанс SL

📌 Эти три бота = основа HFT-профиля

---

## 🧩 Этап 2 — Расширение до 6–9 ботов

Запуск дополнительных скальперов и свинг-ботов на других парах:

-   HFT-боты: OptiScalp A/B/C (как 3 независимых инстанса)
-   2–3 умеренных скальп-бота с другим набором пар (на основе логики 1.1)
-   2–3 микросвинг-бота с увеличенным hold_time и TP2-only логикой

📊 Цель: выйти на \$90–150+ в день при депозите \$600–700 на каждого

---

## 🎯 Финальный тюнинг (для всех ботов)

### ✅ 1. Фильтры объёма и волатильности

```python
volume_filter = median_volume * 1.2
atr_filter = median_atr * 0.9
```

### ✅ 2. Пауза между сделками

```python
min_pause_between_trades = 300  # 5 минут
```

### ✅ 3. Auto-pause при серии лоссов

```python
if last_3_results == ['loss', 'loss', 'loss']:
    pause_trading(symbol, duration=900)  # 15 минут
```

### ✅ 4. Daily Max Loss Limit

```python
if daily_pnl < -5:
    pause_all_trading(duration=3600)  # стоп на 1 час
```

### ✅ 5. Лимит сделок в час (для HFT)

```python
max_trades_per_hour = 6
```

---

## 🧠 Финальные замечания

-   Начинай с одного-двух ботов (OptiScalp A + B)
-   Проверяй, что фильтры не глушат сигналы полностью
-   Telegram-логика должна давать ясную картину: вход, выход, результат
-   Обязательно логируй отфильтрованные пары с пояснением

✅ Когда всё отлажено — масштабируй спокойно до 6–9 процессов.

## Хочешь — могу подготовить `runtime_config_optiscalpA.json` и шаблон папки под 3 бота.

---

## 🔜 Следующий шаг — Параллельный запуск через ENV

-   Добавить поддержку `--config` и `--data-dir` в `main.py`
-   Создать следующие конфиги:
    -   `runtime_config_optiscalpA.json`
    -   `runtime_config_optiscalpB.json`
    -   `runtime_config_optiscalpC.json`
-   Создать скрипт `bot_launcher.sh` или использовать `pm2` / `tmux`
-   Убедиться, что каждая сессия имеет свой `data/`, `log/`, `config/`

📦 Пример запуска:

```bash
python main.py --config=configs/optiscalpA.json --data-dir=data/scalp_A/
python main.py --config=configs/optiscalpB.json --data-dir=data/scalp_B/
```

Details:
🔁 Ближайшие шаги (по документации и прогрессу):

1. Подготовить runtime_config_optiscalpA.json
   json
   Copy
   Edit
   {
   "max_concurrent_positions": 2,
   "base_risk_pct": 0.008,
   "risk_multiplier": 1.0,
   "SL_PERCENT": 0.006,
   "step_tp_levels": [0.003, 0.006],
   "step_tp_sizes": [0.4, 0.6],
   "max_hourly_trade_limit": 6,
   "cooldown_minutes": 2,
   "min_profit_threshold": 0.03,
   "monitoring_hours_utc": [0, 1, 2, 3, 4, 5]
   }
2. Добавить аргументы в main.py:
   python
   Copy
   Edit
   import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--config", help="Path to runtime_config.json")
parser.add_argument("--data-dir", help="Path to data directory")
args = parser.parse_args()

if args.config:
os.environ["RUNTIME_CONFIG_PATH"] = args.config
if args.data_dir:
os.environ["DATA_DIR"] = args.data_dir
🔧 Это даст тебе гибкость запускать 3–9 ботов так:

bash
Copy
Edit
python main.py --config=configs/scalp_a.json --data-dir=data/scalp_a/
python main.py --config=configs/scalp_b.json --data-dir=data/scalp_b/ 3. Создать скрипт запуска bot_launcher.sh (если на Linux/pm2):
bash
Copy
Edit
#!/bin/bash
python3 main.py --config=configs/optiscalpA.json --data-dir=data/optiscalpA &
python3 main.py --config=configs/optiscalpB.json --data-dir=data/optiscalpB &
python3 main.py --config=configs/optiscalpC.json --data-dir=data/optiscalpC &
📦 Готов подготовить:
runtime_config_optiscalpA.json

runtime_config_optiscalpB.json

runtime_config_optiscalpC.json

bot_launcher.sh шаблон

Хочешь — создаю сразу и показываю готовые конфиги для запуска параллельных ботов?

You said:
куда добавить это todo в один из 3 qafqkjf &

ChatGPT said:
Чтобы грамотно встроить актуальный мультибот TODO (OptiScalp A/B/C + launcher) в текущие документы, вот наилучший вариант:

✅ Добавить в файл: optiflow.md
📁 Это главный системный план (OptiFlow System — Финальный Детальный План), именно он уже содержит:

✅ этапы OptiScalp A/B/C

✅ цели по доходу

✅ runtime-защиту, Telegram, и т.п.
