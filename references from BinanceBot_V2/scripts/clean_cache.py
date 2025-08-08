#!/usr/bin/env python3
import shutil
from pathlib import Path


def clean_project():
    """Очищает кеш проекта"""

    # Удаляем __pycache__
    for pycache in Path(".").rglob("__pycache__"):
        print(f"Removing: {pycache}")
        shutil.rmtree(pycache)

    # Удаляем .pyc файлы
    for pyc in Path(".").rglob("*.pyc"):
        print(f"Removing: {pyc}")
        pyc.unlink()

    # Очищаем логи
    log_dir = Path("logs")
    if log_dir.exists():
        for log in log_dir.glob("*.log"):
            print(f"Removing: {log}")
            log.unlink()

    print("\n✅ Cleanup complete!")


if __name__ == "__main__":
    clean_project()
