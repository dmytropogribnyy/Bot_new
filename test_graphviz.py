import os
import re
from graphviz import Digraph

# Настройки
root_dir = "."
exclude_dirs = {
    "venv",
    "__pycache__",
    ".ruff_cache",
    ".vscode",
    "data",
    "docs",
    "test-output",
    ".git",
}
exclude_files = {"__init__.py"}

# Создаём граф
dot = Digraph(comment="BinanceBot Real Imports", format="png")
dot.attr(rankdir="LR")

nodes = {}

# Проход по всем .py файлам
for foldername, subfolders, filenames in os.walk(root_dir):
    if any(excluded in foldername for excluded in exclude_dirs):
        continue

    rel_folder = os.path.relpath(foldername, root_dir).replace("\\", "/")
    for filename in filenames:
        if filename.endswith(".py") and filename not in exclude_files:
            filepath = os.path.join(foldername, filename)
            module_name = os.path.relpath(filepath, root_dir).replace("\\", "/")
            nodes[module_name] = filepath

# Добавляем узлы
for node in nodes:
    dot.node(node, node)

# Добавляем связи по импортам
for node, filepath in nodes.items():
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        for other_node in nodes:
            other_module = os.path.splitext(os.path.basename(other_node))[0]

            # Простая проверка по имени модуля
            if re.search(rf"\bimport {other_module}\b", content) or re.search(
                rf"\bfrom .*{other_module}\b", content
            ):
                if node != other_node:  # чтобы не рисовать стрелку на себя
                    dot.edge(node, other_node)

    except Exception as e:
        print(f"Ошибка чтения {filepath}: {e}")

# Сохраняем
os.makedirs("test-output", exist_ok=True)
output_path = "test-output/binancebot_imports"
dot.render(output_path, view=True)

print(f"Импорт-граф построен и сохранён в {output_path}.png")
