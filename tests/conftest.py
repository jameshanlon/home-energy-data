import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "aed", Path(__file__).parent.parent / "analyse-energy-data.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
sys.modules["aed"] = mod
