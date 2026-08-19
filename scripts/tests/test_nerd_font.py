"""Tests for nerd_font.py."""

from __future__ import annotations

import unittest

from fontTools.ttLib import TTFont

from scripts.download import jetbrains_mono_nerd_font_path, jetbrains_mono_path
from scripts.nerd_font import apply_nerd_font

# A handful of well-known, stable Nerd Font icon codepoints (git, apple,
# github, folder icons -- confirmed present when this was written).
KNOWN_ICON_CODEPOINTS = (0xE5FA, 0xE702, 0xF09B, 0xF113, 0xF115)


class NerdFontTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font = TTFont(str(jetbrains_mono_path("Regular")))
        cls.latin_advance = cls.font["hmtx"]["A"][0]
        cls.added = apply_nerd_font(cls.font, jetbrains_mono_nerd_font_path())

    def test_adds_a_large_number_of_icons(self):
        # The Mono symbols release ships 10000+ icons; a low count would
        # indicate the overlay silently failed for most of them.
        self.assertGreater(self.added, 5000)

    def test_known_icons_are_present_and_single_cell_width(self):
        cmap = self.font.getBestCmap()
        hmtx = self.font["hmtx"]
        for cp in KNOWN_ICON_CODEPOINTS:
            self.assertIn(cp, cmap, msg=f"missing icon U+{cp:04X}")
            name = cmap[cp]
            self.assertEqual(
                hmtx[name][0],
                self.latin_advance,
                msg=f"U+{cp:04X} should be single-cell width, not double like CJK",
            )

    def test_does_not_overwrite_existing_latin_codepoints(self):
        cmap = self.font.getBestCmap()
        self.assertEqual(cmap[ord("A")], "A")


if __name__ == "__main__":
    unittest.main()
