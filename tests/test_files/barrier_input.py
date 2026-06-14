"""Definitions never cross a side-effecting statement that may depend on them."""

import sys
from pathlib import Path

ZEBRA = 1
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

BANANA = 3
APPLE = 2
