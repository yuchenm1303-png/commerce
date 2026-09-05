from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ProductRef(BaseModel):
    """Stable identity of a product/listing on one source platform."""

    source: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    title: str | None = None


class ProductSnapshot(BaseModel):
    """Append-only observation of measurable facts at one point in time.

    Numeric facts are intentionally separate from AI interpretation. A source
    adapter may leave unsupported metrics as ``None``; proxies must not be
    mislabeled as real sales.
    """

    source: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    observed_at: datetime
    url: str | None = None
    title: str | None = None

    price: float | None = None
    sales_count: float | None = None
    views_count: float | None = None
    wants_count: float | None = None
    reviews_count: float | None = None
    rating: float | None = None
    rank: float | None = None
    stock: float | None = None
    seller_count: float | None = None
    published_at: datetime | None = None

    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("observed_at", "published_at", mode="after")
    @classmethod
    def normalize_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def metric(self, name: str) -> float | None:
        value = getattr(self, name, None)
        if value is None:
            return None
        return float(value)


TrendDirection = Literal["rising", "falling", "flat"]
QualityDirection = Literal["improving", "deteriorating", "flat", "unknown"]


class TrendSignal(BaseModel):
    metric: str
    observations: int
    first_observed_at: datetime
    last_observed_at: datetime
    window_hours: float
    start_value: float
    end_value: float
    delta: float
    velocity_per_hour: float
    acceleration_per_hour2: float | None = None
    direction: TrendDirection
    quality_direction: QualityDirection = "unknown"


EvidenceVerdict = Literal["positive", "neutral", "negative", "unknown"]


class EvidenceItem(BaseModel):
    """One auditable semantic conclusion produced by an evaluator."""

    dimension: str = Field(min_length=1)
    verdict: EvidenceVerdict
    claim: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


SelectionRecommendation = Literal["accept", "watch", "reject", "needs_review"]


class SelectionAssessment(BaseModel):
    recommendation: SelectionRecommendation
    summary: str = Field(min_length=1)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class OpportunityContext(BaseModel):
    product: ProductRef
    snapshots: list[ProductSnapshot]
    trends: list[TrendSignal]
    deterministic_facts: dict[str, Any] = Field(default_factory=dict)
