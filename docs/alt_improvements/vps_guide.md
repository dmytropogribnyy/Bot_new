🧭 Оптимальный гайд: Windows + Hetzner + tmux для запуска бота
🔧 Что тебе нужно:
✅ Hetzner Cloud VPS (например, CX32 — 2 vCPU / 8 GB RAM)

✅ SSH-клиент на Windows — лучший вариант: [Windows Terminal] или [Termius]

✅ Установленный Python-бот в GitHub или локально

📦 1. Создай VPS в Hetzner
Зарегистрируйся: https://console.hetzner.cloud

Создай новый сервер (тип CX21/32, Ubuntu 22.04)

Сгенерируй SSH-ключ → вставь в Hetzner при создании

🔐 2. Подключись с Windows к VPS
Через Windows Terminal:

bash
Copy
Edit
ssh root@<твой*IP*адрес_Hetzner>
(если используешь Termius — тоже просто: создать соединение → вставить ключ)

🧰 3. Установи всё на VPS
bash
Copy
Edit
apt update && apt install git tmux python3-pip python3-venv -y
git clone https://github.com/you/yourbot.git
cd yourbot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
🚀 4. Запуск бота через tmux
bash
Copy
Edit
tmux new -s bot
source venv/bin/activate
python main.py --config runtime_config.json
📌 После запуска — нажми Ctrl + B, потом D
→ ты отсоединишься, но бот продолжит работать в фоне

🔄 5. Вернуться к боту:
bash
Copy
Edit
tmux attach -t bot
🛑 6. Остановить бота:
Внутри tmux → нажми Ctrl + C
Бот завершится, но tmux-сессия будет жива

🔁 7. Обновить бота с GitHub:
bash
Copy
Edit
cd yourbot
git pull
Если приватный репозиторий:

Используй SSH-ключ или token в URL

Или настрой .netrc / ~/.ssh/config

📲 8. Мониторинг с iPhone:
Через Telegram-бот (уведомления + команды)

Через Termius App → SSH → tmux attach

Через Hetzner Cloud App — посмотреть статус VPS

✅ Готово!
Ты теперь можешь запускать, перезапускать, обновлять и контролировать своего бота 24/7 с любого устройства,
даже если ноутбук выключен — VPS и tmux всё держат надёжно.
