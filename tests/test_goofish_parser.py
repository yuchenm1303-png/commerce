from datetime import datetime, timezone

from commerce.domain import ProductRef
from commerce.sources.goofish import parse_detail_response, parse_search_response


SEARCH_PAYLOAD = {
    "data": {
        "resultList": [
            {
                "data": {
                    "item": {
                        "main": {
                            "exContent": {
                                "itemId": "item-1",
                                "title": "Portable monitor",
                                "price": [
                                    {"text": "当前价"},
                                    {"text": "¥"},
                                    {"text": "399.5"},
                                ],
                                "userNickName": "seller",
                                "area": "上海",
                                "picUrl": "https://img.example/item-1.jpg",
                                "oriPrice": "499",
                            },
                            "clickParam": {
                                "args": {
                                    "publishTime": "1788588000000",
                                    "wantNum": "1.2万",
                                }
                            },
                            "targetUrl": "fleamarket://item?id=item-1",
                        }
                    }
                }
            }
        ]
    }
}


def test_parse_search_response_maps_measurable_facts_without_inventing_sales():
    items = parse_search_response(SEARCH_PAYLOAD)

    assert len(items) == 1
    item = items[0]
    assert item.product.source == "goofish"
    assert item.product.external_id == "item-1"
    assert item.product.url == "https://www.goofish.com/item?id=item-1"
    assert item.price == 399.5
    assert item.wants_count == 12000
    assert item.published_at == datetime.fromtimestamp(
        1788588000,
        tz=timezone.utc,
    )


def test_parse_detail_response_merges_detail_with_search_seed():
    seed = parse_search_response(SEARCH_PAYLOAD)[0]
    detail_payload = {
        "data": {
            "itemDO": {
                "title": "Portable monitor 15.6 inch",
                "wantCnt": "123",
                "browseCnt": "4567",
                "imageInfos": [
                    {"url": "https://img.example/1.jpg"},
                    {"url": "https://img.example/2.jpg"},
                ],
            },
            "sellerDO": {
                "sellerId": "seller-9",
                "userNick": "alice",
                "userRegDay": 930,
                "zhimaLevelInfo": {"levelName": "信用极好"},
            },
        }
    }
    observed_at = datetime(2026, 9, 5, 6, 30, tzinfo=timezone.utc)

    snapshot = parse_detail_response(
        detail_payload,
        product=seed.product,
        seed=seed,
        observed_at=observed_at,
    )

    assert snapshot.observed_at == observed_at
    assert snapshot.title == "Portable monitor 15.6 inch"
    assert snapshot.price == 399.5
    assert snapshot.wants_count == 123
    assert snapshot.views_count == 4567
    assert snapshot.sales_count is None
    assert snapshot.published_at == seed.published_at
    assert snapshot.raw["seller"]["id"] == "seller-9"
    assert snapshot.raw["image_urls"] == [
        "https://img.example/1.jpg",
        "https://img.example/2.jpg",
    ]


def test_parse_detail_response_does_not_relabel_missing_metrics():
    product = ProductRef(
        source="goofish",
        external_id="x",
        url="https://www.goofish.com/item?id=x",
    )

    snapshot = parse_detail_response(
        {"data": {"itemDO": {"browseCnt": "88"}}},
        product=product,
        observed_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
    )

    assert snapshot.views_count == 88
    assert snapshot.wants_count is None
    assert snapshot.sales_count is None
    assert snapshot.reviews_count is None
