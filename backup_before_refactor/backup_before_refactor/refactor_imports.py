import os
import shutil

# Настройки
root_dir = "."
backup_dir = "./backup_before_refactor"

# Что заменить
replacements = {
    "from config import": "from common.config_loader import get_config  # updated",
    "from notifier import": "from common.messaging import send_notification, send_error  # updated",
    "send_message(": "send_notification(",
    "send_error_message(": "send_error(",
}

# Создание бэкапа
os.makedirs(backup_dir, exist_ok=True)

# Проход по проекту
for foldername, subfolders, filenames in os.walk(root_dir):
    if (
        "venv" in foldername
        or "__pycache__" in foldername
        or ".git" in foldername
        or "test-output" in foldername
    ):
        continue

    for filename in filenames:
        if filename.endswith(".py"):
            full_path = os.path.join(foldername, filename)
            rel_path = os.path.relpath(full_path, root_dir)

            # Копируем в backup
            backup_path = os.path.join(backup_dir, rel_path)
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy2(full_path, backup_path)

            # Заменяем строки
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content

            for old, new in replacements.items():
                content = content.replace(old, new)

            if content != original_content:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"Updated: {rel_path}")

print("\n✅ Refactoring completed! Backup stored in 'backup_before_refactor/'")
