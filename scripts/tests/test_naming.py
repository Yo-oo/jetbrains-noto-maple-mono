"""Tests for download.py's style_suffix() and rename.py's name table output."""

from __future__ import annotations

import unittest

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._n_a_m_e import table__n_a_m_e

from scripts.download import style_suffix
from scripts.rename import apply_family_name


def _font_with_empty_name_table() -> TTFont:
    font = TTFont()
    font["name"] = table__n_a_m_e()
    font["name"].names = []
    return font


class StyleSuffixTest(unittest.TestCase):
    def test_regular_upright_has_no_suffix(self):
        self.assertEqual(style_suffix("Regular", italic=False), "Regular")

    def test_regular_italic_is_just_italic_not_regular_italic(self):
        # This exact edge case was a real bug caught during development:
        # build.py's naming logic diverged from download.py's, producing
        # "RegularItalic.ttf" (wrong) instead of "Italic.ttf" (matching
        # every upstream's own convention).
        self.assertEqual(style_suffix("Regular", italic=True), "Italic")

    def test_other_weight_italic_gets_weight_prefix(self):
        self.assertEqual(style_suffix("Bold", italic=True), "BoldItalic")
        self.assertEqual(style_suffix("Thin", italic=True), "ThinItalic")

    def test_other_weight_upright_is_unchanged(self):
        self.assertEqual(style_suffix("ExtraBold", italic=False), "ExtraBold")


class ApplyFamilyNameTest(unittest.TestCase):
    def test_version_string_credits_all_upstreams(self):
        font = _font_with_empty_name_table()
        upstream_versions = {"JetBrains Mono": "2.304", "Noto Sans CJK": "Sans2.004", "Maple Mono": "7.9"}
        apply_family_name(font, "Regular", "0.1.0", upstream_versions)
        version_record = font["name"].getName(5, 3, 1, 0x409)
        self.assertIsNotNone(version_record)
        version_string = version_record.toUnicode()
        self.assertIn("0.1.0", version_string)
        for name, ver in upstream_versions.items():
            self.assertIn(name, version_string)
            self.assertIn(ver, version_string)

    def test_family_and_subfamily_names(self):
        font = _font_with_empty_name_table()
        apply_family_name(font, "BoldItalic", "0.1.0", {})
        self.assertEqual(font["name"].getName(1, 3, 1, 0x409).toUnicode(), "JetBrains Noto Maple Mono")
        self.assertEqual(font["name"].getName(2, 3, 1, 0x409).toUnicode(), "BoldItalic")
        self.assertEqual(
            font["name"].getName(4, 3, 1, 0x409).toUnicode(),
            "JetBrains Noto Maple Mono BoldItalic",
        )


if __name__ == "__main__":
    unittest.main()
