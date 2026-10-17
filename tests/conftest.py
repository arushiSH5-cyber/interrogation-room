"""Shared pytest setup: make `import src...` work from the repo root."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
