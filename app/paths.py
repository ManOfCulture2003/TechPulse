"""Default private workspace belongs to the current operating-system user."""
import os
from pathlib import Path


def data_directory():
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    target = root / "TechPulse"
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        target.chmod(0o700)
    return target
