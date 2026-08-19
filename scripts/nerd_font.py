"""Overlay Nerd Font's icon glyphs onto a base font.

Source: NerdFontsSymbolsOnly's "Mono" variant -- a release specifically
published for exactly this "merge into another font" use case (unlike the
main Nerd Fonts release, which is meant to be used standalone and requires
the full FontForge-based patcher to extract). No FontForge/system
dependency needed: it's a plain glyf-outline TTF, copied the same way
overlay_cjk.py/tag_ligatures.py copy artwork from their own donors.

All 10519 glyphs in this release share one fixed advance (2048, in a
2048-unitsPerEm font) -- deliberately single-cell width for terminal icon
usage, unlike CJK's 2x-cell convention. Scaled to the base font's own
single Latin cell width and vertically centered around the base's own
(ascent+descent)/2, both read from each font's actual tables (no hardcoded
assumptions about either font's metrics).

NERD_FONT_SCALE_BOOST (config.json's nerd_font.scale_boost) enlarges icons
beyond an exact 1:1 fit to the cell, applied around the cell's own center so
they grow symmetrically rather than toward one edge. This isn't a bug fix
for the source artwork (measured: these icons already fill ~100% of their
own native 2048 box width, they're not drawn with generous padding) -- it's
compensating for a real perceptual effect: sparse icon linework reads as
visually smaller/lighter than dense text glyphs at the same nominal box
size, which is why patched Nerd Fonts conventionally scale icons up beyond
a naive box-fit. Tune by eye, like CJK_FILL_RATIO; icons are expected to
slightly overflow their nominal single-cell width at higher boost values --
that's normal for Nerd Font icon rendering, not clipped or misaligned.

Only NEW codepoints are added, matching every other overlay step in this
project: never touch what the base already covers.
"""

from __future__ import annotations

from pathlib import Path

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from scripts.config import load_config

NERD_FONT_SCALE_BOOST = load_config()["nerd_font"]["scale_boost"]


def apply_nerd_font(base: TTFont, nerd_font_path: Path) -> int:
    """Mutate base in place, adding Nerd Font icon glyphs. Returns codepoints added."""
    nerd_font = TTFont(str(nerd_font_path))
    nerd_upm = nerd_font["head"].unitsPerEm
    nerd_cmap = nerd_font.getBestCmap()
    nerd_hhea = nerd_font["hhea"]

    base_cmap = base.getBestCmap()
    base_advance = base["hmtx"]["A"][0]
    base_hhea = base["hhea"]

    fit_scale = base_advance / nerd_upm
    base_center_y = (base_hhea.ascent + base_hhea.descent) / 2
    nerd_center_y = (nerd_hhea.ascent + nerd_hhea.descent) / 2 * fit_scale
    fit_y_shift = base_center_y - nerd_center_y

    # Compose the exact-fit transform above with a boost around the cell's
    # own center (base_advance/2 horizontally, base_center_y vertically),
    # so enlarging doesn't also drift the icon off-center.
    boost = NERD_FONT_SCALE_BOOST
    cell_center_x = base_advance / 2
    scale = fit_scale * boost
    x_shift = cell_center_x * (1 - boost)
    y_shift = boost * fit_y_shift + base_center_y * (1 - boost)

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
            cu2qu_pen = Cu2QuPen(pen, max_err=1.0, reverse_direction=True)
            transform_pen = TransformPen(cu2qu_pen, (scale, 0, 0, scale, x_shift, y_shift))
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
