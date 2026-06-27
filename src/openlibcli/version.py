import sys
from pathlib import Path


def _get_version() -> str:
    if getattr(sys, "frozen", False):
        version_file = Path(sys.executable).resolve().parent / "version"
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()

    # Search in potential locations:
    # - parent.parent.parent (repo root: opencli-python/)
    # - parent.parent (src/)
    # - parent (src/openlibcli/)
    base_dir = Path(__file__).resolve().parent
    for candidate in [base_dir.parent.parent / "version", base_dir.parent / "version", base_dir / "version"]:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8").strip()

    return "0.1.0"


__version__ = _get_version()
