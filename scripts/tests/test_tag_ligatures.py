"""Tests for tag_ligatures.py.

Verifies structurally via fontTools' own GSUB inspection rather than
shelling out to hb-shape -- keeps this runnable in CI without needing the
harfbuzz command-line tool installed, and is exactly what hb-shape's own
behavior is derived from (the actual lookup graph).
"""

from __future__ import annotations

import unittest

from fontTools.ttLib import TTFont

from scripts.download import jetbrains_mono_path, maple_mono_path
from scripts.tag_ligatures import apply_tag_ligatures


class TagLigaturesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font = TTFont(str(jetbrains_mono_path("Regular")))
        cls.tag_count = apply_tag_ligatures(cls.font, maple_mono_path("Regular"))

    def test_grafts_at_least_maples_known_tags(self):
        # Exact count depends on Maple's release (discovered dynamically,
        # not hardcoded -- see tag_ligatures.py's docstring), but these
        # specific ones have existed across many Maple releases.
        self.assertGreaterEqual(self.tag_count, 10)

    def test_badge_glyphs_and_placeholder_were_copied(self):
        names = set(self.font.getGlyphOrder())
        self.assertIn("SPC", names)
        self.assertIn("tag_info.liga", names)
        self.assertIn("tag_warn.liga", names)
        self.assertIn("tag_error.liga", names)

    def test_calt_feature_extended_not_replaced(self):
        gsub = self.font["GSUB"].table
        calt_frs = [fr for fr in gsub.FeatureList.FeatureRecord if fr.FeatureTag == "calt"]
        self.assertEqual(len(calt_frs), 1, "must extend the existing calt, not add a duplicate")

    def test_ss03_feature_was_added(self):
        gsub = self.font["GSUB"].table
        ss03_frs = [fr for fr in gsub.FeatureList.FeatureRecord if fr.FeatureTag == "ss03"]
        self.assertEqual(len(ss03_frs), 1)

    def test_ss03_is_reachable_from_every_script_that_offers_calt(self):
        # A FeatureRecord that exists but isn't wired into ScriptList/LangSys
        # compiles fine and silently never fires -- this is the exact bug
        # class apply_tag_ligatures() has to avoid when adding a brand new
        # feature tag.
        gsub = self.font["GSUB"].table
        calt_index = next(
            i for i, fr in enumerate(gsub.FeatureList.FeatureRecord) if fr.FeatureTag == "calt"
        )
        ss03_index = next(
            i for i, fr in enumerate(gsub.FeatureList.FeatureRecord) if fr.FeatureTag == "ss03"
        )
        for script_record in gsub.ScriptList.ScriptRecord:
            script = script_record.Script
            lang_systems = [script.DefaultLangSys] if script.DefaultLangSys else []
            lang_systems += [lsr.LangSys for lsr in script.LangSysRecord]
            for lang_sys in lang_systems:
                if calt_index in lang_sys.FeatureIndex:
                    self.assertIn(
                        ss03_index,
                        lang_sys.FeatureIndex,
                        msg="ss03 missing from a LangSys that offers calt",
                    )

    def test_native_jetbrains_features_untouched(self):
        # This project's whole premise is JetBrains-Mono-as-base: adding
        # tags must never disturb JetBrains' own existing feature set.
        fresh = TTFont(str(jetbrains_mono_path("Regular")))
        original_tags = {fr.FeatureTag for fr in fresh["GSUB"].table.FeatureList.FeatureRecord}
        result_tags = {fr.FeatureTag for fr in self.font["GSUB"].table.FeatureList.FeatureRecord}
        missing = original_tags - result_tags
        self.assertEqual(missing, set(), "grafting tags must not remove any native feature")


if __name__ == "__main__":
    unittest.main()
