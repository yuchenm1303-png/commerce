from datetime import datetime, timezone

from fastapi.testclient import TestClient

from commerce.api.app import create_app
from commerce.domain import ProductRef, ProductSnapshot


class ApiFakeSource:
    name = "goofish"

    def __init__(self):
        self.round = 0

    async def discover(self, query: str, *, limit: int = 100) -> list[ProductRef]:
        self.round += 1
        return [
            ProductRef(
                source=self.name,
                external_id="item-1",
                url="https://www.goofish.com/item?id=item-1",
                title=query,
            )
        ][:limit]

    async def snapshot(self, product: ProductRef) -> ProductSnapshot:
        return ProductSnapshot(
            source=self.name,
            external_id=product.external_id,
            url=product.url,
            title=product.title,
            observed_at=datetime(2026, 9, 5, self.round, tzinfo=timezone.utc),
            wants_count=10 + self.round * 4,
            views_count=100 + self.round * 40,
            price=199,
        )


def test_scan_endpoint_uses_configured_source_and_returns_trends(tmp_path):
    source = ApiFakeSource()
    app = create_app(
        database_path=str(tmp_path / "commerce.sqlite3"),
        sources={"goofish": source},
    )

    with TestClient(app) as client:
        assert client.get("/v1/sources").json() == {"sources": ["goofish"]}

        first = client.post(
            "/v1/scans/goofish",
            json={"query": "portable monitor", "limit": 1, "concurrency": 1},
        )
        second = client.post(
            "/v1/scans/goofish",
            json={"query": "portable monitor", "limit": 1, "concurrency": 1},
        )

    assert first.status_code == 200
    assert first.json()["captured_count"] == 1
    assert second.status_code == 200

    trends = {trend["metric"]: trend for trend in second.json()["items"][0]["trends"]}
    assert trends["wants_count"]["delta"] == 4.0
    assert trends["views_count"]["velocity_per_hour"] == 40.0


def test_scan_endpoint_rejects_unconfigured_source(tmp_path):
    app = create_app(database_path=str(tmp_path / "commerce.sqlite3"), sources={})

    with TestClient(app) as client:
        response = client.post(
            "/v1/scans/xiaohongshu",
            json={"query": "template"},
        )

    assert response.status_code == 404
