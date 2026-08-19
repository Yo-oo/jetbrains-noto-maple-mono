"""Rewrite a font's name table to this project's own identity.

Only touches Windows (platform 3) name records -- fonttools/most tools read
those; the legacy Mac (platform 1) records JetBrains ships aren't consumed
by anything relevant here and are left untouched.
"""

from __future__ import annotations

from fontTools.ttLib import TTFont


def apply_family_name(
    font: TTFont,
    family_name: str,
    weight: str,
    project_version: str,
    upstream_versions: dict[str, str],
) -> None:
    """Set name table records. upstream_versions e.g. {"JetBrains Mono": "2.304", ...}."""
    subfamily = weight
    full_name = f"{family_name} {subfamily}"
    postscript_name = f"{family_name.replace(' ', '')}-{subfamily.replace(' ', '')}"
    credits = "; ".join(f"{name} {ver}" for name, ver in upstream_versions.items())
    version_string = f"Version {project_version} ({credits})"

    values = {
        1: family_name,
        2: subfamily,
        3: f"{project_version};{postscript_name}",
        4: full_name,
        5: version_string,
        6: postscript_name,
        16: family_name,
        17: subfamily,
    }
    name_table = font["name"]
    for name_id, value in values.items():
        name_table.setName(value, name_id, 3, 1, 0x409)
