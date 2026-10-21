"""Skema Pydantic untuk output terstruktur LLM."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ClauseSentimentItem(BaseModel):
    id: int = Field(description="Indeks 1-based klausa dalam batch")
    relevan: bool = False
    sentimen: Literal['positif', 'negatif', 'netral'] = 'netral'


class ClauseSentimentBatch(BaseModel):
    items: List[ClauseSentimentItem] = Field(default_factory=list)

    @classmethod
    def json_schema_for_llm(cls) -> dict:
        return {
            'type': 'json_schema',
            'json_schema': {
                'name': 'clause_sentiment_batch',
                'strict': True,
                'schema': {
                    'type': 'object',
                    'properties': {
                        'items': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'id': {'type': 'integer'},
                                    'relevan': {'type': 'boolean'},
                                    'sentimen': {
                                        'type': 'string',
                                        'enum': ['positif', 'negatif', 'netral'],
                                    },
                                },
                                'required': ['id', 'relevan', 'sentimen'],
                                'additionalProperties': False,
                            },
                        },
                    },
                    'required': ['items'],
                    'additionalProperties': False,
                },
            },
        }


class RerankFitItem(BaseModel):
    place_id: str
    fit_score: float = 0.0
    reason: Optional[str] = None


class RerankFitList(BaseModel):
    fits: List[RerankFitItem] = Field(default_factory=list)


def parse_json_with_pydantic(model_cls, raw: str, *, repair_fn=None):
    """Validasi JSON via Pydantic; fallback repair_fn lalu validate lagi."""
    text = (raw or '').strip()
    if not text:
        return None
    try:
        return model_cls.model_validate_json(text)
    except Exception:
        pass
    if repair_fn:
        try:
            repaired = repair_fn(text)
            if isinstance(repaired, str):
                return model_cls.model_validate_json(repaired)
            return model_cls.model_validate(repaired)
        except Exception:
            return None
    return None
