"""Build Blanda JNM Mono: JetBrains Mono + Noto Sans CJK + Maple Mono's tags.

Per (weight, style):
  1. Download JetBrains Mono {weight}[Italic].ttf as the base.
  2. Overlay Noto Sans CJK (han_priority locale for Han/punctuation, jp for
     kana, kr for hangul -- each instantiated from its variable font at this
     weight) at codepoints the base doesn't already have, exactly 2x the
     Latin advance width (overlay_cjk.py). Italic applies a synthetic
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
    NERD_FONT_VERSION,
    NOTO_CJK_RELEASE_TAG,
    WEIGHT_VALUES,
    WEIGHTS,
    jetbrains_mono_nerd_font_path,
    jetbrains_mono_path,
    maple_mono_path,
    noto_cjk_weight_instance_path,
    style_suffix,
)
from scripts.naming import compose_family_name, compose_file_prefix
from scripts.nerd_font import apply_nerd_font
from scripts.overlay_cjk import CJK_FILL_RATIO, overlay_cjk
from scripts.rename import apply_family_name
from scripts.tag_ligatures import apply_tag_ligatures

_config = load_config()

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

# Which locale's Noto Sans CJK release provides the Han + shared CJK
# punctuation/symbols/bopomofo glyphs (kana/hangul always come from jp/kr
# regardless of this -- see overlay_cjk.py's module docstring for why).
# Pinned in config.json (cjk.han_priority), overridable per-build via
# --han-priority for local/self-built variants -- not exposed as a separate
# release.yml build matrix entry (see conversation: tc/hk/sc/jp/kr cover the
# exact same codepoints, only glyph shape differs, so this is a one-line
# config change for anyone who wants a different regional build, not a
# reason to multiply the number of official release assets).
HAN_PRIORITY_CHOICES = ("tc", "hk", "sc", "jp", "kr")
HAN_PRIORITY_DEFAULT = _config["cjk"]["han_priority"]


def build_one(
    weight_key: str,
    italic: bool,
    out_dir: Path,
    nerd_font: bool,
    project_version: str,
    han_priority: str = HAN_PRIORITY_DEFAULT,
    fill_ratio: float = CJK_FILL_RATIO,
    italic_angle: float = CJK_ITALIC_ANGLE,
    jetbrains_mono_version: str = JETBRAINS_MONO_VERSION,
    noto_cjk_release_tag: str = NOTO_CJK_RELEASE_TAG,
    maple_mono_version: str = MAPLE_MONO_VERSION,
    nerd_fonts_version: str = NERD_FONT_VERSION,
) -> Path:
    weight = WEIGHT_KEYS[weight_key]
    label = style_suffix(weight, italic)
    print(f"[build] {label}: downloading upstream releases...")
    jbm_path = jetbrains_mono_path(weight, italic, version=jetbrains_mono_version)
    weight_value = WEIGHT_VALUES[weight]
    han_path = noto_cjk_weight_instance_path(
        han_priority, weight_value, version=noto_cjk_release_tag
    )
    jp_path = noto_cjk_weight_instance_path("jp", weight_value, version=noto_cjk_release_tag)
    kr_path = noto_cjk_weight_instance_path("kr", weight_value, version=noto_cjk_release_tag)
    maple_path = maple_mono_path(weight, italic, version=maple_mono_version)

    font = TTFont(str(jbm_path))

    print(f"[build] {label}: overlaying Noto Sans CJK (han_priority={han_priority})...")
    added = overlay_cjk(
        font, han_path, jp_path, kr_path,
        italic_angle=italic_angle if italic else 0.0,
        fill_ratio=fill_ratio,
    )
    print(f"[build] {label}: added {added} CJK codepoints")

    print(f"[build] {label}: grafting Maple Mono tag ligatures...")
    tag_count = apply_tag_ligatures(font, maple_path)
    print(f"[build] {label}: grafted {tag_count} tags")

    # NF and non-NF are separate, side-by-side-installable variants -- like
    # every other Nerd Font patched font, appending " NF" to the family name
    # (rather than silently baking icons into the same name) is what lets a
    # font picker/terminal config tell them apart, and lets a user keep both
    # installed if they use icons in some apps but not others. Han-priority
    # locale is folded in too (naming.py), so a future sc/jp/kr/hk release
    # variant gets its own name for free.
    family_name = compose_family_name(han_priority, nerd_font)
    file_prefix = compose_file_prefix(han_priority, nerd_font)

    if nerd_font:
        print(f"[build] {label}: patching Nerd Font icons...")
        nerd_count = apply_nerd_font(
            font, jetbrains_mono_nerd_font_path(version=nerd_fonts_version)
        )
        print(f"[build] {label}: added {nerd_count} Nerd Font icons")

    upstream_versions = {
        "JetBrains Mono": jetbrains_mono_version,
        "Noto Sans CJK": noto_cjk_release_tag,
        "Maple Mono": maple_mono_version,
    }
    apply_family_name(font, family_name, weight, italic, project_version, upstream_versions)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{file_prefix}-{label}.ttf"
    font.save(str(out_path))
    print(f"[build] {label}: saved {out_path}")

    # Same table data, different container: flavor="woff2" only changes how
    # save() packs the sfnt (brotli-compressed, web-oriented), so this is a
    # second save() on the same already-built font object, not a rebuild.
    woff2_path = out_dir / f"{file_prefix}-{label}.woff2"
    font.flavor = "woff2"
    font.save(str(woff2_path))
    print(f"[build] {label}: saved {woff2_path}")
    return out_path


def main() -> None:
    build_defaults = _config["build_defaults"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", default=build_defaults["weights"])
    parser.add_argument("--styles", default=build_defaults["styles"])
    parser.add_argument("--out", type=Path, default=FONTS_DIR)
    parser.add_argument("--nerd-font", action="store_true", default=build_defaults["nerd_font"])
    parser.add_argument(
        "--han-priority",
        choices=HAN_PRIORITY_CHOICES,
        default=HAN_PRIORITY_DEFAULT,
        help=(
            "Which locale's Noto Sans CJK release provides Han + shared CJK "
            "punctuation/symbols/bopomofo glyphs (kana/hangul always come "
            "from jp/kr regardless). Defaults to config.json's cjk.han_priority."
        ),
    )
    parser.add_argument(
        "--fill-ratio",
        type=float,
        default=CJK_FILL_RATIO,
        help="CJK glyph shrink-toward-center ratio. Defaults to config.json's cjk.fill_ratio.",
    )
    parser.add_argument(
        "--italic-angle",
        type=float,
        default=CJK_ITALIC_ANGLE,
        help=(
            "Synthetic CJK italic shear angle in degrees. Defaults to "
            "config.json's cjk.italic_angle."
        ),
    )
    parser.add_argument(
        "--jetbrains-mono-version",
        default=JETBRAINS_MONO_VERSION,
        help=(
            "Override the pinned JetBrains Mono release version for this build only "
            "(config.json's upstream_versions.jetbrains_mono is untouched -- "
            "release.yml never passes this, so a real release always uses what's "
            "pinned there)."
        ),
    )
    parser.add_argument(
        "--noto-cjk-release-tag",
        default=NOTO_CJK_RELEASE_TAG,
        help="Override the pinned Noto Sans CJK release tag for this build only.",
    )
    parser.add_argument(
        "--maple-mono-version",
        default=MAPLE_MONO_VERSION,
        help="Override the pinned Maple Mono release version for this build only.",
    )
    parser.add_argument(
        "--nerd-fonts-version",
        default=NERD_FONT_VERSION,
        help="Override the pinned Nerd Fonts release version for this build only.",
    )
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
        build_one(
            weight_key,
            style_map[style_key],
            args.out,
            args.nerd_font,
            project_version,
            han_priority=args.han_priority,
            fill_ratio=args.fill_ratio,
            italic_angle=args.italic_angle,
            jetbrains_mono_version=args.jetbrains_mono_version,
            noto_cjk_release_tag=args.noto_cjk_release_tag,
            maple_mono_version=args.maple_mono_version,
            nerd_fonts_version=args.nerd_fonts_version,
        )
        for weight_key in weight_keys
        for style_key in style_keys
    ]
    print(f"[build] done: {len(produced)} font(s) in {args.out}")


if __name__ == "__main__":
    main()
