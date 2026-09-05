from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, status

from commerce.application import OpportunityPipeline
from commerce.domain import ProductSnapshot, TrendSignal
from commerce.infrastructure import SQLiteSnapshotRepository


def create_app(*, database_path: str | None = None) -> FastAPI:
    repository = SQLiteSnapshotRepository(
        database_path or os.getenv("COMMERCE_DB_PATH", "data/commerce.sqlite3")
    )
    pipeline = OpportunityPipeline(repository)
    api = FastAPI(
        title="Commerce Intelligence API",
        version="0.1.0",
        description="Evidence-driven product opportunity intelligence core.",
    )

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post(
        "/v1/snapshots",
        response_model=list[TrendSignal],
        status_code=status.HTTP_201_CREATED,
    )
    def ingest_snapshot(snapshot: ProductSnapshot) -> list[TrendSignal]:
        return pipeline.ingest(snapshot)

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
