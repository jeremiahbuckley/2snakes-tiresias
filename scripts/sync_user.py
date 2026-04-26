"""
Force a one-off prediction sync for a single user.

Runs the same sync_user_predictions job the scheduler triggers every 15 min,
immediately, without waiting for the next scheduled firing.

Requires:
  - DATABASE_URL set in your environment (start the stack first)
  - CREDENTIAL_ENCRYPTION_KEY set in your environment

Usage:
  python scripts/sync_user.py <user-uuid>

Find your user UUID:
  psql $DATABASE_URL -c "SELECT id, email FROM users;"

Or source your .env first if the vars are there:
  set -a && source .env && set +a
  python scripts/sync_user.py <user-uuid>
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from uuid import UUID

# Add all service packages to sys.path (mirrors conftest.py)
_root = Path(__file__).parent.parent
for _service in sorted(_root.glob("services/*/")):
    sys.path.insert(0, str(_service))


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if sys.argv[1:] in (["-h"], ["--help"]) else 1)

    user_id = sys.argv[1]

    try:
        UUID(user_id)
    except ValueError:
        print(f"Error: {user_id!r} is not a valid UUID.")
        sys.exit(1)

    if not os.environ.get("DATABASE_URL"):
        print("Error: DATABASE_URL is not set.")
        print("Start the stack first, then: set -a && source .env && set +a")
        sys.exit(1)

    if not os.environ.get("CREDENTIAL_ENCRYPTION_KEY"):
        print("Error: CREDENTIAL_ENCRYPTION_KEY is not set.")
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from scheduler.jobs import sync_user_predictions

    print(f"Syncing predictions for user {user_id} ...")
    asyncio.run(sync_user_predictions(user_id))
    print("Done.")


if __name__ == "__main__":
    main()
