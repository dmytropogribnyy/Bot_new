import ast
import os

# Путь к config_loader
CONFIG_LOADER_PATH = os.path.join("common", "config_loader.py")


# Соберём все переменные, реально объявленные в config_loader.py
def get_declared_variables():
    declared = set()
    with open(CONFIG_LOADER_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        declared.add(target.id)
    return declared


# Найдём все импорты из common.config_loader
def get_imported_variables():
    imported = set()
    for root, dirs, files in os.walk("."):
        # Пропускаем виртуальные окружения и кэш
        if any(skip in root for skip in ["venv", "__pycache__", ".ruff_cache", ".git"]):
            continue
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read())
                        for node in tree.body:
                            if isinstance(node, ast.ImportFrom) and node.module == "common.config_loader":
                                for alias in node.names:
                                    imported.add(alias.name)
                    except SyntaxError:
                        pass  # можно добавить лог, если нужно
    return imported


def main():
    declared = get_declared_variables()
    imported = get_imported_variables()

    missing = imported - declared

    if not missing:
        print("✅ Все импортируемые переменные объявлены в config_loader.py!")
    else:
        print("❌ Не найдены в config_loader.py переменные:")
        for var in sorted(missing):
            print(f" - {var}")


if __name__ == "__main__":
    main()
