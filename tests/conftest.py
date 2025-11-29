import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_SRC = REPO_ROOT / "api" / "src"
PIPELINES_SRC = REPO_ROOT / "pipelines" / "src"

for path in (API_SRC, PIPELINES_SRC):
    if str(path) not in sys.path:
        sys.path.append(str(path))
