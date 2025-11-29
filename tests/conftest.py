import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINES_SRC = REPO_ROOT / "pipelines" / "src"

if str(PIPELINES_SRC) not in sys.path:
    sys.path.append(str(PIPELINES_SRC))
