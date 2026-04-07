"""
scheduler
~~~~~~~~~
Periodic job runner. Drives all background sync and scoring work:

  - Sync markets from each connector (every 15 min)
  - Detect newly resolved markets and trigger scoring (every 5 min)
  - Re-evaluate badges after scoring (on-demand, triggered by scoring)
  - Rebuild leaderboard snapshot (every hour)

Uses APScheduler for job management.
"""
