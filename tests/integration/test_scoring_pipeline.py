"""
Integration test: full scoring pipeline.

Verifies that predictions written to the data layer are correctly scored
by the scoring engine and that badges are issued appropriately.

TODO: implement once data layer + scoring engine are wired together.
"""

import pytest


@pytest.mark.skip(reason="Not yet implemented — wire up DB fixtures first")
async def test_score_resolved_prediction():
    """
    Given a resolved prediction in the DB,
    when the scoring job runs,
    then a UserScore record is created with the correct Brier score.
    """
    pass


@pytest.mark.skip(reason="Not yet implemented")
async def test_badge_issued_after_scoring():
    """
    Given a user with 10+ resolved predictions and a positive BSS,
    when scoring and badge evaluation run,
    then the user holds the 'above-baseline' badge.
    """
    pass
