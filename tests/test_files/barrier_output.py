"""Definitions never cross a side-effecting statement that may depend on them."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ZEBRA = 1
sys.path.insert(0, str(REPO_ROOT))

APPLE = 2
BANANA = 3
