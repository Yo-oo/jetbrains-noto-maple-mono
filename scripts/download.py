"""Fetch and cache the three upstream releases this project layers together.

Every function downloads once and reuses the cached file on later runs
(cache lives under dist/upstream/, which .gitignore excludes). Version
pins live in config.json (single source of truth, also read by
check_upstream_versions.py) -- re-running the pipeline against a newer
upstream version is just bumping the relevant version there, no vendored/
forked upstream code to keep in sync.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from urllib.request import urlopen

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from scripts.common import UPSTREAM_DIR, save_font_atomic
from scripts.config import load_config

_upstream_versions = load_config()["upstream_versions"]

# Every *_path()/*_VERSION function below takes an optional version override
# (build.py wires these to --jetbrains-mono-version etc., in turn wired to
# build.yml's workflow_dispatch inputs) -- config.json's pins are still the
# DEFAULT, and release.yml never passes an override, so a real release only
# ever uses what's pinned and reviewed in config.json. Overrides exist for
# ad-hoc build.yml runs (write-access collaborators only, artifact-only
# output, no Release created -- see conversation), not for loosening what
# ships publicly.
JETBRAINS_MONO_VERSION = _upstream_versions["jetbrains_mono"]

# Noto Sans CJK (the regular, non-"Mono" release): despite the family being
# "proportional", its CJK Han/Hangul/Kana glyphs still use the exact same
# fixed-fullwidth convention as the dedicated Mono release (verified: Han
# advance=1000, Hangul=920, identical at every weight from 100-900) --
# proportionality in this family only affects Latin/punctuation, never CJK
# ideograph-class scripts. Using this instead of the Mono release (which
# only ships Regular/Bold, no variable version with a usable weight range)
# gets the full wght 100-900 axis for free, with zero change needed to
# overlay_cjk.py's per-glyph native-advance scaling.
NOTO_CJK_RELEASE_TAG = _upstream_versions["noto_cjk_release_tag"]
NOTO_CJK_VF_ASSET = "02_NotoSansCJK-TTF-VF.zip"
NOTO_CJK_VF_MEMBERS = {
    "jp": "Variable/TTF/NotoSansCJKjp-VF.ttf",
    "kr": "Variable/TTF/NotoSansCJKkr-VF.ttf",
    "tc": "Variable/TTF/NotoSansCJKtc-VF.ttf",
    "sc": "Variable/TTF/NotoSansCJKsc-VF.ttf",
    "hk": "Variable/TTF/NotoSansCJKhk-VF.ttf",
}

MAPLE_MONO_VERSION = _upstream_versions["maple_mono"]
MAPLE_MONO_ASSET = "MapleMono-TTF.zip"

WEIGHTS = ("Thin", "ExtraLight", "Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold")
WEIGHT_VALUES = {
    "Thin": 100,
    "ExtraLight": 200,
    "Light": 300,
    "Regular": 400,
    "Medium": 500,
    "SemiBold": 600,
    "Bold": 700,
    "ExtraBold": 800,
}


def _cached_zip(url: str) -> Path:
    """Download url once, cache the whole zip -- callers extract members from it.

    Avoids re-downloading the same multi-locale/multi-weight archive once
    per member (e.g. 16 weight x style combos would otherwise mean 16 full
    downloads of the same JetBrains Mono zip).
    """
    cache_dir = UPSTREAM_DIR / "_zips"
    cache_dir.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha1(url.encode()).hexdigest()[:16] + ".zip"
    zip_path = cache_dir / name
    if not zip_path.exists():
        with urlopen(url) as response:
            zip_path.write_bytes(response.read())
    return zip_path


def _extract_member(url: str, member_name: str, dest_path: Path) -> Path:
    if dest_path.exists():
        return dest_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    zip_path = _cached_zip(url)
    with zipfile.ZipFile(zip_path) as archive:
        dest_path.write_bytes(archive.read(member_name))
    return dest_path


def style_suffix(weight: str, italic: bool) -> str:
    if not italic:
        return weight
    return "Italic" if weight == "Regular" else f"{weight}Italic"


def jetbrains_mono_path(weight: str, italic: bool = False, version: str | None = None) -> Path:
    version = version or JETBRAINS_MONO_VERSION
    suffix = style_suffix(weight, italic)
    url = (
        f"https://github.com/JetBrains/JetBrainsMono/releases/download/"
        f"v{version}/JetBrainsMono-{version}.zip"
    )
    dest = UPSTREAM_DIR / "jetbrains-mono" / version / f"JetBrainsMono-{suffix}.ttf"
    return _extract_member(url, f"fonts/ttf/JetBrainsMono-{suffix}.ttf", dest)


def noto_cjk_variable_path(locale: str, version: str | None = None) -> Path:
    version = version or NOTO_CJK_RELEASE_TAG
    url = (
        f"https://github.com/notofonts/noto-cjk/releases/download/"
        f"{version}/{NOTO_CJK_VF_ASSET}"
    )
    member = NOTO_CJK_VF_MEMBERS[locale]
    dest = UPSTREAM_DIR / "noto-sans-cjk-vf" / version / f"NotoSansCJK{locale}-VF.ttf"
    return _extract_member(url, member, dest)


def noto_cjk_weight_instance_path(
    locale: str, weight_value: int, version: str | None = None
) -> Path:
    """Instantiate one static weight from the Noto Sans CJK variable font, cached."""
    version = version or NOTO_CJK_RELEASE_TAG
    dest = (
        UPSTREAM_DIR / "noto-sans-cjk-instances" / version
        / f"NotoSansCJK{locale}-{weight_value}.ttf"
    )
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = TTFont(str(noto_cjk_variable_path(locale, version)))
    instance = instantiateVariableFont(source, {"wght": float(weight_value)}, inplace=False)
    return save_font_atomic(instance, dest)


def maple_mono_path(weight: str, italic: bool = False, version: str | None = None) -> Path:
    version = version or MAPLE_MONO_VERSION
    suffix = style_suffix(weight, italic)
    url = (
        f"https://github.com/subframe7536/maple-font/releases/download/"
        f"v{version}/{MAPLE_MONO_ASSET}"
    )
    dest = UPSTREAM_DIR / "maple-mono" / version / f"MapleMono-{suffix}.ttf"
    return _extract_member(url, f"MapleMono-{suffix}.ttf", dest)


NERD_FONT_VERSION = _upstream_versions["nerd_fonts"]

# Nerd Fonts ships a pre-patched "JetBrainsMono Nerd Font" release -- icons
# already scaled by the official font-patcher's per-icon-set ScaleGroups/
# Attributes rules against JetBrains Mono's OWN cell metrics (not some
# generic donor scaled to an arbitrary base). Verified: this release's
# head.unitsPerEm/hmtx advance/hhea ascent+descent are identical to our own
# jetbrains_mono_path() base, so glyphs drop in with zero rescaling -- no
# hand-tuned boost constant needed (nerd_font.py used to carry one, tuned by
# eye against Maple Mono's own NF release, before this switch).
#
# Deliberately NOT the "Mono" suffixed variant (JetBrainsMonoNerdFontMono):
# that one clamps every icon's ink strictly inside its single-cell advance
# box (ink/advance ratio forced to ~1.0), which reads visually smaller/
# thinner than icon fonts that let ink overlap past the box edge -- verified
# against Maple Mono's own NF release, whose icon ink/advance ratios (e.g.
# 1.49 for fa-github, 1.75 for fa-folder_open_o) match this plain variant
# almost exactly, not the Mono variant's clamped ~1.0. Advance width is
# still a uniform single cell either way (600, same as Latin) since the
# *base* font (JetBrains Mono) is monospace -- "Mono" here only describes
# whether icon ink is allowed to bleed past that cell, not whether the grid
# itself is monospace.
NERD_FONT_ASSET = "JetBrainsMono.zip"


def jetbrains_mono_nerd_font_path(version: str | None = None) -> Path:
    version = version or NERD_FONT_VERSION
    url = (
        f"https://github.com/ryanoasis/nerd-fonts/releases/download/"
        f"{version}/{NERD_FONT_ASSET}"
    )
    dest = UPSTREAM_DIR / "nerd-fonts" / version / "JetBrainsMonoNerdFont-Regular.ttf"
    return _extract_member(url, "JetBrainsMonoNerdFont-Regular.ttf", dest)
