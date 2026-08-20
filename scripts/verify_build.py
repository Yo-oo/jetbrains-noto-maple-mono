"""Sanity-check real build output before it gets uploaded/released.

The unit tests in scripts/tests/ verify the overlay functions in isolation
against small, fast codepoint subsets -- they can't catch a regression that
only shows up in the ACTUAL full build (e.g. a silent partial failure that
still leaves the font "valid" but missing most of its CJK coverage). This
runs a handful of cheap structural checks directly against the real .ttf
files a build just produced, so CI fails loudly instead of silently
uploading/publishing a broken font.

Run:

    python -m scripts.verify_build dist/fonts/*.ttf
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.ttLib import TTFont

from scripts.naming import BASE_FAMILY_NAME

MIN_GLYPH_COUNT = 40000  # full CJK + Latin should be ~55k; a big drop means something silently failed
JETBRAINS_NATIVE_FEATURES = {"zero", "cv01", "ss01", "frac", "ordn", "subs", "sups", "case"}


def verify_font(path: Path) -> list[str]:
    """Return a list of problem descriptions; empty means the font is fine."""
    problems: list[str] = []
    font = TTFont(str(path))

    num_glyphs = font["maxp"].numGlyphs
    if num_glyphs < MIN_GLYPH_COUNT:
        problems.append(f"only {num_glyphs} glyphs (expected >= {MIN_GLYPH_COUNT}) -- CJK overlay may have failed")

    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    if "A" not in hmtx.metrics:
        problems.append("missing Latin 'A' glyph entirely")
    else:
        latin_advance = hmtx["A"][0]
        for ch in ("中", "한", "し"):
            cp = ord(ch)
            if cp not in cmap:
                problems.append(f"missing CJK codepoint U+{cp:04X} ({ch})")
                continue
            advance = hmtx[cmap[cp]][0]
            if advance != latin_advance * 2:
                problems.append(
                    f"{ch} (U+{cp:04X}) advance={advance}, expected exactly {latin_advance * 2} (2x Latin)"
                )

    glyph_names = set(font.getGlyphOrder())
    if "tag_info.liga" not in glyph_names:
        problems.append("missing tag_info.liga -- tag ligature grafting may have failed")

    if "GSUB" not in font:
        problems.append("no GSUB table at all")
    else:
        feature_tags = {fr.FeatureTag for fr in font["GSUB"].table.FeatureList.FeatureRecord}
        missing_native = JETBRAINS_NATIVE_FEATURES - feature_tags
        if missing_native:
            problems.append(f"missing native JetBrains features: {sorted(missing_native)}")
        if "ss03" not in feature_tags:
            problems.append("missing ss03 (case-insensitive tag matching)")
        if "calt" not in feature_tags:
            problems.append("missing calt entirely")

    name_table = font["name"]
    family_record = name_table.getName(1, 3, 1, 0x409)
    if family_record is None or BASE_FAMILY_NAME not in family_record.toUnicode():
        problems.append("name table family name wasn't rewritten correctly")

    return problems


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        raise SystemExit("usage: python -m scripts.verify_build <font.ttf> [more.ttf ...]")

    any_failed = False
    for path in paths:
        problems = verify_font(path)
        if problems:
            any_failed = True
            print(f"[verify] FAIL {path.name}:")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print(f"[verify] OK {path.name}")

    if any_failed:
        raise SystemExit(1)
    print(f"[verify] all {len(paths)} font(s) passed")


if __name__ == "__main__":
    main()
