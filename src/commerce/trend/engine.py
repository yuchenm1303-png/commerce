from __future__ import annotations

from collections.abc import Iterable

from commerce.domain import ProductSnapshot, TrendSignal


DEFAULT_METRICS = (
    "sales_count",
    "views_count",
    "wants_count",
    "reviews_count",
    "rank",
    "price",
)

# +1 means larger values are normally favorable; -1 means smaller values are.
_METRIC_POLARITY = {
    "sales_count": 1,
    "views_count": 1,
    "wants_count": 1,
    "reviews_count": 1,
    "rank": -1,
}


class TrendEngine:
    """Deterministic time-series signal calculator.

    This layer never asks an LLM to do arithmetic. It only turns observations
    into auditable deltas, velocities and acceleration signals.
    """

    def analyze(
        self,
        snapshots: Iterable[ProductSnapshot],
        *,
        metrics: Iterable[str] = DEFAULT_METRICS,
    ) -> list[TrendSignal]:
        ordered = sorted(snapshots, key=lambda item: item.observed_at)
        return [
            signal
            for metric in metrics
            if (signal := self._metric_signal(ordered, metric)) is not None
        ]

    def _metric_signal(
        self, snapshots: list[ProductSnapshot], metric: str
    ) -> TrendSignal | None:
        points = [
            (snapshot.observed_at, value)
            for snapshot in snapshots
            if (value := snapshot.metric(metric)) is not None
        ]
        if len(points) < 2:
            return None

        first_time, start_value = points[0]
        last_time, end_value = points[-1]
        window_hours = (last_time - first_time).total_seconds() / 3600
        if window_hours <= 0:
            return None

        delta = end_value - start_value
        velocity = delta / window_hours
        acceleration = self._latest_acceleration(points)
        direction = "flat"
        if delta > 0:
            direction = "rising"
        elif delta < 0:
            direction = "falling"

        polarity = _METRIC_POLARITY.get(metric)
        if delta == 0:
            quality_direction = "flat"
        elif polarity is None:
            quality_direction = "unknown"
        elif delta * polarity > 0:
            quality_direction = "improving"
        else:
            quality_direction = "deteriorating"

        return TrendSignal(
            metric=metric,
            observations=len(points),
            first_observed_at=first_time,
            last_observed_at=last_time,
            window_hours=round(window_hours, 6),
            start_value=start_value,
            end_value=end_value,
            delta=round(delta, 6),
            velocity_per_hour=round(velocity, 6),
            acceleration_per_hour2=(
                round(acceleration, 6) if acceleration is not None else None
            ),
            direction=direction,
            quality_direction=quality_direction,
        )

    @staticmethod
    def _latest_acceleration(points: list[tuple]) -> float | None:
        if len(points) < 3:
            return None

        (t1, y1), (t2, y2), (t3, y3) = points[-3:]
        dt1 = (t2 - t1).total_seconds() / 3600
        dt2 = (t3 - t2).total_seconds() / 3600
        if dt1 <= 0 or dt2 <= 0:
            return None

        v1 = (y2 - y1) / dt1
        v2 = (y3 - y2) / dt2
        midpoint_hours = (dt1 + dt2) / 2
        return (v2 - v1) / midpoint_hours
