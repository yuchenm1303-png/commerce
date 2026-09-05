# Goofish source adapter

The Goofish adapter is the first platform-specific discovery source for Commerce.

## Design

The adapter deliberately separates two responsibilities:

1. `PlaywrightGoofishTransport` opens an authenticated Goofish web session and captures the JSON responses emitted by the site itself.
2. Pure parsing functions convert those responses into `ProductRef` and `ProductSnapshot` domain objects.

The current network markers are:

- search: `mtop.taobao.idlemtopsearch.pc.search`
- detail: `mtop.taobao.idle.pc.detail`

These are observed web-interface details, not a stable official API contract. If Goofish changes them, only the source adapter should need to change.

## Metrics

Current snapshots can contain:

- `price`
- `wants_count`
- `views_count`
- `published_at`
- seller/image context in `raw`

The adapter intentionally leaves `sales_count`, `reviews_count`, and other unsupported facts as `None`. A proxy is never relabeled as real sales.

## Setup

Install the optional browser dependency:

```bash
pip install -e ".[dev,goofish]"
playwright install chromium
```

Export a valid Playwright storage-state JSON from an authenticated Goofish session and configure:

```bash
export GOOFISH_STATE_FILE=state/goofish.json
```

The file is local runtime state and must not be committed.

## Minimal usage

```python
from commerce.sources import GoofishSourceAdapter

adapter = GoofishSourceAdapter()
products = await adapter.discover("显示器", limit=20)
snapshot = await adapter.snapshot(products[0])
```

`discover()` currently captures the first search response and applies `limit` to that result set. Pagination, long-running scheduling, seller-profile enrichment, and account rotation belong to later source-infrastructure work rather than the domain core.

## Operational behavior

The transport fails closed when it cannot capture the expected JSON or when the browser is redirected to a Goofish login flow. It does not try to bypass verification challenges. Authentication, request frequency, and platform rules remain deployment concerns.
