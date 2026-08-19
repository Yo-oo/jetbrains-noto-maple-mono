"""Build JetBrains Noto Maple Mono: JetBrains Mono + Noto Sans CJK + Maple Mono's tags.

Per (weight, style):
  1. Download JetBrains Mono {weight}[Italic].ttf as the base.
  2. Overlay Noto Sans CJK (tc/jp/kr, instantiated from the variable font at
     this weight) at codepoints the base doesn't already have, exactly 2x
     the Latin advance width (overlay_cjk.py). Italic applies a synthetic
     shear -- Noto has no italic CJK register at all to draw from instead.
  3. Graft Maple Mono's plain-text tag ligatures (`[INFO]`, `[WARN]`, ...)
     fresh into calt, from Maple's matching weight+style release
     (tag_ligatures.py).
  4. Rewrite the name table to this project's own identity (rename.py).
  5. Optionally patch in Nerd Font icons (nerd_font.py).

All 8 weights JetBrains Mono/Maple Mono ship (Thin-ExtraBold) x both styles
(Regular/Italic) are supported, even though Noto Sans CJK's variable font
only technically needs instantiating once per weight regardless of style.

Run:

    python -m scripts.build [--weights thin,regular,bold] \
        [--styles regular,italic] [--out dist/fonts] [--nerd-font] \
        [--version 0.2.0]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.ttLib import TTFont

from scripts.common import FONTS_DIR, read_project_version
from scripts.config import load_config
from scripts.download import (
    JETBRAINS_MONO_VERSION,
    MAPLE_MONO_VERSION,
    NOTO_CJK_RELEASE_TAG,
    WEIGHT_VALUES,
    WEIGHTS,
    jetbrains_mono_path,
    maple_mono_path,
    nerd_font_symbols_path,
    noto_cjk_weight_instance_path,
    style_suffix,
)
from scripts.nerd_font import apply_nerd_font
from scripts.overlay_cjk import overlay_cjk
from scripts.rename import apply_family_name
from scripts.tag_ligatures import apply_tag_ligatures

_config = load_config()
FAMILY_NAME = _config["family_name"]
FILE_PREFIX = FAMILY_NAME.replace(" ", "")

# JetBrains Mono's OWN italic angle -- read from JetBrainsMono-Italic.ttf's
# post.italicAngle (-9.0) and confirmed against hhea's caret slope (~9.0 deg
# from caretSlopeRise/Run = 1000/158). NOT the same as the old build.py-based
# pipeline's CJK shear angle (10 deg), which was tuned for Maple Mono's own
# italic angle -- that number doesn't apply here since JetBrains Mono has a
# shallower slant. Matching JetBrains' actual angle keeps CJK glyphs' shear
# visually consistent with the Latin italic they sit next to. Pinned in
# config.json (cjk.italic_angle).
CJK_ITALIC_ANGLE = _config["cjk"]["italic_angle"]
WEIGHT_KEYS = {w.lower(): w for w in WEIGHTS}


def build_one(
    weight_key: str, italic: bool, out_dir: Path, nerd_font: bool, project_version: str
) -> Path:
    weight = WEIGHT_KEYS[weight_key]
    label = style_suffix(weight, italic)
    print(f"[build] {label}: downloading upstream releases...")
    jbm_path = jetbrains_mono_path(weight, italic)
    weight_value = WEIGHT_VALUES[weight]
    tc_path = noto_cjk_weight_instance_path("tc", weight_value)
    jp_path = noto_cjk_weight_instance_path("jp", weight_value)
    kr_path = noto_cjk_weight_instance_path("kr", weight_value)
    maple_path = maple_mono_path(weight, italic)

    font = TTFont(str(jbm_path))

    print(f"[build] {label}: overlaying Noto Sans CJK...")
    added = overlay_cjk(
        font, tc_path, jp_path, kr_path,
        italic_angle=CJK_ITALIC_ANGLE if italic else 0.0,
    )
    print(f"[build] {label}: added {added} CJK codepoints")

    print(f"[build] {label}: grafting Maple Mono tag ligatures...")
    tag_count = apply_tag_ligatures(font, maple_path)
    print(f"[build] {label}: grafted {tag_count} tags")

    if nerd_font:
        print(f"[build] {label}: patching Nerd Font icons...")
        nerd_count = apply_nerd_font(font, nerd_font_symbols_path())
        print(f"[build] {label}: added {nerd_count} Nerd Font icons")

    upstream_versions = {
        "JetBrains Mono": JETBRAINS_MONO_VERSION,
        "Noto Sans CJK": NOTO_CJK_RELEASE_TAG,
        "Maple Mono": MAPLE_MONO_VERSION,
    }
    apply_family_name(font, FAMILY_NAME, label, project_version, upstream_versions)

    out_path = out_dir / f"{FILE_PREFIX}-{label}.ttf"
    out_dir.mkdir(parents=True, exist_ok=True)
    font.save(str(out_path))
    print(f"[build] {label}: saved {out_path}")
    return out_path


def main() -> None:
    build_defaults = _config["build_defaults"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", default=build_defaults["weights"])
    parser.add_argument("--styles", default=build_defaults["styles"])
    parser.add_argument("--out", type=Path, default=FONTS_DIR)
    parser.add_argument("--nerd-font", action="store_true", default=build_defaults["nerd_font"])
    parser.add_argument(
        "--version",
        default=None,
        help=(
            "Version string embedded in the font's own name table. Defaults to "
            "pyproject.toml's version (a dev-build placeholder) -- release.yml "
            "passes the git tag being released instead, so the tag is the single "
            "source of truth for a real release rather than something that has "
            "to be kept in sync by hand across two files."
        ),
    )
    args = parser.parse_args()
    project_version = args.version or read_project_version()

    weight_keys = [w.strip().lower() for w in args.weights.split(",") if w.strip()]
    unknown = set(weight_keys) - set(WEIGHT_KEYS)
    if unknown:
        raise SystemExit(f"unknown weight(s): {sorted(unknown)} -- choose from {sorted(WEIGHT_KEYS)}")

    style_map = {"regular": False, "italic": True}
    style_keys = [s.strip().lower() for s in args.styles.split(",") if s.strip()]
    unknown_styles = set(style_keys) - set(style_map)
    if unknown_styles:
        raise SystemExit(f"unknown style(s): {sorted(unknown_styles)} -- choose from regular, italic")

    produced = [
        build_one(weight_key, style_map[style_key], args.out, args.nerd_font, project_version)
        for weight_key in weight_keys
        for style_key in style_keys
    ]
    print(f"[build] done: {len(produced)} font(s) in {args.out}")


if __name__ == "__main__":
    main()
