import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _load(name: str, filename: str):
    """
    Import a top-level script whose filename is not a valid module name.
    """
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


aed = _load("aed", "analyse-energy-data.py")
renovation = _load("renovation", "renovation-charts.py")
