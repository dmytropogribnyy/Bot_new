#!/usr/bin/env python3
"""Simple JSON-backed idempotency key store.

Provides a minimal persistence layer mapping an `intent_key` to a
`clientOrderId` with a timestamp. The store is intended for lightweight,
append-mostly usage with atomic writes to avoid corruption on Windows.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any


class IdempotencyStore:
    def __init__(self, path: str):
        self.path = path
        self._cache: dict[str, dict[str, Any]] = {}

    def load(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                self._cache = json.load(f)
        else:
            self._cache = {}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False)
        os.replace(tmp, self.path)  # атомарно

    def get(self, intent_key: str) -> str | None:
        rec = self._cache.get(intent_key)
        return rec["id"] if isinstance(rec, dict) and "id" in rec else None

    def put(self, intent_key: str, client_id: str) -> None:
        self._cache[intent_key] = {"id": client_id, "ts": time.time()}
        self.save()

    def cleanup_old(self, days: int = 7) -> None:
        cutoff = time.time() - days * 86_400
        self._cache = {k: v for k, v in self._cache.items() if isinstance(v, dict) and v.get("ts", 0) > cutoff}
        self.save()
