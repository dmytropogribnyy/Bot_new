from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_UP, Decimal
from typing import Literal

Number = float | int | Decimal


def _D(x: Number) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def round_to_tick(
    price: Number,
    tick_size: Number,
    direction: Literal["nearest", "down", "up"] = "nearest",
) -> float:
    p = _D(price)
    tick = _D(tick_size)
    if tick <= 0:
        raise ValueError("tick_size must be > 0")
    rounding = {
        "nearest": ROUND_HALF_EVEN,
        "down": ROUND_DOWN,
        "up": ROUND_UP,
    }[direction]
    return float(p.quantize(tick, rounding=rounding))


def round_to_step(
    qty: Number,
    step_size: Number,
    direction: Literal["down", "up"] = "down",
) -> float:
    q = _D(qty)
    step = _D(step_size)
    if step <= 0:
        raise ValueError("step_size must be > 0")
    rounding = ROUND_DOWN if direction == "down" else ROUND_UP
    return float(q.quantize(step, rounding=rounding))


def min_price_buffer(
    ref_price: Number,
    tick_size: Number,
    min_basis_points: float = 2.0,
    min_ticks: int = 2,
) -> float:
    ref = _D(ref_price)
    tick = _D(tick_size)
    bp = _D(min_basis_points) / _D(10000)
    return float(max(_D(min_ticks) * tick, ref * bp))


def nudge_price(
    price: Number,
    current_price: Number,
    tick_size: Number,
    *,
    side: Literal["buy", "sell"],
    is_sl: bool,
    min_ticks: int = 1,
) -> float:
    p = _D(price)
    cur = _D(current_price)
    tick = _D(tick_size)
    if tick <= 0:
        raise ValueError("tick_size must be > 0")

    # For original entry side: SL must be against PnL direction
    # want_less True -> target below current; want_less False -> target above current
    want_less = (side == "buy" and is_sl) or (side == "sell" and not is_sl)
    wrong_or_equal = (p >= cur) if want_less else (p <= cur)

    if wrong_or_equal:
        shift = _D(min_ticks) * tick
        p = (cur - shift) if want_less else (cur + shift)
        p = _D(round_to_tick(p, tick, direction="down" if want_less else "up"))
    else:
        dist_ticks = (cur - p) / tick if want_less else (p - cur) / tick
        if dist_ticks < _D(min_ticks):
            need = (_D(min_ticks) - dist_ticks) * tick
            p = p - need if want_less else p + need
            p = _D(round_to_tick(p, tick, direction="down" if want_less else "up"))

    return float(p)


def ensure_minimums(
    qty: Number,
    price: Number,
    *,
    step_size: Number,
    min_qty: Number | None = None,
    min_notional: Number | None = None,
    allow_increase: bool = True,
) -> float:
    q = _D(round_to_step(qty, step_size, direction="down"))
    p = _D(price)

    def bump(q_now: Decimal) -> Decimal:
        return _D(round_to_step(float(q_now + _D(step_size)), step_size, direction="up"))

    if min_qty is not None and q < _D(min_qty):
        if not allow_increase:
            raise ValueError(f"qty {q} < min_qty {min_qty}")
        q = bump(_D(min_qty))

    if min_notional is not None and q * p < _D(min_notional):
        if not allow_increase:
            raise ValueError(f"qty*price {q * p} < min_notional {min_notional}")
        target = _D(min_notional) / p
        q = _D(round_to_step(float(target), step_size, direction="up"))

    return float(q)
