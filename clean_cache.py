import os
import shutil


def clean_pycache(root_dir="."):
    for foldername, _subfolders, _filenames in os.walk(root_dir):
        if "__pycache__" in foldername:
            print(f"Удаление папки: {foldername}")
            shutil.rmtree(foldername)
    print("\n✅ Все папки __pycache__ удалены.")


def clean_pyc_files(root_dir="."):
    for foldername, _subfolders, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".pyc"):
                file_path = os.path.join(foldername, filename)
                print(f"Удаление файла: {file_path}")
                os.remove(file_path)
    print("\n✅ Все файлы *.pyc удалены.")


if __name__ == "__main__":
    clean_pycache()
    clean_pyc_files()
