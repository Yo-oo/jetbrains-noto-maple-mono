"""Overlay Noto Sans CJK glyphs onto a JetBrains Mono base.

Source: the regular (non-"Mono") Noto Sans CJK variable font, instantiated
per weight (download.py's noto_cjk_weight_instance_path) -- NOT the
dedicated "Mono" release, which only ships Regular/Bold with no usable
variable-weight version. Despite Noto Sans CJK being a "proportional"
family, its Han/Hangul/Kana glyphs use the exact same fixed-fullwidth
convention as the Mono release at every weight (verified: Han advance=1000,
Hangul=920, identical from wght 100 to 900) -- proportionality in this
family only affects Latin/punctuation, never CJK ideograph-class scripts.
Source is glyf (TrueType), not CFF, but the Cu2QuPen conversion step below
is kept anyway -- verified it passes already-quadratic input through
unchanged, so this works for either outline format without a branch.

Source-of-truth per codepoint: tc (Traditional Chinese Han shapes + shared
CJK punctuation/symbols/bopomofo) by default, overridden by jp for kana and
kr for hangul -- each locale's own release renders those scripts with
locale-appropriate typography even though all three regional releases
technically contain the full repertoire.

Transform: Noto's own fullwidth advance is exactly 2x ITS OWN paired Latin
advance (1000 vs 500, in a 1000-unitsPerEm font) -- it's designed for
pairing with a monospace Latin font, just not this specific one. JetBrains
Mono's Latin advance is 600, so the natural target scale is 1200/1000 =
1.2x. But that "1000" isn't universal within Noto CJK itself: Hangul
syllables use a narrower native advance (920) than Han/Kana's 1000, by
design (Hangul blocks are drawn with built-in side padding). Scaling
everything by the same 1.2x factor derived from Han's 1000 therefore
under-fills Hangul's cell, making it visibly smaller/lighter than Han at
the same nominal advance width -- so scale is computed PER GLYPH from that
glyph's own source advance, not one constant. Vertical centering is
likewise computed per SOURCE FONT (tc/jp/kr can each carry slightly
different hhea ascent/descent), around JetBrains' own (ascent+descent)/2,
all read from each loaded font's actual tables.

Only NEW codepoints are added (skip any codepoint the base already maps),
matching overlay_latin.py's spirit in the old maple-font fork: never
overwrite what's already there, since CJK and JetBrains' own Latin/symbol
coverage shouldn't overlap in the first place.

CJK_FILL_RATIO is a separate, purely cosmetic knob layered on top of the
width-alignment math above: it shrinks each glyph toward its cell's center
by a fixed percentage, adding uniform breathing room on all sides. Noto Sans
Mono CJK's own native margins (preserved by the transform above) fill more
of the 2x cell than this project's earlier build.py-based pipeline did --
side by side, Noto reads as visually denser/more cramped even though both
are mathematically exact 2x. This is a density preference, not a
correctness fix; tune the constant, don't touch the scale/shift math above.
"""

from __future__ import annotations

import math
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

from scripts.config import load_config

# Shrink toward cell center by this fraction (1.0 = no shrink) -- see module
# docstring. Tune by eye against a reference font; not derived from metrics.
# Pinned in config.json (cjk.fill_ratio), not here, so every tunable knob
# this project exposes lives in one place.
CJK_FILL_RATIO = load_config()["cjk"]["fill_ratio"]

# (start, end) inclusive Unicode ranges, in override-priority order applied
# AFTER the tc-wide base pass.
JP_KANA_RANGES = (
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
    (0x31F0, 0x31FF),  # Katakana Phonetic Extensions
    (0xFF65, 0xFF9F),  # Halfwidth Katakana
)
KR_HANGUL_RANGES = (
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x3130, 0x318F),  # Hangul Compatibility Jamo
    (0xA960, 0xA97F),  # Hangul Jamo Extended-A
    (0xAC00, 0xD7A3),  # Hangul Syllables
    (0xD7B0, 0xD7FF),  # Hangul Jamo Extended-B
)


def _in_ranges(cp: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= cp <= end for start, end in ranges)


def build_codepoint_source_map(
    tc_font: TTFont, jp_font: TTFont, kr_font: TTFont
) -> dict[int, tuple[TTFont, str]]:
    """Return {codepoint: (source_font, glyph_name)}, tc-wide with jp/kr overrides."""
    tc_cmap = tc_font.getBestCmap()
    jp_cmap = jp_font.getBestCmap()
    kr_cmap = kr_font.getBestCmap()

    result: dict[int, tuple[TTFont, str]] = {
        cp: (tc_font, name) for cp, name in tc_cmap.items()
    }
    for cp, name in jp_cmap.items():
        if _in_ranges(cp, JP_KANA_RANGES):
            result[cp] = (jp_font, name)
    for cp, name in kr_cmap.items():
        if _in_ranges(cp, KR_HANGUL_RANGES):
            result[cp] = (kr_font, name)
    return result


def _vertical_shift_for(cjk_font: TTFont, jetbrains_font: TTFont, scale: float) -> float:
    jb_hhea = jetbrains_font["hhea"]
    cjk_hhea = cjk_font["hhea"]
    jb_center = (jb_hhea.ascent + jb_hhea.descent) / 2
    cjk_center = (cjk_hhea.ascent + cjk_hhea.descent) / 2 * scale
    return jb_center - cjk_center


