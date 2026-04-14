# scoring-engine

Computes Brier scores, calibration curves, and Brier Skill Scores (BSS) for resolved user predictions. Pure computation library — no HTTP endpoints.

## Tech Stack
- Python 3.12, NumPy, sqlalchemy (via data-layer)

## Key Files
```
scoring_engine/
  brier.py        # brier_score(prob, outcome) — single prediction; mean_brier_score(predictions) — aggregate
  calibration.py  # calibration_curve(predictions) — bins predictions by probability, computes accuracy per bin
  engine.py       # score_predictions(user_id, db) — loads unscored resolved predictions, scores, upserts UserScore
```

## Entry Point
```python
from scoring_engine.engine import score_predictions
await score_predictions(user_id=uuid, db=async_session)
```

## Score Formulas
- **Brier Score**: `(probability - outcome)²` — lower is better, 0.0 = perfect
- **BSS (Brier Skill Score)**: `1 - (user_brier / climatology_brier)` — positive = better than baseline
- **Calibration**: Bins predictions by stated probability; compares to actual resolution rate

## Output
Upserts a `UserScore` row with `{brier_score, calibration, bss, badge_ids}` keyed on `user_id`.

## Dependencies
- Imports from `data-layer`: `data.crud.prediction.get_unscored`, `data.crud.score.upsert_user_score`
- Called by `services/scheduler` job `detect_and_score_resolutions` (not run standalone)

## Notes
- Only scores predictions where the market has a non-null `resolved_outcome`
- Skips users with fewer than N predictions to avoid noisy scores (threshold in engine.py)
- Badge IDs field preserved on upsert — scoring engine does not modify badge state
