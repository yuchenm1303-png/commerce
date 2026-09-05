from __future__ import annotations

from typing import Protocol

from commerce.domain import OpportunityContext, SelectionAssessment


class SemanticEvaluator(Protocol):
    """AI/business reasoning boundary.

    Implementations may call an LLM, but they must return structured evidence.
    Deterministic trend calculations stay outside this interface.
    """

    async def evaluate(self, context: OpportunityContext) -> SelectionAssessment: ...
