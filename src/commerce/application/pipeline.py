from __future__ import annotations

from commerce.domain import OpportunityContext, ProductRef, ProductSnapshot, SelectionAssessment
from commerce.intelligence import SemanticEvaluator, validate_assessment_evidence
from commerce.repositories import SnapshotRepository
from commerce.trend import TrendEngine


class OpportunityPipeline:
    """Coordinates memory, deterministic signals and optional AI evaluation."""

    def __init__(
        self,
        repository: SnapshotRepository,
        *,
        trend_engine: TrendEngine | None = None,
        evaluator: SemanticEvaluator | None = None,
    ) -> None:
        self.repository = repository
        self.trend_engine = trend_engine or TrendEngine()
        self.evaluator = evaluator

    def ingest(self, snapshot: ProductSnapshot):
        self.repository.save(snapshot)
        history = self.repository.list_for_product(snapshot.source, snapshot.external_id)
        return self.trend_engine.analyze(history)

    def context(self, source: str, external_id: str) -> OpportunityContext:
        snapshots = self.repository.list_for_product(source, external_id)
        if not snapshots:
            raise LookupError(f"no snapshots for {source}:{external_id}")
        latest = snapshots[-1]
        product = ProductRef(
            source=source,
            external_id=external_id,
            url=latest.url or f"{source}:{external_id}",
            title=latest.title,
        )
        return OpportunityContext(
            product=product,
            snapshots=snapshots,
            trends=self.trend_engine.analyze(snapshots),
            deterministic_facts={"observation_count": len(snapshots)},
        )

    async def evaluate(self, source: str, external_id: str) -> SelectionAssessment:
        if self.evaluator is None:
            raise RuntimeError("semantic evaluator is not configured")
        assessment = await self.evaluator.evaluate(self.context(source, external_id))
        warnings = validate_assessment_evidence(assessment)
        if warnings:
            raise ValueError("; ".join(warnings))
        return assessment
