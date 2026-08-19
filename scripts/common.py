"""Small shared helpers for loading/saving fonts consistently across the pipeline."""

from __future__ import annotations

import re
from pathlib import Path

from fontTools.ttLib import TTFont

REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = REPO_ROOT / "dist"
UPSTREAM_DIR = DIST_DIR / "upstream"
FONTS_DIR = DIST_DIR / "fonts"


def read_project_version() -> str:
    """Read `version = "X.Y.Z"` from pyproject.toml.

    A plain regex, not tomllib -- this project's pyproject.toml declares
    requires-python >=3.10, and tomllib is 3.11+; not worth a dependency
    (or narrowing the supported Python range) just for a one-line read.
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    if not match:
        raise ValueError("pyproject.toml has no top-level version = \"...\" line")
    return match.group(1)


def load_font(path: Path) -> TTFont:
    return TTFont(str(path))


def save_font_atomic(font: TTFont, target_path: Path) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = target_path.with_name(f".{target_path.name}.tmp")
    temporary.unlink(missing_ok=True)
    try:
        font.save(str(temporary))
        temporary.replace(target_path)
    finally:
        temporary.unlink(missing_ok=True)
    return target_path
