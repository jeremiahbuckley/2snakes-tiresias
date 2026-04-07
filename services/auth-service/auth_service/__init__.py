"""
auth-service
~~~~~~~~~~~~
Handles user identity, JWT session tokens, and linking of external
prediction market accounts (Kalshi, Polymarket, Manifold, Metaculus).

Each exchange uses a different proof-of-ownership mechanism:
  - Kalshi:     API key provided by the user
  - Polymarket: wallet signature (EIP-191)
  - Manifold:   API key provided by the user
  - Metaculus:  OAuth2 or API token
"""
