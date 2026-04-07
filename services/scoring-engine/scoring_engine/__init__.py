"""
scoring-engine
~~~~~~~~~~~~~~
Computes accuracy scores for resolved predictions.

Supported metrics:
  - Brier score (primary)
  - Calibration curves
  - Domain-level breakdowns

Called by the scheduler after each market resolution, and by the
badge-service when evaluating badge eligibility.
"""
