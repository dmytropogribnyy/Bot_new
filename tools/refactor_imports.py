import os
import re
import shutil

# Папки, которые пропускаем при обходе
EXCLUDE_DIRS = {"venv", "__pycache__", ".git", "test-output"}

root_dir = "."
backup_dir = "./backup_before_refactor"
os.makedirs(backup_dir, exist_ok=True)

# Шаблоны (regex) → строка-замена
patterns = {
    r"from\s+common\.config_loader\s+import\s+get_config(\s*#\s*updated)?": "from common.config_loader import get_config  # updated",
    r"send_notification\s*\(": "send_notification(",
    r"send_error\s*\(": "send_error(",
}

updated_count = 0

for foldername, _, filenames in os.walk(root_dir):
    # Пропускаем системные папки
    if any(exc in foldername for exc in EXCLUDE_DIRS):
        continue

    for filename in filenames:
        if filename.endswith(".py"):
            full_path = os.path.join(foldername, filename)
            rel_path = os.path.relpath(full_path, root_dir)

            # Бэкапим файл
            backup_path = os.path.join(backup_dir, rel_path)
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy2(full_path, backup_path)

            # Читаем исходник
            with open(full_path, encoding="utf-8") as f:
                content = f.read()

            original_content = content

            # Применяем все регулярные замены
            for pattern, replacement in patterns.items():
                content = re.sub(pattern, replacement, content)

            # Если изменилось — перезаписываем и выводим
            if content != original_content:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"Updated: {rel_path}")
                updated_count += 1

print(f"\n✔️ Total files updated: {updated_count}")
print("✅ Refactoring completed! Backup stored in 'backup_before_refactor/'")
