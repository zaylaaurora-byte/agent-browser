"""Pytest configuration — fix Python path so tests can import backend modules."""
import sys
from pathlib import Path

# Allow imports from backend/
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
