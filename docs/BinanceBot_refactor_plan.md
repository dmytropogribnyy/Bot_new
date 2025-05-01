# Новый проект: BinanceBot — Перенос глобальных переменных и рефакторинг импортов

---

## Контекст:

-   Проект BinanceBot (версия `v1.6-dev`) успешно собран, запущен и готов к дальнейшей чистке и улучшению.
-   Реализованы:
    -   Ruff linting + auto-fix (`ruff check --fix .`)
    -   Синтаксическая проверка (`python -m compileall .`)
    -   Настройки VSCode, Venv, Python Interpreter.

## Цель нового этапа:

**Системно убрать глобальные импорты config/.env и все значения перенести на загрузку через `common/config_loader.py` с вызовом `get_config()`**.

## Что уже готово:

-   Создан модуль `common/config_loader.py`:
    -   Загрузка через dotenv
    -   Функция `get_config(var_name, default=None)`
-   Создан заготовочный `common/messaging.py` (ещё пустой)

## Что надо сделать:

1. Убрать все `import config` и прямые загрузки .env переменных.
2. Везде заменить на:
    ```python
    from common.config_loader import get_config
    API_KEY = get_config("API_KEY")
    ```
3. Откорректировать все проблемы Ruff (imports, E501, F821).
4. Перепроверить:
    - `python -m compileall .`
    - `ruff check .`
5. Убедиться, что бот собирается и запускается без ошибок.

---

## Структура проекта:

_(Сюда вставить картинку `binancebot_structure.png`)_

---

## Принципы работы:

-   ✅ Все переменные через `get_config()`.
-   ✅ Чистые импорты `core/`, `telegram/`, `common/`.
-   ✅ Нет прямой загрузки `.env` и `config.py`.
-   ✅ Ruff auto-fix + compileall перед коммитом.

---

Краткое резюме
В проекте конфигурация задана фрагментарно: часть параметров хранится в файле .env, часть – в устаревшем config.py, а также некоторые настройки уже перенесены в common/config_loader.py. Такая раздробленность приводит к дублированию и ошибкам (неопределённые имена, некорректные импорты и пр.). Цель – объединить все ключевые настройки в common/config_loader.py, убрать config.py и исправить импорты. По результатам анализа: все важные переменные окружения и параметры из config.py нужно перенести (с помощью get_config() и дефолтов) в config_loader.py, после чего заменить обращения к ним на from common.config_loader import .... При таком подходе config.py можно удалить без потерь, а структура проекта станет единообразной и устойчивой.
Перечень основных переменных конфигурации
Переменные окружения (.env): API_KEY, API_SECRET, API_KEY_TESTNET, API_SECRET_TESTNET, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID и др. Эти значения загружаются через get_config() и теперь централизованы в config_loader.py.
Флаги и опции: USE_TESTNET, DRY_RUN, USE_HTF_CONFIRMATION, ADAPTIVE_SCORE_ENABLED, VERBOSE и т.п. Все они по умолчанию берутся через get_config(…, default).
Логирование: LOG_FILE_PATH, LOG_LEVEL, TIMEZONE и пр. В частности, стоит перенести в config_loader.py переменную TIMEZONE (как pytz.timezone(get_config("TIMEZONE","Europe/Bratislava"))), чтобы штатно использовать её в модулях аналитики.
Торговые настройки: константы и словари вроде LEVERAGE_MAP, MIN_NOTIONAL_OPEN, MIN_NOTIONAL_ORDER, SL_PERCENT, TP1_PERCENT, TP2_PERCENT, TP2_SHARE, MAX_MARGIN_PERCENT, MIN_TRADE_SCORE, MAX_POSITIONS и др. Они ранее были в config.py и должны быть объявлены (с нужными значениями) в config_loader.py. Многие из них можно сделать настраиваемыми через .env с дефолтами.
Счётчик и флаги времени исполнения: RUNNING, trade_stats и trade_stats_lock. Эти объекты (флаг остановки бота и статистика сделок) упоминаются в stats.py и telegram_commands.py. Их тоже следует инициализировать в config_loader.py (например, RUNNING = True, trade_stats_lock = Lock() и т.д.), чтобы модули могли импортировать их через common.config_loader.
Периодичность и пределы: IP_MONITOR_INTERVAL_SECONDS, UPDATE_INTERVAL_SECONDS, MAX_OPEN_ORDERS, SOFT_EXIT_ENABLED/SHARE/THRESHOLD, ENABLE_TRAILING, BREAKEVEN_TRIGGER и др. Все они определены в старом config.py и теперь должны жить в единой конфигурации.
Таблица примеров старых и новых импортов
Старый импорт Новый импорт (common/config_loader.py)
from config import DRY_RUN, API_KEY, ...
USE_TESTNET = True (в коде) from common.config_loader import DRY_RUN, API_KEY, ...
import config
config.RUNNING = False (в telegram_commands.py) from common.config_loader import RUNNING
RUNNING = False
from config import LEVERAGE_MAP, TP1_PERCENT, ... (например, в strategy.py) from common.config_loader import LEVERAGE_MAP, TP1_PERCENT, ...
from common.config_loader import get_config, ... # некорректный перенос (исправлен) from common.config_loader import get_config, USE_TESTNET, ...
или перечисление переменных без разрыва строки
from common.config_loader import CONFIG_FILE, TP_ML_MIN_TRADES_FULL, ... (сброс в tp_optimizer_ml.py) from common.config_loader import CONFIG_FILE, TP_ML_MIN_TRADES_FULL, ... (при условии, что эти константы добавлены в config_loader)

