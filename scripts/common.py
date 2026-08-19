"""Small shared helpers for loading/saving fonts consistently across the pipeline."""

from __future__ import annotations

from pathlib import Path

from fontTools.ttLib import TTFont

REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = REPO_ROOT / "dist"
UPSTREAM_DIR = DIST_DIR / "upstream"
FONTS_DIR = DIST_DIR / "fonts"


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
