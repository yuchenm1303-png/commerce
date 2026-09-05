import asyncio
from datetime import datetime, timezone

from commerce.domain import ProductRef
from commerce.sources.goofish import GoofishSourceAdapter


SEARCH_PAYLOAD = {
    "data": {
        "resultList": [
            {
                "data": {
                    "item": {
                        "main": {
                            "exContent": {
                                "itemId": "a",
                                "title": "A",
                                "price": [{"text": "¥10"}],
                            },
                            "clickParam": {"args": {"wantNum": "2"}},
                            "targetUrl": "https://www.goofish.com/item?id=a",
                        }
                    }
                }
            },
            {
                "data": {
                    "item": {
                        "main": {
                            "exContent": {
                                "itemId": "b",
                                "title": "B",
                                "price": [{"text": "¥20"}],
                            },
                            "clickParam": {"args": {"wantNum": "4"}},
                            "targetUrl": "https://www.goofish.com/item?id=b",
                        }
                    }
                }
            },
        ]
    }
}


class FakeTransport:
    def __init__(self):
        self.search_queries = []
        self.detail_ids = []

    async def search(self, query: str):
        self.search_queries.append(query)
        return SEARCH_PAYLOAD

    async def detail(self, product: ProductRef):
        self.detail_ids.append(product.external_id)
        return {
            "data": {
                "itemDO": {
                    "wantCnt": "9",
                    "browseCnt": "100",
                }
            }
        }


def test_adapter_discovers_and_snapshots_with_cached_search_evidence():
    transport = FakeTransport()
    fixed_now = datetime(2026, 9, 5, 7, tzinfo=timezone.utc)
    adapter = GoofishSourceAdapter(
        transport,
        clock=lambda: fixed_now,
    )

    async def run():
        products = await adapter.discover("monitor", limit=1)
        snapshot = await adapter.snapshot(products[0])
        return products, snapshot

    products, snapshot = asyncio.run(run())

    assert [item.external_id for item in products] == ["a"]
    assert transport.search_queries == ["monitor"]
    assert transport.detail_ids == ["a"]
    assert snapshot.observed_at == fixed_now
    assert snapshot.price == 10
    assert snapshot.wants_count == 9
    assert snapshot.views_count == 100


def test_adapter_rejects_product_from_other_source():
    adapter = GoofishSourceAdapter(FakeTransport())
    product = ProductRef(
        source="other",
        external_id="x",
        url="https://example.com/x",
    )

    async def run():
        await adapter.snapshot(product)

    try:
        asyncio.run(run())
    except ValueError as exc:
        assert "cannot snapshot source" in str(exc)
    else:
        raise AssertionError("expected ValueError")
