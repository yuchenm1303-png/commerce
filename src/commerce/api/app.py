from __future__ import annotations

import os
from collections.abc import Mapping

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from commerce.application import (
    OpportunityPipeline,
    ScanRun,
    SourceDiscoveryError,
    SourceScanService,
)
from commerce.domain import ProductSnapshot, TrendSignal
from commerce.infrastructure import SQLiteSnapshotRepository
from commerce.sources import GoofishSourceAdapter, ProductSourceAdapter


class ScanRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=20, ge=1, le=100)
    concurrency: int = Field(default=3, ge=1, le=10)


def _default_sources() -> dict[str, ProductSourceAdapter]:
    sources: dict[str, ProductSourceAdapter] = {}
    state_file = os.getenv("GOOFISH_STATE_FILE")
    if state_file:
        sources["goofish"] = GoofishSourceAdapter(state_file=state_file)
    return sources


def create_app(
    *,
    database_path: str | None = None,
    sources: Mapping[str, ProductSourceAdapter] | None = None,
) -> FastAPI:
    repository = SQLiteSnapshotRepository(
        database_path or os.getenv("COMMERCE_DB_PATH", "data/commerce.sqlite3")
    )
    pipeline = OpportunityPipeline(repository)
    source_registry = dict(sources) if sources is not None else _default_sources()

    api = FastAPI(
        title="Commerce Intelligence API",
        version="0.2.0",
        description="Evidence-driven product opportunity intelligence core.",
    )

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/v1/sources")
    def list_sources() -> dict[str, list[str]]:
        return {"sources": sorted(source_registry)}

    @api.post(
        "/v1/snapshots",
        response_model=list[TrendSignal],
        status_code=status.HTTP_201_CREATED,
    )
    def ingest_snapshot(snapshot: ProductSnapshot) -> list[TrendSignal]:
        return pipeline.ingest(snapshot)

    @api.post("/v1/scans/{source}", response_model=ScanRun)
    async def scan_source(source: str, request: ScanRequest) -> ScanRun:
        adapter = source_registry.get(source)
        if adapter is None:
            raise HTTPException(
                status_code=404,
                detail=f"source {source!r} is not configured",
            )

        service = SourceScanService(
            adapter,
            pipeline,
            concurrency=request.concurrency,
        )
        try:
            return await service.scan(request.query, limit=request.limit)
        except SourceDiscoveryError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.get(
        "/v1/products/{source}/{external_id}/trends",
        response_model=list[TrendSignal],
    )
    def get_trends(source: str, external_id: str) -> list[TrendSignal]:
        try:
            return pipeline.context(source, external_id).trends
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return api


app = create_app()
