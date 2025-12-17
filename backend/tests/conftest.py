import sys
from pathlib import Path

# Resolve: backend/tests -> backend
BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Ensure `app` package is importable in tests
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
