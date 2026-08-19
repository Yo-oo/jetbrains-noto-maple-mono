"""Tests for overlay_cjk.py against real (cached) upstream downloads.

Uses codepoint_filter to keep these fast (seconds, not the minutes a full
~44k-glyph Cu2Qu conversion takes) -- see overlay_cjk.py's own docstring.
Network access is required on first run only; download.py caches everything
under dist/upstream/ afterward.
"""

from __future__ import annotations

import unittest

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

from scripts.download import jetbrains_mono_path, noto_cjk_weight_instance_path
from scripts.overlay_cjk import overlay_cjk

TEST_CHARS = "中文資料真好，。：；しくす私にの니다습조화한글국際"


def _build_test_font(weight_value: int = 400, italic_angle: float = 0.0) -> TTFont:
    base = TTFont(str(jetbrains_mono_path("Regular")))
    tc = noto_cjk_weight_instance_path("tc", weight_value)
    jp = noto_cjk_weight_instance_path("jp", weight_value)
    kr = noto_cjk_weight_instance_path("kr", weight_value)
    codepoints = {ord(c) for c in TEST_CHARS}
    overlay_cjk(base, tc, jp, kr, codepoint_filter=codepoints, italic_angle=italic_angle)
    return base


class OverlayCjkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font = _build_test_font()
        cls.cmap = cls.font.getBestCmap()
        cls.hmtx = cls.font["hmtx"]
        cls.latin_advance = cls.hmtx["A"][0]

    def test_latin_advance_is_600(self):
        # Sanity check on the assumption every width calculation depends on.
        self.assertEqual(self.latin_advance, 600)

    def test_han_is_exactly_2x_latin(self):
        name = self.cmap[ord("中")]
        self.assertEqual(self.hmtx[name][0], self.latin_advance * 2)

    def test_hangul_is_exactly_2x_latin(self):
        # Hangul's native advance (920) differs from Han/Kana's (1000) --
        # the historical bug this project hit was under-scaling Hangul
        # using a single constant derived from Han's advance instead of
        # each glyph's own.
        name = self.cmap[ord("한")]
        self.assertEqual(self.hmtx[name][0], self.latin_advance * 2)

    def test_hiragana_is_exactly_2x_latin(self):
        name = self.cmap[ord("し")]
        self.assertEqual(self.hmtx[name][0], self.latin_advance * 2)

    def test_punctuation_is_exactly_2x_latin(self):
        for ch in "，。：；":
            name = self.cmap[ord(ch)]
            self.assertEqual(self.hmtx[name][0], self.latin_advance * 2, msg=ch)

    def test_new_glyphs_have_nonzero_left_side_bearing_matching_ink(self):
        # Regression test for the hmtx LSB=0 bug: every copied glyph's
        # stored left-side-bearing must match its actual ink's xMin, or
        # higher-level rendering paths (browsers, fontTools' own
        # getGlyphSet().draw()) drag the whole glyph flush against the
        # cell's left edge regardless of its real shape.
        glyph_set = self.font.getGlyphSet()
        for ch in "中好資한":
            name = self.cmap[ord(ch)]
            pen = BoundsPen(glyph_set)
            glyph_set[name].draw(pen)
            xmin, _, _, _ = pen.bounds
            self.assertEqual(
                xmin, self.hmtx[name][1], msg=f"{ch}: hmtx LSB doesn't match actual ink xMin"
            )
            # A real CJK glyph should never be flush against x=0 -- every
            # source glyph in this test set has natural side-bearing.
            self.assertGreater(xmin, 0, msg=f"{ch}: unexpectedly flush against left cell edge")

    def test_no_codepoint_added_outside_the_filter(self):
        # ord('A') (Latin) must still resolve to JetBrains' own glyph, not
        # something this overlay step touched.
        self.assertNotIn(ord("A"), {ord(c) for c in TEST_CHARS})
        self.assertEqual(self.cmap[ord("A")], "A")


class OverlayCjkItalicTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upright = _build_test_font(italic_angle=0.0)
        cls.italic = _build_test_font(italic_angle=9.0)

    def test_italic_shear_changes_glyph_shape(self):
        upright_cmap = self.upright.getBestCmap()
        italic_cmap = self.italic.getBestCmap()
        name_upright = upright_cmap[ord("中")]
        name_italic = italic_cmap[ord("中")]

        upright_pen = BoundsPen(self.upright.getGlyphSet())
        self.upright.getGlyphSet()[name_upright].draw(upright_pen)
        italic_pen = BoundsPen(self.italic.getGlyphSet())
        self.italic.getGlyphSet()[name_italic].draw(italic_pen)

        # A shear widens the bounding box (top and bottom edges shift by
        # different amounts) without changing the advance width.
        upright_width = upright_pen.bounds[2] - upright_pen.bounds[0]
        italic_width = italic_pen.bounds[2] - italic_pen.bounds[0]
        self.assertGreater(italic_width, upright_width)

    def test_italic_advance_unchanged(self):
        upright_cmap = self.upright.getBestCmap()
        italic_cmap = self.italic.getBestCmap()
        upright_advance = self.upright["hmtx"][upright_cmap[ord("中")]][0]
        italic_advance = self.italic["hmtx"][italic_cmap[ord("中")]][0]
        self.assertEqual(upright_advance, italic_advance)


if __name__ == "__main__":
    unittest.main()
