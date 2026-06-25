"""Groq call + JSON validation for AI recommendations.

The flow is:
    UI clicks "Generate"
        → generate_recommendations(max_suggestions)
            → prompt_builder.build_user_context()
            → Groq ChatCompletion (json_object response_format)
            → Pydantic validation
            → recommendations.save_recommendation(...) per item
        → returns the list of saved rec dicts (with their new ids)

Any failure (missing key, network error, malformed JSON, schema violation)
raises `AIEngineError` with a user-friendly message. We never persist
unvalidated data.
"""
from __future__ import annotations

import json
import os
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from config import GROQ_MODEL
from services.prompt_builder import build_messages, build_user_context
from services.recommendations import get_recommendation, save_recommendation


class AIEngineError(Exception):
    """Raised when a recommendation generation cannot be completed."""


class _RecOut(BaseModel):
    """Schema for one recommendation item returned by the LLM."""
    ticker: str = Field(min_length=1, max_length=8)
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: int = Field(ge=1, le=5)
    reasoning: str = Field(min_length=1, max_length=600)
    risk_note: str = Field(min_length=1, max_length=400)

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, v: str) -> str:
        return v.upper().strip()


class _RecBatch(BaseModel):
    recommendations: list[_RecOut]


def generate_recommendations(max_suggestions: int = 3) -> list[dict]:
    """Generate fresh recommendations, persist them, return the saved rows.

    Raises AIEngineError on any failure. Caller (UI) catches and shows
    a friendly message.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise AIEngineError(
            "GROQ_API_KEY is not set. Add it to your .env file."
        )

    try:
        from groq import Groq
    except ImportError as e:
        raise AIEngineError("The 'groq' package is not installed.") from e

    context = build_user_context(max_suggestions=max_suggestions)
    messages = build_messages(context, max_suggestions=max_suggestions)

    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.4,
        )
    except Exception as e:
        raise AIEngineError(f"Groq request failed: {e}") from e

    raw = (completion.choices[0].message.content or "").strip()
    if not raw:
        raise AIEngineError("AI returned an empty response.")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AIEngineError(f"AI returned invalid JSON: {e}") from e

    try:
        batch = _RecBatch.model_validate(parsed)
    except ValidationError as e:
        raise AIEngineError(f"AI response failed schema validation: {e}") from e

    if not batch.recommendations:
        raise AIEngineError("AI returned no recommendations.")

    saved: list[dict] = []
    for rec in batch.recommendations[: int(max_suggestions)]:
        rec_id = save_recommendation(
            ticker=rec.ticker,
            action=rec.action,
            confidence=rec.confidence,
            reasoning=rec.reasoning,
            risk_note=rec.risk_note,
            context=context,
        )
        stored = get_recommendation(rec_id)
        if stored:
            saved.append(stored)
    return saved
