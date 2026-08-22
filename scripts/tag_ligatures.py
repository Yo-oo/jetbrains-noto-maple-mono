"""Wire plain-text tag ligatures (`[INFO]`, `[WARN]`, ...) into a base font.

Two separate things, still sourced/handled differently on purpose:

1. Badge ARTWORK -- generated fresh by tag_badges.py (rounded rect + the
   trigger text cut through it using a caller-supplied letter font's own
   outlines), not copied from Maple Mono's release. See that module's
   docstring. This module only calls it and places the result.

2. Substitution RULES (which trigger text activates which badge) are
   implemented here via feaLib. Mechanism (verified via hb-shape against
   Maple Mono's actual release, which uses the same trick): replace all
   glyphs except the last with a shared blank placeholder (`SPC`, empty
   outline but a normal 600-unit advance -- NOT zero-width, or the column
   grid would desync), and let the LAST glyph carry the full badge artwork
   via a large negative left side bearing, so it visually draws backward
   over the now-blank earlier cells while every position still occupies its
   own column (required for monospace grid/cursor alignment -- a true GSUB
   ligature substitution would instead collapse N glyphs into 1, breaking
   column alignment).

Trigger case: `calt` matches exact-case only (e.g. "[INFO]", not "[info]").
A second, separate opt-in `ss03` feature (JetBrains Mono doesn't use that
tag for anything of its own, so there's no collision) additionally matches
any letter case per position ("[info]", "[Info]", "[INFO]", ...) -- same
artwork, same mechanism, just per-letter case-insensitive glyph classes for
alphabetic characters (non-letter characters in a tag, e.g. ":" or "[",
have no case and match literally in both features).
"""

from __future__ import annotations

import copy
import io

from fontTools.feaLib.builder import addOpenTypeFeatures
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph

from scripts.tag_badges import build_badge_glyph


def _glyph_name_for_char(font: TTFont, ch: str) -> str:
    cmap = font.getBestCmap()
    cp = ord(ch)
    if cp not in cmap:
        raise ValueError(f"base font has no glyph for {ch!r}")
    return cmap[cp]


def _badge_glyph_name(index: int) -> str:
    return f"tag_badge.{index}"


def _tag_lookups(
    base: TTFont, tags: list[str], prefix: str, case_insensitive: bool
) -> tuple[list[str], list[str]]:
    """Return (fea_lines, lookup_names) for one feature's worth of tag rules.

    case_insensitive=False emits literal glyph sequences (calt); True emits
    [Xx]-style two-glyph classes for each alphabetic character (ss03),
    non-alphabetic characters matching literally either way.
    """
    # Longest-text-first: a shorter tag sharing a prefix with a longer one
    # must not get first chance at the shared glyphs.
    ordered = sorted(range(len(tags)), key=lambda i: -len(tags[i]))
    lines = []
    lookup_names: list[str] = []
    for tag_index in ordered:
        text = tags[tag_index]
        badge_name = _badge_glyph_name(tag_index)
        if case_insensitive:
            sequence = []
            for ch in text:
                if ch.isalpha():
                    upper_name = _glyph_name_for_char(base, ch.upper())
                    lower_name = _glyph_name_for_char(base, ch.lower())
                    sequence.append(f"[{upper_name} {lower_name}]")
                else:
                    sequence.append(_glyph_name_for_char(base, ch))
        else:
            sequence = [_glyph_name_for_char(base, ch) for ch in text]

        n = len(sequence)
        for i in range(n):
            lk_name = f"{prefix}_{tag_index}_{i}"
            lookup_names.append(lk_name)
            backtrack = " ".join(["SPC"] * i)
            lookahead = " ".join(sequence[i + 1 :])
            marked = f"{sequence[i]}'"
            output = "SPC" if i < n - 1 else badge_name
            parts = [p for p in (backtrack, marked, lookahead) if p]
            lines.append(f"lookup {lk_name} {{")
            lines.append(f"    sub {' '.join(parts)} by {output};")
            lines.append(f"}} {lk_name};")
    return lines, lookup_names


def _build_fea(base: TTFont, tags: list[str]) -> tuple[str, list[str], list[str]]:
    """Return (fea_source, calt_lookup_names, ss03_lookup_names)."""
    calt_lines, calt_names = _tag_lookups(base, tags, "tagc", case_insensitive=False)
    ss03_lines, ss03_names = _tag_lookups(base, tags, "tags", case_insensitive=True)

    fea = "\n".join(calt_lines) + "\n" + "\n".join(ss03_lines)
    fea += "\nfeature calt {\n"
    for lk_name in calt_names:
        fea += f"    lookup {lk_name};\n"
    fea += "} calt;\n"
    fea += "\nfeature ss03 {\n"
    for lk_name in ss03_names:
        fea += f"    lookup {lk_name};\n"
    fea += "} ss03;\n"
    return fea, calt_names, ss03_names


def _shift_records(container, offset: int) -> None:
    records = getattr(container, "SubstLookupRecord", None)
    if records:
        for record in records:
            record.LookupListIndex += offset


def _shift_lookup_refs(lookup, offset: int) -> None:
    for subtable in getattr(lookup, "SubTable", []):
        format_ = getattr(subtable, "Format", None)
        if format_ == 1:
            for rule_set in getattr(subtable, "ChainSubRuleSet", []) or []:
                if rule_set is None:
                    continue
                for rule in getattr(rule_set, "ChainSubRule", []):
                    _shift_records(rule, offset)
        elif format_ == 2:
            for class_set in getattr(subtable, "ChainSubClassSet", []) or []:
                if class_set is None:
                    continue
                for rule in getattr(class_set, "ChainSubClassRule", []):
                    _shift_records(rule, offset)
        else:
            _shift_records(subtable, offset)


