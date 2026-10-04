"""Just the settings fetch_monitors.py needs (the full wa-smoke config lives on the PC)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEST, EAST = -125.0, -116.6
SOUTH, NORTH = 45.45, 49.02
START = "2026-07-25"
END = "2026-09-10"
