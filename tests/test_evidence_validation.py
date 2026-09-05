from commerce.domain import EvidenceItem, SelectionAssessment
from commerce.intelligence import validate_assessment_evidence


def test_hard_recommendation_requires_evidence_chain():
    assessment = SelectionAssessment(
        recommendation="accept",
        summary="Looks promising",
        confidence=0.8,
    )
    assert validate_assessment_evidence(assessment) == [
        "final recommendation has no evidence chain"
    ]


def test_positive_claim_without_evidence_is_flagged():
    assessment = SelectionAssessment(
        recommendation="watch",
        summary="Need more data",
        confidence=0.6,
        evidence=[
            EvidenceItem(
                dimension="demand",
                verdict="positive",
                claim="Demand is accelerating",
                evidence=[],
                confidence=0.9,
            )
        ],
    )
    assert "without evidence" in validate_assessment_evidence(assessment)[0]
