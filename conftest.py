import enum
import sys
from pathlib import Path

# Test-only polyfill: the codebase targets Python 3.12 (StrEnum is stdlib
# there), but CI and some developer environments may still run 3.10. Inject
# a minimal StrEnum so that `from enum import StrEnum` resolves during test
# collection. This is a no-op on 3.11+.
if not hasattr(enum, "StrEnum"):

    class StrEnum(str, enum.Enum):  # type: ignore[no-redef]
        def __str__(self) -> str:
            return self.value

    enum.StrEnum = StrEnum  # type: ignore[attr-defined]

root = Path(__file__).parent

sys.path.insert(0, str(root / "services/api-gateway"))
sys.path.insert(0, str(root / "services/auth-service"))
sys.path.insert(0, str(root / "services/badge-service"))
sys.path.insert(0, str(root / "services/connector-kalshi"))
sys.path.insert(0, str(root / "services/connector-manifold"))
sys.path.insert(0, str(root / "services/connector-metaculus"))
sys.path.insert(0, str(root / "services/connector-polymarket"))
sys.path.insert(0, str(root / "services/data-layer"))
sys.path.insert(0, str(root / "services/notification-service"))
sys.path.insert(0, str(root / "services/scheduler"))
sys.path.insert(0, str(root / "services/scoring-engine"))
sys.path.insert(0, str(root / "apps/public-leaderboard"))
sys.path.insert(0, str(root / "apps/public-profile"))
sys.path.insert(0, str(root / "apps/user-dashboard"))
