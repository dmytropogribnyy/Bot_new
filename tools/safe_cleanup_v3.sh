#!/usr/bin/env bash
# Safe cleanup script v3 (no code deletions)
set -euo pipefail

echo "🧹 Starting safe cleanup (no code files will be deleted)..."

# 1) Backup selected configs
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "📦 Creating backup in $BACKUP_DIR"
cp -r data/backup "$BACKUP_DIR/" 2>/dev/null || true
cp .env "$BACKUP_DIR/" 2>/dev/null || true

# 2) Python caches
echo "🗑️ Removing Python caches..."
find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
rm -rf .pytest_cache .ruff_cache .mypy_cache 2>/dev/null || true

# 3) Logs (truncate, keep structure)
echo "📝 Truncating logs..."
[ -f logs/main.log ] && : > logs/main.log || true
find logs -type f -name "*.log" -size +10M -delete 2>/dev/null || true

# 4) Temp artifacts
echo "🧹 Removing temp files..."
find . -type f -name "*.tmp" -delete 2>/dev/null || true
find . -type f -name "*.bak" -delete 2>/dev/null || true
find . -type f -name "*.swp" -delete 2>/dev/null || true

# 5) Optional: archive old docs (comment out to disable)
# mkdir -p references_archive/$(date +%Y-%m)
# if [ -d docs/Archive ]; then
#   rsync -a --remove-source-files docs/Archive/ references_archive/$(date +%Y-%m)/ || true
#   find docs/Archive -type d -empty -delete || true
# fi

echo "✅ Cleanup complete."
du -sh . | awk '{print "📊 Repo size now:", $1}'