def apply_tag_ligatures(
    base: TTFont,
    tags: list[str],
    letter_font: TTFont,
    corner_radius: str | float,
) -> int:
    """Mutate base in place, adding generated tag badges + fresh calt/ss03 rules.

    Returns the number of tags wired.
    """
    if not tags:
        raise ValueError("no tags to wire")

    # Step 1: generate badge artwork + a blank placeholder, add as new glyphs.
    base_glyf = base["glyf"]
    base_hmtx = base["hmtx"]
    glyph_order = list(base.getGlyphOrder())

    if "SPC" not in glyph_order:
        base_glyf["SPC"] = Glyph()
        base_hmtx["SPC"] = (600, 0)
        glyph_order.append("SPC")

    for index, text in enumerate(tags):
        badge_name = _badge_glyph_name(index)
        glyph, advance = build_badge_glyph(text, letter_font, corner_radius)
        base_glyf[badge_name] = glyph
        base_hmtx[badge_name] = (advance, 0)
        if badge_name not in glyph_order:
            glyph_order.append(badge_name)

    base_glyf.setGlyphOrder(glyph_order)
    base.setGlyphOrder(glyph_order)
    base["maxp"].numGlyphs = len(glyph_order)

    # Step 2: compile fresh rules in an isolated scratch copy (feaLib's
    # addOpenTypeFeatures replaces GSUB wholesale), then transplant.
    scratch = copy.deepcopy(base)
    fea, _calt_names, _ss03_names = _build_fea(base, tags)
    addOpenTypeFeatures(scratch, io.StringIO(fea))

    scratch_gsub = scratch["GSUB"].table
    scratch_lookups = scratch_gsub.LookupList.Lookup
    scratch_calt_indices = None
    scratch_ss03_fr = None
    for fr in scratch_gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "calt":
            scratch_calt_indices = list(fr.Feature.LookupListIndex)
        elif fr.FeatureTag == "ss03":
            scratch_ss03_fr = fr
    if scratch_calt_indices is None:
        raise RuntimeError("scratch compile produced no calt feature")
    if scratch_ss03_fr is None:
        raise RuntimeError("scratch compile produced no ss03 feature")

    # HarfBuzz applies GSUB lookups in ascending GLOBAL LookupList index
    # order, not a feature's own LookupListIndex array order -- so these new
    # lookups must get LOWER indices than everything already in the base to
    # run first. Insert at the front, shift every existing reference up by
    # the inserted count (every FeatureRecord's LookupListIndex, and every
    # lookup's own internal chain-context SubstLookupRecord references).
    base_gsub = base["GSUB"].table
    new_count = len(scratch_lookups)

    for lookup in base_gsub.LookupList.Lookup:
        _shift_lookup_refs(lookup, new_count)
    shifted_existing = base_gsub.LookupList.Lookup
    base_gsub.LookupList.Lookup = [copy.deepcopy(lk) for lk in scratch_lookups] + shifted_existing
    base_gsub.LookupList.LookupCount = len(base_gsub.LookupList.Lookup)

    for fr in base_gsub.FeatureList.FeatureRecord:
        fr.Feature.LookupListIndex = [i + new_count for i in fr.Feature.LookupListIndex]
        fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)

    base_calt_fr = None
    for fr in base_gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "calt":
            base_calt_fr = fr
            break
    if base_calt_fr is None:
        raise RuntimeError("base font has no calt feature to extend")
    base_calt_index = base_gsub.FeatureList.FeatureRecord.index(base_calt_fr)
    base_calt_fr.Feature.LookupListIndex = list(scratch_calt_indices) + list(
        base_calt_fr.Feature.LookupListIndex
    )
    base_calt_fr.Feature.LookupCount = len(base_calt_fr.Feature.LookupListIndex)

    # ss03: base has no existing ss03 feature (confirmed JetBrains Mono
    # doesn't use that tag for anything), so append a brand new
    # FeatureRecord rather than merge -- its lookup indices are already
    # correct as-is, since scratch's own lookups occupy the same front
    # block of base's LookupList (0-based, no shift needed). A new
    # FeatureRecord alone isn't reachable by any shaper until it's also
    # registered in every ScriptList/LangSys that already offers calt --
    # otherwise it compiles fine but silently never fires.
    new_ss03_fr = copy.deepcopy(scratch_ss03_fr)
    base_gsub.FeatureList.FeatureRecord.append(new_ss03_fr)
    ss03_index = len(base_gsub.FeatureList.FeatureRecord) - 1
    base_gsub.FeatureList.FeatureCount = len(base_gsub.FeatureList.FeatureRecord)

    for script_record in base_gsub.ScriptList.ScriptRecord:
        script = script_record.Script
        lang_systems = [script.DefaultLangSys] if script.DefaultLangSys else []
        lang_systems += [lsr.LangSys for lsr in script.LangSysRecord]
        for lang_sys in lang_systems:
            if base_calt_index in lang_sys.FeatureIndex:
                lang_sys.FeatureIndex.append(ss03_index)
                lang_sys.FeatureCount = len(lang_sys.FeatureIndex)

    return len(tags)
