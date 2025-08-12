import compileall
import pathlib

exclude_dirs = {".git", ".venv", "venv", ".ruff_cache", "__pycache__", "backup_before_refactor"}


def should_include(path):
    return not any(excluded in path.parts for excluded in exclude_dirs)


project_root = pathlib.Path(".").resolve()

print("\n🔎 Scanning project...\n")

files_to_check = [str(path) for path in project_root.rglob("*.py") if should_include(path)]

if not files_to_check:
    print("⚠️ No files found to compile.")
else:
    failed_files = []

    for file in files_to_check:
        print(f"Compiling: {file}")
        success = compileall.compile_file(file, force=True, quiet=1)
        if not success:
            failed_files.append(file)

    if failed_files:
        print("\n❌ Compilation failed for:")
        for f in failed_files:
            print(f" - {f}")
    else:
        print("\n✅ All files compiled successfully.")
