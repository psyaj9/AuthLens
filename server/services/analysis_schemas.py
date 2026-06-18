from typing import Literal

from pydantic import BaseModel, Field, model_validator


class StructuredCriterion(BaseModel):
    criterion_code: str = Field(min_length=1, max_length=32)
    criterion_type: str = Field(min_length=1, max_length=64)
    requirement: str = Field(min_length=1)
    required_evidence: list[str] = Field(default_factory=list)
    is_required: bool = True
    source_quote: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    source_page: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    ambiguity_notes: list[str] = Field(default_factory=list)


class CriteriaExtractionOutput(BaseModel):
    criteria: list[StructuredCriterion] = Field(default_factory=list)
    missing_or_ambiguous_policy_info: list[str] = Field(default_factory=list)


class StructuredEvidenceMatch(BaseModel):
    criterion_code: str = Field(min_length=1, max_length=32)
    status: Literal["met", "unclear", "not_found", "not_met"]
    evidence_summary: str = Field(min_length=1)
    source_quote: str = ""
    source_file: str = ""
    source_page: str = ""
    why_it_matters: str = Field(min_length=1)
    missing_evidence: list[str] = Field(default_factory=list)
    conflicting_evidence: list[str] = Field(default_factory=list)
    recommended_action: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def met_requires_source_citation(self):
        if self.status == "met" and not all(
            value.strip() for value in [self.source_quote, self.source_file, self.source_page, self.why_it_matters]
        ):
            raise ValueError("met evidence requires source quote, file, page, and rationale")
        return self


class EvidenceMatchingOutput(BaseModel):
    matches: list[StructuredEvidenceMatch] = Field(default_factory=list)


class ReadinessOutput(BaseModel):
    readiness_score: float = Field(ge=0, le=100)
    overall_status: Literal["ready_for_review", "needs_more_documentation"]
    summary: str = Field(min_length=1)
    highest_risk_items: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
