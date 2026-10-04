from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Claim(StrictModel):
    claim_id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=4000)
    supporting_chunk_ids: list[int] = Field(min_length=1, max_length=10)


class Answer(StrictModel):
    answerable: bool
    claims: list[Claim] = Field(max_length=20)
    reason: str = Field(max_length=2000)

    @model_validator(mode='after')
    def coherent(self):
        if self.answerable != bool(self.claims):
            raise ValueError('Answerable answers need claims; refusals must not contain claims.')
        if len({c.claim_id for c in self.claims}) != len(self.claims):
            raise ValueError('Claim IDs must be unique.')
        return self


class ClaimSupport(StrictModel):
    claim_id: str
    status: Literal['supported', 'partial', 'unsupported', 'contradicted']
    explanation: str = Field(max_length=1500)
    supporting_chunk_ids: list[int]


class SupportJudgment(StrictModel):
    claims: list[ClaimSupport]


class CorrectnessJudgment(StrictModel):
    label: Literal['correct', 'partial', 'wrong']
    explanation: str = Field(min_length=1, max_length=2000)


class ExtractedObligation(StrictModel):
    obligation_text: str = Field(min_length=1, max_length=4000)
    obligated_party: str = Field(max_length=300)
    condition: str = Field(max_length=2000)
    deadline_or_trigger: str = Field(max_length=2000)
    source_quote: str = Field(min_length=1, max_length=4000)
    confidence: Literal['high', 'medium', 'low']


class Extraction(StrictModel):
    obligations: list[ExtractedObligation] = Field(max_length=12)


class GapJudgment(StrictModel):
    status: Literal['addressed', 'partially_addressed', 'not_addressed', 'conflicting', 'needs_review']
    policy_chunk_id: int | None
    explanation: str = Field(min_length=1, max_length=3000)
    confidence: Literal['high', 'medium', 'low']
