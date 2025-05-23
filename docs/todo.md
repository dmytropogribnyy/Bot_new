✅ Текущий статус проекта (v1.6.3-final)
🔄 Обновление «живых» пар:
test_api.py реализован и проверяет ≥30 свечей на 3m/5m/15m;

valid-список пар сохраняется в data/valid_usdc_symbols.json;

pair_selector.py использует именно этот whitelist, не USDC_SYMBOLS;

файл обновляется автоматически при запуске бота, если прошёл лимит времени;

в случае ошибок (ошибочный путь или Python не найден) файл может не создаться, что ведёт к загрузке старого списка — ты это отловил и пофиксил через sys.executable.

⚠️ Проблема (устранена):
❌ Была ошибка FileNotFoundError, потому что путь к Python был некорректен;

✅ Заменено на subprocess.call([sys.executable, "test_api.py"]);

❌ Также была ситуация, когда valid_usdc_symbols.json не успел создаться до начала отбора пар;

✅ Мы добавили лог на result != 0 после subprocess + проверку наличия файла.

🧠 Архитектура пар и ротации
Все пары берутся из valid_usdc_symbols.json, проверенные через test_api.py;

Пары отбираются в select_active_symbols() по динамическим фильтрам: ATR, объём, волатильность, risk_factor, performance_score;

Гибкий диапазон пар:

min_dynamic_pairs = 8

max_dynamic_pairs = 15

Эти значения задаются через runtime_config.json;

При нехватке хороших пар включается fallback через force_fallback_if_active.

📊 fetch_data_multiframe
limit = 300, поэтапный join (3m + 5m + 15m);

dropna() после join;

df["atr"] = df["atr_15m"] для устранения KeyError;

логируется df.shape, сохраняется fetch_debug.json;

работает стабильно, без Suffixes not supported и без no data, если пары из whitelist.

🧠 calculate_score (v1.6.3)
Поддерживает сигналы: RSI, MACD, EMA_CROSS, Volume, HTF, PriceAction;

breakdown логируется;

защита от NaN;

теперь виден в debug log как:

csharp
Copy
Edit
[ScoreDebug] BTC/USDC raw_score=1.2, breakdown={'MACD': 1.2}
🔧 Что осталось / текущие задачи:
Задача Статус
✅ Обновление valid_usdc_symbols.json через test_api.py ✔ Сделано
✅ Проверка всех пар при старте, исключая те, где нет свечей ✔ Сделано
✅ Ротация только по рабочим символам ✔ Сделано
✅ Устранение KeyError 'atr' ✔ Сделано
✅ calculate_score с breakdown ✔ Сделано
⚠️ Автоматическая перезапись valid_usdc_symbols.json при фейле test_api.py Внедрено, но стоит ещё раз протестировать
⚠️ Обработка fallback, если valid.json не создан вовремя Уже покрыта — можно дополнительно логировать Path.exists()

📌 Что можно улучшить (опционально):
Логировать список всех символов, проверенных в test_api.py с кол-вом прошедших (например, ✅ Checked 36, valid: 31, skipped: 5);

Добавить Telegram-уведомление при успешном выполнении test_api.py с количеством валидных пар;

Вынести путь к test_api.py в переменную (будет удобнее для Windows/Linux);

Добавить backup старого valid_usdc_symbols.json перед перезаписью.
