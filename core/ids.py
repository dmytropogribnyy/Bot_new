#!/usr/bin/env python3
"""Utilities for generating stable, compact client order IDs.

This module provides helpers to sanitize ID components, generate short hashes,
and compose a `clientOrderId` string that is concise, readable, and respects a
maximum length limit typical for exchange APIs.
"""

from __future__ import annotations

import hashlib
import re
import time


def sanitize_id_component(s: str) -> str:
    """
    Сохраняем семантику символов:
    '/' -> 'SLASH', '-' -> 'DASH', остальное чистим до [A-Z0-9_].
    """
    s = (s or "").upper().strip()
    s = s.replace("/", "SLASH").replace("-", "DASH")
    return re.sub(r"[^A-Z0-9_]", "_", s)


def short_hash(*parts: str, n: int = 8) -> str:
    """Return the first `n` hex characters of a SHA-256 of the joined parts."""
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:n]


def ensure_max_len(s: str, max_len: int = 36) -> str:
    """Ensure `s` does not exceed `max_len`, appending a short hash if needed."""
    if len(s) <= max_len:
        return s
    head = s[: max_len - 9]
    return f"{head}-{short_hash(s, n=8)}"


def make_client_id(
    env: str,
    strategy: str,
    symbol: str,
    side: str,
    intent_key: str,
    ts_ms: int | None = None,
    max_len: int = 36,
) -> str:
    """Create a client order ID that is stable within a 1-second bucket.

    Components are sanitized to preserve special character semantics and
    normalized to uppercase alphanumerics with underscores. A short hash of the
    `intent_key` is included to disambiguate similar keys.
    """
    env = sanitize_id_component(env)
    strategy = sanitize_id_component(strategy)
    symbol = sanitize_id_component(symbol)
    side = sanitize_id_component(side)
    intent_key = sanitize_id_component(intent_key)

    bucket = int((ts_ms or int(time.time() * 1000)) / 1000)  # секунды
    base = f"{env}-{strategy}-{symbol}-{side}-{bucket}-{short_hash(intent_key, n=6)}"
    return ensure_max_len(base, max_len)
