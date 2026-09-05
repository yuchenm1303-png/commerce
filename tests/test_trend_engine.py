from datetime import datetime, timedelta, timezone

import pytest

from commerce.domain import ProductSnapshot
from commerce.trend import TrendEngine


def snapshot(hour: int, *, sales: float, wants: float | None = None, rank: float | None = None):
    return ProductSnapshot(
        source="test",
        external_id="sku-1",
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=hour),
        sales_count=sales,
        wants_count=wants,
        rank=rank,
    )


def test_sales_velocity_and_acceleration_are_deterministic():
    signals = TrendEngine().analyze(
        [
            snapshot(0, sales=100),
            snapshot(2, sales=120),
            snapshot(4, sales=160),
        ],
        metrics=["sales_count"],
    )

    signal = signals[0]
    assert signal.delta == 60
    assert signal.velocity_per_hour == 15
    assert signal.acceleration_per_hour2 == 5
    assert signal.direction == "rising"
    assert signal.quality_direction == "improving"


def test_rank_falling_is_an_improvement():
    signal = TrendEngine().analyze(
        [snapshot(0, sales=0, rank=50), snapshot(2, sales=0, rank=20)],
        metrics=["rank"],
    )[0]

    assert signal.delta == -30
    assert signal.direction == "falling"
    assert signal.quality_direction == "improving"


def test_missing_metrics_are_not_invented():
    signals = TrendEngine().analyze(
        [snapshot(0, sales=1), snapshot(1, sales=2)],
        metrics=["wants_count"],
    )
    assert signals == []
