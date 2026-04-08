import sys
from pathlib import Path

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
