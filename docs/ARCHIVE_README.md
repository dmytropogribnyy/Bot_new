# Archive and Legacy Policy (August 2025)

Strict rules for isolating legacy components while keeping history:

1) Do not hide legacy under .gitignore. Keep tracked for transparency.
2) If legacy code is not imported by runtime, move it under `archive/2025-08/` preserving structure.
3) If runtime imports exist, do NOT move; instead, add a README warning and create an Issue: "Remove legacy import in <module>".
4) Archived code must not be imported at runtime. CI may fail if imports are detected.
5) Always create a backup before restructuring. Never delete `data/backup/*`.

Directory layout example:

```
archive/
  2025-08/
    core_legacy/
    dev_tools/
  README.md
```

Migration Guide:
- Identify imports: search for `from core.legacy` or `import core.legacy`.
- Replace with modern equivalents or adapters.
- Add unit tests for migrated modules.
- Only then move modules into `archive/2025-08/core_legacy/`.

Safety:
- No code deletions during archive moves.
- No runtime imports from `archive/**`.


# Archive Policy

## ⚠️ WARNING: Legacy Code — DO NOT USE IN PRODUCTION

This `archive/` folder contains:
- **Legacy modules** replaced by v2 architecture
- **Historical code** for reference only
- **Deprecated tools** no longer maintained

## Structure
archive/
├── 2025-08/
│   ├── core_legacy/      # Old core modules (replaced by v2)
│   ├── dev_tools/        # Obsolete development tools
│   └── README.md         # What was archived and why

## Rules
1. **NEVER import** from this directory in production code.
2. **DO NOT add** to `.gitignore` (keep for historical reference).
3. If accidentally imported, **raise ImportError** with a clear message and a link to this policy.
4. **Date folders** show when code was archived.

## Migration Guide (keep expanding)
| Old Module                        | New Replacement              | Notes                  |
|----------------------------------|------------------------------|------------------------|
| core/legacy/trade_engine.py      | core/trade_engine_v2.py      | Async, simplified      |
| core/legacy/binance_api.py       | core/exchange_client.py      | CCXT-based             |
| core/legacy/position_manager.py  | core/order_manager.py        | Unified OMS            |
| ...                              | ...                          | ...                    |
