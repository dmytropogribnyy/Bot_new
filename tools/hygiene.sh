#!/usr/bin/env bash
set -euo pipefail

echo "=== Stage A: Smart Repository Hygiene ==="
echo "========================================="

MODE="${1:---dry-run}"
if [[ "$MODE" != "--dry-run" && "$MODE" != "--force" ]]; then
  echo "Usage: $0 [--dry-run|--force]"
  echo "  --dry-run  Preview changes without modifying files"
  echo "  --force    Execute changes"
  exit 1
fi

DRY_RUN=1
ACTION="echo [DRY-RUN] would:"
if [[ "$MODE" == "--force" ]]; then
  DRY_RUN=0
  ACTION=""
  echo "🚀 Running in FORCE mode - files will be modified!"
else
  echo "👀 Running in DRY-RUN mode - no files will be changed"
fi
echo ""

# Ensure directory structure
ARCHIVE_DIR="references_archive/$(date +%Y-%m)"
LEGACY_DIR="core/legacy"

echo "📁 Creating directory structure..."
mkdir -p "$ARCHIVE_DIR"
mkdir -p "$LEGACY_DIR"
echo "   ✓ Archive: $ARCHIVE_DIR"
echo "   ✓ Legacy:  $LEGACY_DIR"
echo ""

# Update .gitignore (idempotent)
ensure_ignore() {
  local entry="$1"
  if ! grep -qF "$entry" .gitignore 2>/dev/null; then
    if [[ $DRY_RUN -eq 1 ]]; then
      echo "[DRY-RUN] would: add '$entry' to .gitignore"
    else
      echo "$entry" >> .gitignore
      echo "   ✓ Added to .gitignore: $entry"
    fi
  fi
}

echo "📝 Updating .gitignore..."
touch .gitignore
ensure_ignore "core/legacy/"
ensure_ignore "references_archive/"
ensure_ignore ".ruff_cache/"
ensure_ignore ".mypy_cache/"
ensure_ignore "__pycache__/"

# Helper functions
get_ext() {
  local f="$1"
  local base="$(basename "$f")"
  local ext="${base##*.}"
  [[ "$base" == "$ext" ]] && echo "" || echo "${ext,,}"
}

is_doc_media() {
  local ext="$1"
  case "$ext" in
    md|rst|txt|pdf|doc|docx|png|jpg|jpeg|gif|svg|csv|xlsx|xls|tsv|xml)
      return 0;;
    *) return 1;;
  esac
}

is_bin_trash() {
  local ext="$1"
  case "$ext" in
    exe|dll|bin|obj|o|class|pyc|pyo|log|tmp|swp|swo|bak|orig)
      return 0;;
    *) return 1;;
  esac
}

is_used() {
  local name="$1"
  local base="${name%.*}"
  grep -r \
    --include="*.py" --include="*.json" --include="*.yaml" --include="*.yml" \
    --include="*.toml" --include="*.ini" --include="requirements*.txt" \
    --exclude-dir=".git" --exclude-dir=".venv" --exclude-dir="references_archive" \
    --exclude-dir="core/legacy" --exclude-dir="__pycache__" \
    -l "$base" . >/dev/null 2>&1
}

# Process functions
move_to_archive() {
  local src="$1"
  local dest="$ARCHIVE_DIR/$(basename "$src")"
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[DRY-RUN] would: archive '$src' → '$dest'"
  else
    mkdir -p "$(dirname "$dest")"
    if git ls-files --error-unmatch "$src" >/dev/null 2>&1; then
      git mv "$src" "$dest" 2>/dev/null || mv "$src" "$dest"
    else
      mv "$src" "$dest"
    fi
    echo "   📦 Archived: $src"
  fi
}

delete_file() {
  local src="$1"
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[DRY-RUN] would: delete '$src'"
  else
    if git ls-files --error-unmatch "$src" >/dev/null 2>&1; then
      git rm -f "$src" 2>/dev/null || rm -f "$src"
    else
      rm -f "$src"
    fi
    echo "   🗑️  Deleted: $src"
  fi
}

# Counters
ARCHIVED_CNT=0
DELETED_CNT=0
KEPT_CNT=0

process_file() {
  local f="$1"
  [[ ! -f "$f" ]] && return 0
  [[ "$f" == *"references_archive"* ]] && return 0
  [[ "$f" == *"core/legacy"* ]] && return 0

  local base="$(basename "$f")"
  local ext="$(get_ext "$f")"

  if is_doc_media "$ext"; then
    move_to_archive "$f"
    ((ARCHIVED_CNT++))
  elif is_bin_trash "$ext"; then
    if is_used "$base"; then
      echo "   ⚠️  Keep: '$base' (binary but referenced)"
      ((KEPT_CNT++))
    else
      delete_file "$f"
      ((DELETED_CNT++))
    fi
  else
    echo "   ✓ Keep: '$f' (code/config)"
    ((KEPT_CNT++))
  fi
}

# Find and process reference directories
echo "🔍 Scanning for reference directories..."
while IFS= read -r -d '' dir; do
  [[ "$dir" == "." ]] && continue
  echo "   Found: $dir"
  while IFS= read -r -d '' file; do
    process_file "$file"
  done < <(find "$dir" -type f -print0 2>/dev/null)
done < <(find . -type d \( -iname "*reference*" -o -iname "*ReferenceSRAM*" \) -not -path "./.git/*" -not -path "./references_archive/*" -print0 2>/dev/null)

# Process top-level reference files
echo "🔍 Scanning for top-level reference files..."
while IFS= read -r -d '' file; do
  process_file "$file"
done < <(find . -maxdepth 1 -type f \( -iname "*reference*" -o -iname "*ReferenceSRAM*" \) -print0 2>/dev/null)

# Clean caches
echo ""
echo "🧹 Cleaning caches..."
if [[ $DRY_RUN -eq 1 ]]; then
  echo "[DRY-RUN] would: remove Python caches"
else
  find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
  rm -rf .ruff_cache .mypy_cache .pytest_cache 2>/dev/null || true
  echo "   ✓ Cleaned: __pycache__, .ruff_cache, .mypy_cache"
fi

# Summary
echo ""
echo "=== Summary ==="
echo "📦 Archived:    $ARCHIVED_CNT files"
echo "🗑️  Deleted:     $DELETED_CNT files"
echo "✓ Kept:        $KEPT_CNT files"
echo "📁 Archive:     $ARCHIVE_DIR"
echo "📁 Legacy:      $LEGACY_DIR"
echo "Mode:          $MODE"
echo ""
echo "✅ Stage A hygiene complete!"

if [[ $DRY_RUN -eq 1 ]]; then
  echo ""
  echo "💡 To apply changes, run: $0 --force"
fi
