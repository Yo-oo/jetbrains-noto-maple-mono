"""Tests for tag_badges.py."""

from __future__ import annotations

import unittest

from fontTools.ttLib import TTFont

from scripts.download import jetbrains_mono_path
from scripts.tag_badges import (
    _display_text,
    build_badge_glyph,
    check_tag_boundaries,
    resolve_corner_radius,
)


class DisplayTextTest(unittest.TestCase):
    def test_strips_brackets(self):
        self.assertEqual(_display_text("[INFO]"), "INFO")

    def test_strips_symmetric_colons(self):
        self.assertEqual(_display_text("::FIX::"), "FIX")

    def test_strips_trailing_only(self):
        self.assertEqual(_display_text("FIXME:"), "FIXME")

    def test_no_delimiters_is_unchanged(self):
        self.assertEqual(_display_text("TODO"), "TODO")


class ResolveCornerRadiusTest(unittest.TestCase):
    def test_pill_is_half_the_cell_height(self):
        self.assertEqual(resolve_corner_radius("pill", 1020, -300), 660)

    def test_number_passes_through(self):
        self.assertEqual(resolve_corner_radius(150, 1020, -300), 150.0)

    def test_zero_is_square(self):
        self.assertEqual(resolve_corner_radius(0, 1020, -300), 0.0)

    def test_null_raises_with_a_pointer_to_tags_list(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_corner_radius(None, 1020, -300)
        self.assertIn("tags.list", str(ctx.exception))


class CheckTagBoundariesTest(unittest.TestCase):
    def test_bracket_style_tag_has_no_warning(self):
        self.assertEqual(check_tag_boundaries(["[INFO]"]), [])

    def test_symmetric_colon_tag_has_no_warning(self):
        self.assertEqual(check_tag_boundaries(["::FIX::"]), [])

    def test_bare_word_with_trailing_colon_warns(self):
        warnings = check_tag_boundaries(["FIXME:"])
        self.assertEqual(len(warnings), 1)
        self.assertIn("FIXME:", warnings[0])

    def test_multiple_tags_each_checked_independently(self):
        warnings = check_tag_boundaries(["[INFO]", "FIXME:", "::FIX::"])
        self.assertEqual(len(warnings), 1)


class BuildBadgeGlyphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.letter_font = TTFont(str(jetbrains_mono_path("Bold")))

    def test_advance_is_a_single_column(self):
        # This glyph only ever sits at the LAST position of a matched
        # sequence -- every earlier position keeps its own SPC placeholder
        # advance, so this glyph's own advance must stay one column (600),
        # not the full multi-column badge width. Regression: an earlier
        # draft returned the full width here, double-counting it on top of
        # the preceding SPC advances and pushing everything after the badge
        # to the right by (len(text) - 1) * 600.
        _glyph, advance = build_badge_glyph("[INFO]", self.letter_font, "pill")
        self.assertEqual(advance, 600)

    def test_artwork_reaches_back_to_cover_every_column(self):
        # The badge glyph is placed at the last position, so its artwork
        # must extend backward (negative xMin) to cover all len(text)
        # columns, while staying flush with this glyph's own column on the
        # right (xMax == 600).
        glyph, _advance = build_badge_glyph("[INFO]", self.letter_font, "pill")
        width = len("[INFO]") * 600
        xs = [x for x, _y in glyph.coordinates]
        self.assertEqual(max(xs), 600)
        self.assertEqual(min(xs), 600 - width)

    def test_produces_a_hole_not_a_solid_shape(self):
        # Regression: an earlier draft added a spurious contour-reversal
        # that canceled the pre-existing opposite winding back out,
        # producing a solid badge with no visible letter cutout.
        glyph, _advance = build_badge_glyph("[INFO]", self.letter_font, "pill")
        self.assertGreater(glyph.numberOfContours, 1)

    def test_square_corners_when_radius_is_zero(self):
        glyph, _advance = build_badge_glyph("[INFO]", self.letter_font, 0)
        self.assertGreater(glyph.numberOfContours, 1)

    def test_missing_letter_raises(self):
        with self.assertRaises(ValueError):
            build_badge_glyph("[中]", self.letter_font, "pill")


if __name__ == "__main__":
    unittest.main()