def overlay_cjk(
    base: TTFont,
    tc_path: Path,
    jp_path: Path,
    kr_path: Path,
    codepoint_filter: set[int] | None = None,
    italic_angle: float = 0.0,
) -> int:
    """Mutate base in place, adding CJK glyphs at codepoints it doesn't already have.

    codepoint_filter restricts the run to a handful of codepoints -- for fast
    local iteration only (Cu2Qu curve fitting over the full ~44k-glyph Noto
    repertoire takes minutes). Leave it unset for a real build: this project
    deliberately keeps Noto's full coverage rather than trimming to a
    practical subset, since maximum CJK coverage is the whole point of
    choosing Noto as the source.

    italic_angle (degrees) applies a synthetic horizontal shear on top of the
    width/vertical transform -- Noto Sans CJK has no italic register at all,
    so there is no "real" italic CJK to use. This is the same synthesis
    technique this project's earlier build.py-based pipeline used (a plain
    skew, not a redrawn italic design); it's a known, accepted compromise for
    CJK+Latin pairings, not a claim that Noto ships a genuine italic.

    Returns the number of codepoints added.
    """
    tc_font = TTFont(str(tc_path))
    jp_font = TTFont(str(jp_path))
    kr_font = TTFont(str(kr_path))

    base_cmap = base.getBestCmap()
    base_advance = base["hmtx"]["A"][0]
    target_advance = base_advance * 2
    source_map = build_codepoint_source_map(tc_font, jp_font, kr_font)
    if codepoint_filter is not None:
        source_map = {cp: v for cp, v in source_map.items() if cp in codepoint_filter}

    # scale is computed per glyph (from that glyph's own native advance) so
    # Hangul's narrower 920 native advance doesn't end up under-filling its
    # cell relative to Han/Kana's 1000 -- see module docstring.
    y_shift_by_font_id = {
        id(font): _vertical_shift_for(font, base, target_advance / 1000)
        for font in (tc_font, jp_font, kr_font)
    }
    jb_hhea = base["hhea"]
    jb_center = (jb_hhea.ascent + jb_hhea.descent) / 2
    # Fixed offsets for the CJK_FILL_RATIO shrink-toward-center step, composed
    # into the same matrix as the width/vertical transform below.
    fill_tx = target_advance / 2 * (1 - CJK_FILL_RATIO)
    fill_ty = jb_center * (1 - CJK_FILL_RATIO)
    shear_tan = math.tan(math.radians(italic_angle))

    base_glyf = base["glyf"]
    base_hmtx = base["hmtx"]
    glyph_order = list(base.getGlyphOrder())
    existing_names = set(glyph_order)

    added = 0
    name_cache: dict[tuple[int, str], str] = {}  # (id(source_font), glyph_name) -> new_name

    def copy_glyph(source_font: TTFont, glyph_name: str) -> str:
        cache_key = (id(source_font), glyph_name)
        if cache_key in name_cache:
            return name_cache[cache_key]

        new_name = glyph_name
        if new_name in existing_names:
            new_name = f"cjk.{glyph_name}"
            suffix = 1
            while new_name in existing_names:
                new_name = f"cjk.{glyph_name}.{suffix}"
                suffix += 1

        source_hmtx = source_font["hmtx"]
        native_advance = source_hmtx[glyph_name][0]
        scale = target_advance / native_advance if native_advance else target_advance / 1000
        y_shift = y_shift_by_font_id[id(source_font)]

        # Composed matrix: the width/vertical-alignment transform above,
        # followed by the CJK_FILL_RATIO shrink-toward-cell-center (see
        # module docstring) -- combined into one matrix rather than two
        # chained TransformPens.
        combined_scale = scale * CJK_FILL_RATIO
        combined_tx = fill_tx
        combined_ty = y_shift * CJK_FILL_RATIO + fill_ty

        # Fold the italic shear (x depends on y) into the same matrix: a
        # point's final y (combined_scale*y + combined_ty) contributes
        # shear_tan times itself to the final x.
        matrix = (
            combined_scale,
            0,
            combined_scale * shear_tan,
            combined_scale,
            combined_tx + combined_ty * shear_tan,
            combined_ty,
        )

        source_glyph_set = source_font.getGlyphSet()
        # Cu2QuPen converts cubic Bezier input (e.g. from a CFF source) to
        # the quadratic curves glyf requires; verified it passes already-
        # quadratic input (e.g. this glyf-based Noto Sans CJK VF) through
        # unchanged, so it's safe to keep unconditionally either way.
        pen = TTGlyphPen(None)
        cu2qu_pen = Cu2QuPen(pen, max_err=1.0, reverse_direction=True)
        transform_pen = TransformPen(cu2qu_pen, matrix)
        source_glyph_set[glyph_name].draw(transform_pen)
        new_glyph = pen.glyph()
        base_glyf[new_name] = new_glyph

        # hmtx's left-side-bearing is a cached copy of the glyph's own xMin,
        # not an independent value -- TTGlyphPen doesn't compute xMin/xMax on
        # its own (recalcBounds does), and hardcoding LSB=0 here regardless
        # of the glyph's true xMin silently desyncs the two. Higher-level
        # rendering paths (fontTools' own getGlyphSet().draw(), and browser
        # engines) trust hmtx's LSB for phantom-point positioning and shift
        # the whole outline to match it -- so a wrong LSB visibly drags the
        # glyph to the wrong x position (confirmed: every copied glyph was
        # rendering flush against the left cell edge regardless of its
        # actual shape, before this fix).
        new_glyph.recalcBounds(base_glyf)
        lsb = new_glyph.xMin if new_glyph.numberOfContours != 0 else 0
        base_hmtx[new_name] = (target_advance, lsb)

        existing_names.add(new_name)
        glyph_order.append(new_name)
        name_cache[cache_key] = new_name
        return new_name

    cmap_additions: dict[int, str] = {}
    for cp, (source_font, glyph_name) in sorted(source_map.items()):
        if cp in base_cmap:
            continue
        new_name = copy_glyph(source_font, glyph_name)
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
