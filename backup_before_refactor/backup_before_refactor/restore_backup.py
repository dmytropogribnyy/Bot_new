import os
import shutil

backup_dir = "./backup_before_refactor"
restore_dir = "."

for foldername, subfolders, filenames in os.walk(backup_dir):
    for filename in filenames:
        backup_path = os.path.join(foldername, filename)
        rel_path = os.path.relpath(backup_path, backup_dir)
        restore_path = os.path.join(restore_dir, rel_path)

        os.makedirs(os.path.dirname(restore_path), exist_ok=True)
        shutil.copy2(backup_path, restore_path)

print("\n✅ Restore completed! Project reverted to backup state.")
