"""Rewrite a font's name table to this project's own identity.

Only touches Windows (platform 3) name records -- fonttools/most tools read
those; the legacy Mac (platform 1) records JetBrains ships aren't consumed
by anything relevant here and are left untouched.
"""

from __future__ import annotations

from fontTools.ttLib import TTFont

FAMILY_NAME = "JetBrains Noto Maple Mono"


def apply_family_name(font: TTFont, weight: str, version: str) -> None:
    subfamily = weight
    full_name = f"{FAMILY_NAME} {subfamily}"
    postscript_name = f"{FAMILY_NAME.replace(' ', '')}-{subfamily.replace(' ', '')}"

    values = {
        1: FAMILY_NAME,
        2: subfamily,
        3: f"{version};{postscript_name}",
        4: full_name,
        5: f"Version {version}",
        6: postscript_name,
        16: FAMILY_NAME,
        17: subfamily,
    }
    name_table = font["name"]
    for name_id, value in values.items():
        name_table.setName(value, name_id, 3, 1, 0x409)
