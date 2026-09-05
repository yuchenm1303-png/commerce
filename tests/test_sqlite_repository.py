from datetime import datetime, timedelta, timezone

from commerce.domain import ProductSnapshot
from commerce.infrastructure import SQLiteSnapshotRepository


def test_snapshot_history_is_append_only_and_ordered(tmp_path):
    repo = SQLiteSnapshotRepository(str(tmp_path / "commerce.sqlite3"))
    later = ProductSnapshot(
        source="goofish",
        external_id="123",
        observed_at=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
        wants_count=12,
    )
    earlier = ProductSnapshot(
        source="goofish",
        external_id="123",
        observed_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
        wants_count=5,
    )

    repo.save(later)
    repo.save(earlier)
    repo.save(earlier)  # duplicate observation should be idempotent

    history = repo.list_for_product("goofish", "123")
    assert [item.wants_count for item in history] == [5, 12]
