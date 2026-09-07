from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from commerce.application.pipeline import OpportunityPipeline
from commerce.domain import ProductRef, ProductSnapshot, TrendSignal
from commerce.sources import ProductSourceAdapter


class SourceDiscoveryError(RuntimeError):
    """Raised when a source cannot complete the discovery stage."""


class ScanFailure(BaseModel):
    product: ProductRef
    error_type: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ScanItemResult(BaseModel):
    product: ProductRef
    observed_at: datetime
    published_at: datetime | None = None
    metrics: dict[str, float | None] = Field(default_factory=dict)
    trends: list[TrendSignal] = Field(default_factory=list)


class ScanRun(BaseModel):
    source: str = Field(min_length=1)
    query: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    discovered_count: int = Field(ge=0)
    captured_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    items: list[ScanItemResult] = Field(default_factory=list)
    failures: list[ScanFailure] = Field(default_factory=list)


class SourceScanService:
    """Discover products, capture snapshots, persist facts, and return trends.

    Discovery failures stop the run because there is no candidate set to work
    with. Individual product capture failures are isolated so one broken
    listing does not discard the rest of the scan.
    """

    def __init__(
        self,
        adapter: ProductSourceAdapter,
        pipeline: OpportunityPipeline,
        *,
        concurrency: int = 3,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        self.adapter = adapter
        self.pipeline = pipeline
        self.concurrency = concurrency

    async def scan(self, query: str, *, limit: int = 20) -> ScanRun:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if limit < 1:
            raise ValueError("limit must be at least 1")

        started_at = datetime.now(timezone.utc)
        try:
            products = await self.adapter.discover(normalized_query, limit=limit)
        except Exception as exc:
            raise SourceDiscoveryError(
                f"{self.adapter.name} discovery failed: {exc}"
            ) from exc

        semaphore = asyncio.Semaphore(self.concurrency)

        async def capture(product: ProductRef) -> ScanItemResult | ScanFailure:
            async with semaphore:
                try:
                    snapshot = await self.adapter.snapshot(product)
                    trends = self.pipeline.ingest(snapshot)
                    return ScanItemResult(
                        product=product,
                        observed_at=snapshot.observed_at,
                        published_at=snapshot.published_at,
                        metrics=_snapshot_metrics(snapshot),
                        trends=trends,
                    )
                except Exception as exc:
                    return ScanFailure(
                        product=product,
                        error_type=type(exc).__name__,
                        message=str(exc) or type(exc).__name__,
                    )

        outcomes = await asyncio.gather(*(capture(product) for product in products))
        items = [item for item in outcomes if isinstance(item, ScanItemResult)]
        failures = [item for item in outcomes if isinstance(item, ScanFailure)]
        completed_at = datetime.now(timezone.utc)

        return ScanRun(
            source=self.adapter.name,
            query=normalized_query,
            started_at=started_at,
            completed_at=completed_at,
            discovered_count=len(products),
            captured_count=len(items),
            failed_count=len(failures),
            items=items,
            failures=failures,
        )


def _snapshot_metrics(snapshot: ProductSnapshot) -> dict[str, float | None]:
    """Return only measurable facts, not the potentially large raw evidence."""

    return {
        "price": snapshot.price,
        "sales_count": snapshot.sales_count,
        "views_count": snapshot.views_count,
        "wants_count": snapshot.wants_count,
        "reviews_count": snapshot.reviews_count,
        "rating": snapshot.rating,
        "rank": snapshot.rank,
        "stock": snapshot.stock,
        "seller_count": snapshot.seller_count,
    }
