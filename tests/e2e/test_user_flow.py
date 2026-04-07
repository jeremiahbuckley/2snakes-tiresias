"""
E2E test: core user flow.

Covers: register → link account → view profile → check badges.

TODO: implement once the gateway and auth service are running.
"""

import pytest


@pytest.mark.skip(reason="Not yet implemented — requires full stack")
def test_register_and_login(api_client):
    """A new user can register and receive a valid JWT."""
    pass


@pytest.mark.skip(reason="Not yet implemented")
def test_link_kalshi_account(api_client):
    """An authenticated user can link their Kalshi account."""
    pass


@pytest.mark.skip(reason="Not yet implemented")
def test_public_profile_visible(api_client):
    """A user's public profile is accessible without auth."""
    pass


@pytest.mark.skip(reason="Not yet implemented")
def test_leaderboard_returns_ranked_users(api_client):
    """The leaderboard endpoint returns users ranked by Brier Skill Score."""
    pass
