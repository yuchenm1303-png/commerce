import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from commerce.application import OpportunityPipeline, SourceDiscoveryError, SourceScanService
from commerce.domain import ProductRef, ProductSnapshot
from commerce.infrastructure import SQLiteSnapshotRepository


class SequencedSource:
    name = "goofish"

    def __init__(self, *, fail_ids: set[str] | None = None, fail_discovery: bool = False):
        self.round = 0
        self.fail_ids = fail_ids or set()
        self.fail_discovery = fail_discovery

    async def discover(self, query: str, *, limit: int = 100) -> list[ProductRef]:
        if self.fail_discovery:
            raise RuntimeError("search unavailable")
        self.round += 1
        products = [
            ProductRef(
                source="goofish",
                external_id="a",
                url="https://www.goofish.com/item?id=a",
                title=f"{query} A",
            ),
            ProductRef(
                source="goofish",
                external_id="b",
                url="https://www.goofish.com/item?id=b",
                title=f"{query} B",
            ),
        ]
        return products[:limit]

    async def snapshot(self, product: ProductRef) -> ProductSnapshot:
        if product.external_id in self.fail_ids:
            raise RuntimeError("detail unavailable")

        round_index = self.round
        base = 10 if product.external_id == "a" else 20
        return ProductSnapshot(
            source=self.name,
            external_id=product.external_id,
            url=product.url,
            title=product.title,
            observed_at=datetime(2026, 9, 5, round_index, tzinfo=timezone.utc),
            published_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            price=300 - round_index * 10,
            sales_count=None,
            views_count=100 + round_index * 50 + base,
            wants_count=base + round_index * 5,
            raw={"round": round_index},
        )


def test_scan_twice_builds_real_velocity_from_persisted_snapshots(tmp_path):
    repository = SQLiteSnapshotRepository(str(tmp_path / "commerce.sqlite3"))
    source = SequencedSource()
    service = SourceScanService(source, OpportunityPipeline(repository), concurrency=2)

    first = asyncio.run(service.scan("portable monitor", limit=2))
    second = asyncio.run(service.scan("portable monitor", limit=2))

    assert first.discovered_count == 2
    assert first.captured_count == 2
    assert first.failed_count == 0
    assert first.items[0].trends == []

    item_a = next(item for item in second.items if item.product.external_id == "a")
    trends = {trend.metric: trend for trend in item_a.trends}

    assert trends["wants_count"].delta == 5
    assert trends["wants_count"].velocity_per_hour == 5
    assert trends["views_count"].delta == 50
    assert trends["views_count"].velocity_per_hour == 50
    assert trends["price"].delta == -10
    assert item_a.metrics["sales_count"] is None
    assert len(repository.list_for_product("goofish", "a")) == 2


def test_scan_isolates_one_product_failure(tmp_path):
    repository = SQLiteSnapshotRepository(str(tmp_path / "commerce.sqlite3"))
    source = SequencedSource(fail_ids={"b"})
    service = SourceScanService(source, OpportunityPipeline(repository), concurrency=2)

    result = asyncio.run(service.scan("keyboard", limit=2))

    assert result.discovered_count == 2
    assert result.captured_count == 1
    assert result.failed_count == 1
    assert result.failures[0].product.external_id == "b"
    assert result.failures[0].error_type == "RuntimeError"
    assert len(repository.list_for_product("goofish", "a")) == 1
    assert repository.list_for_product("goofish", "b") == []


def test_discovery_failure_stops_scan_with_explicit_error(tmp_path):
    repository = SQLiteSnapshotRepository(str(tmp_path / "commerce.sqlite3"))
    source = SequencedSource(fail_discovery=True)
    service = SourceScanService(source, OpportunityPipeline(repository))

    with pytest.raises(SourceDiscoveryError, match="goofish discovery failed"):
        asyncio.run(service.scan("camera"))
