"""Build JetBrains Noto Maple Mono: JetBrains Mono + Noto Sans Mono CJK + Maple Mono's tags.

Per weight:
  1. Download JetBrains Mono {weight}.ttf as the base.
  2. Overlay Noto Sans Mono CJK (tc/jp/kr) at codepoints the base doesn't
     already have, exactly 2x the Latin advance width (overlay_cjk.py).
  3. Graft Maple Mono's plain-text tag ligatures (`[INFO]`, `[WARN]`, ...)
     fresh into calt (tag_ligatures.py).
  4. Rewrite the name table to this project's own identity (rename.py).

Only Regular and Bold are built: Noto Sans Mono CJK -- the only Noto CJK
release actually designed for exact monospace pairing, which is the whole
reason this project doesn't need risky custom scale/shift tuning -- ships
just those two weights, no lighter/heavier registers. No italic: neither
Noto Sans Mono CJK nor Maple's tag badges have an italic register, and
faux-obliquing CJK ideographs isn't standard practice (Noto/Adobe don't
publish an italic CJK for exactly this reason).

Run:

    python -m scripts.build [--weights regular,bold] [--out dist/fonts]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.ttLib import TTFont

from scripts.common import FONTS_DIR
from scripts.download import (
    JETBRAINS_MONO_VERSION,
    jetbrains_mono_path,
    maple_mono_path,
    noto_mono_cjk_path,
)
from scripts.overlay_cjk import overlay_cjk
from scripts.rename import apply_family_name
from scripts.tag_ligatures import apply_tag_ligatures

WEIGHT_NAMES = {"regular": "Regular", "bold": "Bold"}


def build_one(weight_key: str, out_dir: Path) -> Path:
    weight = WEIGHT_NAMES[weight_key]
    print(f"[build] {weight}: downloading upstream releases...")
    jbm_path = jetbrains_mono_path(weight)
    tc_path = noto_mono_cjk_path("tc", weight)
    jp_path = noto_mono_cjk_path("jp", weight)
    kr_path = noto_mono_cjk_path("kr", weight)
    maple_path = maple_mono_path(weight)

    font = TTFont(str(jbm_path))

    print(f"[build] {weight}: overlaying Noto Sans Mono CJK...")
    added = overlay_cjk(font, tc_path, jp_path, kr_path)
    print(f"[build] {weight}: added {added} CJK codepoints")

    print(f"[build] {weight}: grafting Maple Mono tag ligatures...")
    tag_count = apply_tag_ligatures(font, maple_path)
    print(f"[build] {weight}: grafted {tag_count} tags")

    apply_family_name(font, weight, JETBRAINS_MONO_VERSION)

    out_path = out_dir / f"JetBrainsNotoMapleMono-{weight}.ttf"
    out_dir.mkdir(parents=True, exist_ok=True)
    font.save(str(out_path))
    print(f"[build] {weight}: saved {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", default="regular,bold")
    parser.add_argument("--out", type=Path, default=FONTS_DIR)
    args = parser.parse_args()

    weight_keys = [w.strip().lower() for w in args.weights.split(",") if w.strip()]
    unknown = set(weight_keys) - set(WEIGHT_NAMES)
    if unknown:
        raise SystemExit(f"unknown weight(s): {sorted(unknown)} -- choose from {sorted(WEIGHT_NAMES)}")

    produced = [build_one(weight_key, args.out) for weight_key in weight_keys]
    print(f"[build] done: {len(produced)} font(s) in {args.out}")


if __name__ == "__main__":
    main()
