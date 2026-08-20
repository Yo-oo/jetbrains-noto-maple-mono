"""Rewrite a font's name table to this project's own identity.

Only touches Windows (platform 3) name records -- fonttools/most tools read
those; the legacy Mac (platform 1) records JetBrains ships aren't consumed
by anything relevant here and are left untouched.

Follows the same RIBBI convention Maple Mono's own official release uses
(verified by inspecting MapleMono-{Regular,Thin,Bold,BoldItalic,
MediumItalic}.ttf directly): legacy OpenType software only recognizes 4
values in nameID 2 (Regular/Italic/Bold/Bold Italic) to select a style
within one family. Any OTHER weight (Thin, ExtraLight, Light, Medium,
SemiBold, ExtraBold) has to fold the weight into nameID 1 instead (e.g.
family "Maple Mono Medium", subfamily "Italic") for legacy software to be
able to select it at all -- nameID 16/17 (typographic family/subfamily)
then separately carry the "real", unfolded family + full weight name
("Maple Mono" / "Medium Italic") for modern software that reads those in
preference to 1/2. Getting this wrong doesn't just look wrong: some
software can't select non-RIBBI weights at all if nameID 2 holds anything
other than the 4 legal values.
"""

from __future__ import annotations

from fontTools.ttLib import TTFont

from scripts.download import style_suffix

RIBBI_WEIGHTS = ("Regular", "Bold")


def apply_family_name(
    font: TTFont,
    family_name: str,
    weight: str,
    italic: bool,
    project_version: str,
    upstream_versions: dict[str, str],
) -> None:
    """Set name table records. upstream_versions e.g. {"JetBrains Mono": "2.304", ...}."""
    is_ribbi = weight in RIBBI_WEIGHTS

    if is_ribbi:
        legacy_family = family_name
        if weight == "Bold":
            legacy_subfamily = "Bold Italic" if italic else "Bold"
        else:
            legacy_subfamily = "Italic" if italic else "Regular"
    else:
        legacy_family = f"{family_name} {weight}"
        legacy_subfamily = "Italic" if italic else "Regular"

    # The base Regular master always spells out "{Family} Regular" in the
    # full name by convention (matches Maple Mono's own MapleMono-Regular.ttf
    # and is near-universal -- e.g. "Roboto Regular"), but every OTHER
    # upright non-RIBBI weight omits the redundant "Regular" suffix (Maple's
    # own MapleMono-Thin.ttf's full name is just "Maple Mono Thin", not
    # "Maple Mono Thin Regular").
    if legacy_subfamily == "Regular" and not is_ribbi:
        full_name = legacy_family
    else:
        full_name = f"{legacy_family} {legacy_subfamily}"

    postscript_name = f"{family_name.replace(' ', '')}-{style_suffix(weight, italic)}"

    credits = "; ".join(f"{name} {ver}" for name, ver in upstream_versions.items())
    version_string = f"Version {project_version} ({credits})"

    values = {
        1: legacy_family,
        2: legacy_subfamily,
        3: f"{project_version};{postscript_name}",
        4: full_name,
        5: version_string,
        6: postscript_name,
    }
    if not is_ribbi:
        typographic_subfamily = weight + (" Italic" if italic else "")
        values[16] = family_name
        values[17] = typographic_subfamily

    name_table = font["name"]
    for name_id, value in values.items():
        name_table.setName(value, name_id, 3, 1, 0x409)
