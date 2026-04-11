"""
Metaculus sync entrypoint.

V1 scope:
  - Pull a user's predictions.
  - Pull question metadata on-demand for each unique question in those predictions.

Questions (markets) are stored separately from predictions; the link is market_external_id.
Resolution outcome (if any) is embedded in the question record itself.
"""

from __future__ import annotations

from .adapter import normalise_market, normalise_prediction
from .client import MetaculusClient


async def sync_user_predictions(user_id: str, metaculus_user_id: int) -> list[dict]:
    """Fetch a user's Metaculus prediction history and return normalised predictions."""
    client = MetaculusClient()
    raw = await client.get_user_predictions(metaculus_user_id)
    return [normalise_prediction(p, user_id) for p in raw]


async def sync_market(question_id: int) -> dict:
    """
    Fetch metadata for a single question by ID.

    Called after sync_user_predictions to hydrate the unique questions
    referenced by those predictions. Only fetches questions the user has
    actually predicted on. Resolution outcome (if any) is included.
    """
    client = MetaculusClient()
    raw = await client.get_question(question_id)
    return normalise_market(raw)
