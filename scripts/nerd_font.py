"""Overlay Nerd Font's icon glyphs onto a base font.

Source: Nerd Fonts' own pre-patched "JetBrainsMono Nerd Font Mono" release
(download.py's jetbrains_mono_nerd_font_path()) -- the official font-patcher
already scaled every icon against JetBrains Mono's own cell metrics using
its per-icon-set ScaleGroups/Attributes rules, so there's no generic
donor-to-arbitrary-base fit to approximate here (an earlier version of this
module copied from NerdFontsSymbolsOnly's family-agnostic "Mono" release
and applied a hand-tuned global NERD_FONT_SCALE_BOOST to compensate for
icons looking too small at an exact 1:1 box-fit -- tuned by eye against
Maple Mono's own NF release). Verified: this donor's head.unitsPerEm,
hmtx advance, and hhea ascent/descent are identical to our own JetBrains
Mono base, so glyphs need zero rescaling, only a straight copy -- the exact
metrics ratio below only kicks in if a future Nerd Fonts/JetBrains Mono
version pairing drifts apart (should stay ~1.0).

Only NEW codepoints are added, matching every other overlay step in this
project: never touch what the base already covers.
"""

from __future__ import annotations

from pathlib import Path

from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont


def apply_nerd_font(base: TTFont, nerd_font_path: Path) -> int:
    """Mutate base in place, adding Nerd Font icon glyphs. Returns codepoints added."""
    nerd_font = TTFont(str(nerd_font_path))
    nerd_upm = nerd_font["head"].unitsPerEm
    nerd_cmap = nerd_font.getBestCmap()

    base_cmap = base.getBestCmap()
    base_upm = base["head"].unitsPerEm
    base_advance = base["hmtx"]["A"][0]

    # Both fonts are patched from/built as JetBrains Mono, so this is a
    # no-op scale (1.0) in practice -- kept as a real ratio, not a hardcoded
    # 1.0, so a future upstream metrics drift degrades gracefully instead of
    # silently mis-sizing every icon.
    scale = base_upm / nerd_upm
    x_shift = 0.0
    y_shift = 0.0

    base_glyf = base["glyf"]
    base_hmtx = base["hmtx"]
    glyph_order = list(base.getGlyphOrder())
    existing_names = set(glyph_order)
    nerd_glyph_set = nerd_font.getGlyphSet()

    added = 0
    name_cache: dict[str, str] = {}
    cmap_additions: dict[int, str] = {}

    for cp, glyph_name in sorted(nerd_cmap.items()):
        if cp in base_cmap:
            continue
        if glyph_name in name_cache:
            new_name = name_cache[glyph_name]
        else:
            new_name = glyph_name
            if new_name in existing_names:
                new_name = f"nf.{glyph_name}"
                suffix = 1
                while new_name in existing_names:
                    new_name = f"nf.{glyph_name}.{suffix}"
                    suffix += 1

            pen = TTGlyphPen(None)
            if scale == 1.0:
                nerd_glyph_set[glyph_name].draw(pen)
            else:
                transform_pen = TransformPen(pen, (scale, 0, 0, scale, x_shift, y_shift))
                nerd_glyph_set[glyph_name].draw(transform_pen)
            base_glyf[new_name] = pen.glyph()
            base_hmtx[new_name] = (base_advance, 0)

            existing_names.add(new_name)
            glyph_order.append(new_name)
            name_cache[glyph_name] = new_name

        cmap_additions[cp] = new_name
        added += 1

    base_glyf.setGlyphOrder(glyph_order)
    base.setGlyphOrder(glyph_order)
    base["maxp"].numGlyphs = len(glyph_order)

    for table in base["cmap"].tables:
        max_cp = 0xFFFF if table.format == 4 else 0x10FFFF
        for cp, name in cmap_additions.items():
            if cp <= max_cp:
                table.cmap[cp] = name

    return added
