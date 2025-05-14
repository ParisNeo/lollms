# your_project_root/main.py (NEW thin launcher)
import sys
from pathlib import Path

# Add the project root to sys.path to allow "import backend"
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.main import run as run_backend

if __name__ == "__main__":
    run_backend()