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

Trigger case: matches Maple's own default calt behavior -- exact uppercase
only (`[INFO]`, not `[info]`/`[Info]`), confirmed via hb-shape against the
official release with no extra features enabled. Case-insensitive matching
is a separate opt-in stylistic set in Maple (ss03) this project doesn't
graft in v1.
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


def _build_fea(tags: list[tuple[str, str]]) -> str:
    # Longest-word-first: a shorter tag sharing a letter prefix with a longer
    # one must not get first chance at the shared glyphs (mirrors
    # overlay_ligatures.py's ordering rationale in the old maple-font fork).
    tags = sorted(tags, key=lambda item: -len(item[1]))
    lines = []
    lookup_names: list[str] = []
    for liga_name, word in tags:
        letters = [letter.upper() for letter in word]
        sequence = ["bracketleft", *letters, "bracketright"]
        n = len(sequence)
        base_id = liga_name.replace(".", "_")
        for i in range(n):
            lk_name = f"tag_{base_id}_{i}"
            lookup_names.append(lk_name)
            backtrack = " ".join(["SPC"] * i)
            lookahead = " ".join(sequence[i + 1 :])
            marked = f"{sequence[i]}'"
            output = "SPC" if i < n - 1 else liga_name
            parts = [p for p in (backtrack, marked, lookahead) if p]
            lines.append(f"lookup {lk_name} {{")
            lines.append(f"    sub {' '.join(parts)} by {output};")
            lines.append(f"}} {lk_name};")
    fea = "\n".join(lines)
    fea += "\nfeature calt {\n"
    for lk_name in lookup_names:
        fea += f"    lookup {lk_name};\n"
    fea += "} calt;\n"
    return fea


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
    fea = _build_fea(tags)
    addOpenTypeFeatures(scratch, io.StringIO(fea))

    scratch_gsub = scratch["GSUB"].table
    scratch_lookups = scratch_gsub.LookupList.Lookup
    scratch_calt_indices = None
    for fr in scratch_gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "calt":
            scratch_calt_indices = list(fr.Feature.LookupListIndex)
            break
    if scratch_calt_indices is None:
        raise RuntimeError("scratch compile produced no calt feature")

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

    base_calt_fr = None
    for fr in base_gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "calt":
            base_calt_fr = fr
            break
    if base_calt_fr is None:
        raise RuntimeError("base font has no calt feature to extend")
    base_calt_fr.Feature.LookupListIndex = list(scratch_calt_indices) + list(
        base_calt_fr.Feature.LookupListIndex
    )
    base_calt_fr.Feature.LookupCount = len(base_calt_fr.Feature.LookupListIndex)

    return len(tags)
