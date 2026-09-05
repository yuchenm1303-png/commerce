from __future__ import annotations

from commerce.domain import SelectionAssessment


def validate_assessment_evidence(assessment: SelectionAssessment) -> list[str]:
    """Return audit warnings instead of silently accepting unsupported claims."""

    warnings: list[str] = []
    for item in assessment.evidence:
        if item.verdict in {"positive", "negative"} and not item.evidence:
            warnings.append(
                f"dimension '{item.dimension}' has verdict '{item.verdict}' without evidence"
            )
    if assessment.recommendation in {"accept", "reject"} and not assessment.evidence:
        warnings.append("final recommendation has no evidence chain")
    return warnings
