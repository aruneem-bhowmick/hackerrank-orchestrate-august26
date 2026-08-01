"""Adds the code/ directory to sys.path so tests can import the router package."""

import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
