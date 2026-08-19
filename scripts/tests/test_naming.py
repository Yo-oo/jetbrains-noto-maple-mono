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


def _names(font: TTFont) -> dict[int, str]:
    result = {}
    for name_id in (1, 2, 4, 5, 6, 16, 17):
        record = font["name"].getName(name_id, 3, 1, 0x409)
        if record is not None:
            result[name_id] = record.toUnicode()
    return result


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
    """Matches Maple Mono's own official release name table exactly (see
    rename.py's docstring) -- verified directly against MapleMono-
    {Regular,Thin,Bold,BoldItalic,MediumItalic}.ttf during development."""

    def test_version_string_credits_all_upstreams(self):
        font = _font_with_empty_name_table()
        upstream_versions = {"JetBrains Mono": "2.304", "Noto Sans CJK": "Sans2.004", "Maple Mono": "7.9"}
        apply_family_name(font, "Test Family", "Regular", False, "0.1.0", upstream_versions)
        version_string = _names(font)[5]
        self.assertIn("0.1.0", version_string)
        for name, ver in upstream_versions.items():
            self.assertIn(name, version_string)
            self.assertIn(ver, version_string)

    def test_regular_upright(self):
        font = _font_with_empty_name_table()
        apply_family_name(font, "Test Family", "Regular", False, "0.1.0", {})
        names = _names(font)
        self.assertEqual(names[1], "Test Family")
        self.assertEqual(names[2], "Regular")
        self.assertEqual(names[4], "Test Family Regular")
        self.assertEqual(names[6], "TestFamily-Regular")
        self.assertNotIn(16, names, "RIBBI weights don't need typographic name overrides")
        self.assertNotIn(17, names)

    def test_bold_and_bold_italic_stay_ribbi(self):
        font = _font_with_empty_name_table()
        apply_family_name(font, "Test Family", "Bold", False, "0.1.0", {})
        names = _names(font)
        self.assertEqual(names[1], "Test Family")
        self.assertEqual(names[2], "Bold")
        self.assertEqual(names[4], "Test Family Bold")
        self.assertNotIn(16, names)

        font2 = _font_with_empty_name_table()
        apply_family_name(font2, "Test Family", "Bold", True, "0.1.0", {})
        names2 = _names(font2)
        self.assertEqual(names2[1], "Test Family")
        self.assertEqual(names2[2], "Bold Italic")
        self.assertEqual(names2[4], "Test Family Bold Italic")
        self.assertEqual(names2[6], "TestFamily-BoldItalic")

    def test_non_ribbi_weight_folds_into_family_name(self):
        # This is the exact bug report this test guards against: "Medium
        # Italic" must have a space (matching Maple Mono's own convention),
        # not "MediumItalic" glued together in the name table -- the
        # filename convention (no space) is a separate, deliberately
        # different thing (see style_suffix()).
        font = _font_with_empty_name_table()
        apply_family_name(font, "Test Family", "Medium", True, "0.1.0", {})
        names = _names(font)
        self.assertEqual(names[1], "Test Family Medium")
        self.assertEqual(names[2], "Italic")
        self.assertEqual(names[4], "Test Family Medium Italic")
        self.assertEqual(names[6], "TestFamily-MediumItalic")
        self.assertEqual(names[16], "Test Family")
        self.assertEqual(names[17], "Medium Italic")

    def test_non_ribbi_weight_upright_omits_redundant_regular(self):
        font = _font_with_empty_name_table()
        apply_family_name(font, "Test Family", "Thin", False, "0.1.0", {})
        names = _names(font)
        self.assertEqual(names[1], "Test Family Thin")
        self.assertEqual(names[2], "Regular")
        self.assertEqual(names[4], "Test Family Thin", "must not become 'Test Family Thin Regular'")
        self.assertEqual(names[16], "Test Family")
        self.assertEqual(names[17], "Thin")


if __name__ == "__main__":
    unittest.main()