В целом все упоминания from config import ... или config.X должны быть заменены на импорты из common.config_loader. Также необходимо поправить многострочные импорты (весьма похожие на примеры выше) – они сейчас разбиты некорректно и вызывают ошибки синтаксиса (F821). После добавления нужных имен в config_loader синтаксис можно упростить до одной строки или корректно оформить через скобки.
Рекомендации по улучшению архитектуры
Централизовать конфигурацию: Перенести абсолютно все параметры (от API-ключей до флагов стратегии и лимитов) в common/config_loader.py, используя get_config() с понятными значениями по умолчанию. Это устранит дублирование и позволит управлять настройками через единый .env или один конфигурационный файл.
Упрощение импортов: Использовать именованные импорты вместо импортов целого модуля. Вместо import config и обращения config.X стоит всегда писать from common.config_loader import X. Это ускорит выявление отсутствующих переменных (имена F821) и избавит от путаницы.
Корректировка многострочных импортов: Избегать разрывов строк после комментариев в from ... import (...). Правильный стиль – либо одна строка с перечислением через запятую, либо многострочная запись в скобках без лишних символов. Это снимет ряд синтаксических ошибок.
Разделение статуса и настроек: Текущая реализация смешивает конфигурацию (параметры стратегии) и состояние во время выполнения (флаги RUNNING, статистика сделок). Для чистоты архитектуры имеет смысл хранить глобальный статус отдельно (например, в модуле state.py), а в конфиге держать только неизменяемые параметры. Но на практике можно начать с минимального подхода – вынести то, что нужно статистике/командам, в config_loader и в будущем переработать при необходимости.
Обработка окружений: Использовать USE_TESTNET или другие флаги среды через .env. Например, сделать так, чтобы при USE_TESTNET=True автоматически выбирался нужный URL API и ключи тестнета. Таким образом не придётся жёстко править код – достаточно задавать нужные значения в .env.
Проверка цикличности: Убедиться, что common/config_loader.py не импортирует модули из приложения (чтобы не было кольцевых зависимостей). В предложенном решении config_loader содержит только os, dotenv, pytz, threading.Lock и свои константы, что безопасно.
В результате этих изменений структура проекта станет чище: все настройки – в одном месте, нет дублирования и «тайных» импортов, код проще поддерживать и расширять. Это избавит от ошибок F821/ImportError и сделает проект более устойчивым и читабельным.

Готов запускать!
