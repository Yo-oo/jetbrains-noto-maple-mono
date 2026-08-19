"""Graft Maple Mono's plain-text tag ligatures (`[INFO]`, `[WARN]`, ...) onto a base font.

Two separate things get combined here, sourced differently on purpose:

1. Badge ARTWORK -- the actual drawn rounded-badge outlines (glyphs named
   `tag_info.liga`, `tag_warn.liga`, etc. in Maple Mono's official release)
   are hand-designed and can only be reused by copying them, the same way
   overlay_latin.py copied JetBrains' own Latin outlines in the old
   maple-font fork. The exact set of available tags is read from Maple's
   release at run time (regex over its glyph order), not from a hardcoded
   word list, so this stays correct if Maple adds/removes tags upstream.

2. Substitution RULES (which bracketed word triggers which badge) are
   reimplemented fresh here via feaLib, not ported from Maple's own compiled
   GSUB -- Maple's existing calt lookups aren't self-contained (chain-context
   records reference other, unrelated lookups by global index), so
   transplanting them risks dragging in unrelated behavior. Verified via
   hb-shape against Maple's actual release that its mechanism for e.g.
   "[INFO]" is: replace all glyphs except the last with a shared zero-width
   placeholder (`SPC`), and let the LAST glyph (here, the closing bracket's
   position) carry the full "[INFO]" badge artwork via a large negative
   left side bearing, so it visually draws backward over the now-invisible
   earlier cells while each of the 6 positions still occupies its own
   600-unit column (required for monospace grid/cursor alignment -- a true
   GSUB ligature substitution would instead collapse 6 glyphs into 1,
   breaking column alignment).

No scale/shift transform is needed: Maple Mono's metrics are an exact match
for JetBrains Mono's (unitsPerEm=1000, Latin advance=600, hhea ascent/descent
1020/-300), confirmed by inspection -- these are Maple's own numbers, not
independently chosen, since Maple was originally designed to line up with
JetBrains Mono.

Trigger case: `calt` matches Maple's own default behavior -- exact
uppercase only (`[INFO]`, not `[info]`/`[Info]`), confirmed via hb-shape
against the official release with no extra features enabled. A second,
separate opt-in `ss03` feature (matching Maple's own use of that same tag
for the same purpose -- confirmed JetBrains Mono doesn't use ss03 for
anything of its own, so there's no collision) additionally matches any
letter case per position (`[info]`, `[Info]`, `[INFO]`, ...), same artwork,
same mechanism, just per-letter `[X x]` classes instead of literal
uppercase glyphs.
"""

from __future__ import annotations

import copy
import io
import re
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeatures
from fontTools.ttLib import TTFont

TAG_GLYPH_RE = re.compile(r"^tag_(\w+)\.liga$")


def _discover_tags(maple_font: TTFont) -> list[tuple[str, str]]:
    """Return [(glyph_name, word)] for every tag badge in Maple's release."""
    tags = []
    for name in maple_font.getGlyphOrder():
        match = TAG_GLYPH_RE.match(name)
        if match:
            tags.append((name, match.group(1)))
    return tags


def _tag_lookups(tags: list[tuple[str, str]], prefix: str, case_insensitive: bool) -> tuple[list[str], list[str]]:
    """Return (fea_lines, lookup_names) for one feature's worth of tag rules.

    case_insensitive=False emits literal uppercase-letter sequences (calt);
    True emits [Xx]-style two-glyph classes per letter (ss03).
    """
    # Longest-word-first: a shorter tag sharing a letter prefix with a longer
    # one must not get first chance at the shared glyphs (mirrors
    # overlay_ligatures.py's ordering rationale in the old maple-font fork).
    tags = sorted(tags, key=lambda item: -len(item[1]))
    lines = []
    lookup_names: list[str] = []
    for liga_name, word in tags:
        if case_insensitive:
            letters = [f"[{letter.upper()} {letter.lower()}]" for letter in word]
        else:
            letters = [letter.upper() for letter in word]
        sequence = ["bracketleft", *letters, "bracketright"]
        n = len(sequence)
        base_id = liga_name.replace(".", "_")
        for i in range(n):
            lk_name = f"{prefix}_{base_id}_{i}"
            lookup_names.append(lk_name)
            backtrack = " ".join(["SPC"] * i)
            lookahead = " ".join(sequence[i + 1 :])
            marked = f"{sequence[i]}'"
            output = "SPC" if i < n - 1 else liga_name
            parts = [p for p in (backtrack, marked, lookahead) if p]
            lines.append(f"lookup {lk_name} {{")
            lines.append(f"    sub {' '.join(parts)} by {output};")
            lines.append(f"}} {lk_name};")
    return lines, lookup_names


def _build_fea(tags: list[tuple[str, str]]) -> tuple[str, list[str], list[str]]:
    """Return (fea_source, calt_lookup_names, ss03_lookup_names)."""
    calt_lines, calt_names = _tag_lookups(tags, "tagc", case_insensitive=False)
    ss03_lines, ss03_names = _tag_lookups(tags, "tags", case_insensitive=True)

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


def apply_tag_ligatures(base: TTFont, maple_path: Path) -> int:
    """Mutate base in place, adding Maple's tag badges + fresh calt rules.

    Returns the number of tag words grafted.
    """
    maple_font = TTFont(str(maple_path))
    tags = _discover_tags(maple_font)
    if not tags:
        raise RuntimeError(f"no tag_*.liga glyphs found in {maple_path}")

    base_upm = base["head"].unitsPerEm
    maple_upm = maple_font["head"].unitsPerEm
    if base_upm != maple_upm:
        raise ValueError(f"unitsPerEm mismatch: base={base_upm} maple={maple_upm}")

    # Step 1: copy artwork (SPC + all tag_*.liga outlines), no transform.
    maple_glyf = maple_font["glyf"]
    maple_hmtx = maple_font["hmtx"]
    base_glyf = base["glyf"]
    base_hmtx = base["hmtx"]
    new_names = ["SPC"] + [name for name, _ in tags]
    glyph_order = list(base.getGlyphOrder())
    for name in new_names:
        base_glyf[name] = copy.deepcopy(maple_glyf[name])
        base_hmtx[name] = maple_hmtx[name]
        if name not in glyph_order:
            glyph_order.append(name)
    base_glyf.setGlyphOrder(glyph_order)
    base.setGlyphOrder(glyph_order)
    base["maxp"].numGlyphs = len(glyph_order)

    # Step 2: compile fresh rules in an isolated scratch copy (feaLib's
    # addOpenTypeFeatures replaces GSUB wholesale), then transplant.
    scratch = copy.deepcopy(base)
    fea, _calt_names, _ss03_names = _build_fea(tags)
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
    # lookups must get LOWER indices than everything already in the base
    # (which already ships its own calt/aalt/etc., 460 lookups) to run
    # first. Insert at the front, shift every existing reference up by the
    # inserted count (every FeatureRecord's LookupListIndex, and every
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

    base_calt_index = None
    base_calt_fr = None
    for index, fr in enumerate(base_gsub.FeatureList.FeatureRecord):
        if fr.FeatureTag == "calt":
            base_calt_index = index
            base_calt_fr = fr
            break
    if base_calt_fr is None:
        raise RuntimeError("base font has no calt feature to extend")
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
