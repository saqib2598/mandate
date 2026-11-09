"""Repository paths."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "ituaireadiness"
KB = ROOT / "kb"
MANDATES = ROOT / "mandates"
SCENARIOS = ROOT / "scenarios"
RUNS = ROOT / "runs"
EVAL = ROOT / "eval"
