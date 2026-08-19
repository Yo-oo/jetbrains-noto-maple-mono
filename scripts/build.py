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
        [--styles regular,italic] [--out dist/fonts] [--nerd-font]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.ttLib import TTFont

from scripts.common import FONTS_DIR, read_project_version
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

CJK_ITALIC_ANGLE = 10.0
WEIGHT_KEYS = {w.lower(): w for w in WEIGHTS}


def build_one(weight_key: str, italic: bool, out_dir: Path, nerd_font: bool) -> Path:
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
    apply_family_name(font, label, read_project_version(), upstream_versions)

    out_path = out_dir / f"JetBrainsNotoMapleMono-{label}.ttf"
    out_dir.mkdir(parents=True, exist_ok=True)
    font.save(str(out_path))
    print(f"[build] {label}: saved {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", default="regular,bold")
    parser.add_argument("--styles", default="regular")
    parser.add_argument("--out", type=Path, default=FONTS_DIR)
    parser.add_argument("--nerd-font", action="store_true")
    args = parser.parse_args()

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
        build_one(weight_key, style_map[style_key], args.out, args.nerd_font)
        for weight_key in weight_keys
        for style_key in style_keys
    ]
    print(f"[build] done: {len(produced)} font(s) in {args.out}")


if __name__ == "__main__":
    main()
