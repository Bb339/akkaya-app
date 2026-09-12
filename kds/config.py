"""Runtime data never defaults to the legacy public static directory."""
import os
from pathlib import Path

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ROWS = 20000
MAX_COLUMNS = 100
MAX_EXPANDED_XLSX_BYTES = 50 * 1024 * 1024


def project_store_path() -> Path:
    override = os.environ.get("KDS_PROJECT_STORE")
    if override:
        return Path(override).expanduser().resolve()
    root = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / "CropKDS" / "projects"
