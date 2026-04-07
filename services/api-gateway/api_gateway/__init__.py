"""
api-gateway
~~~~~~~~~~~
Single FastAPI application that mounts all service routers under one
unified API surface. All frontend apps (dashboard, leaderboard, public
profile) talk to this gateway rather than individual services.

Routes:
  /auth/*        → auth-service
  /badges/*      → badge-service
  /users/*       → user endpoints (dashboard data, profile)
  /leaderboard/* → leaderboard endpoints
  /markets/*     → market data endpoints
"""
