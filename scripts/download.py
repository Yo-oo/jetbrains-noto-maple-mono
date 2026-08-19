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

JETBRAINS_MONO_VERSION = _upstream_versions["jetbrains_mono"]
JETBRAINS_MONO_URL = (
    f"https://github.com/JetBrains/JetBrainsMono/releases/download/"
    f"v{JETBRAINS_MONO_VERSION}/JetBrainsMono-{JETBRAINS_MONO_VERSION}.zip"
)

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


def jetbrains_mono_path(weight: str, italic: bool = False) -> Path:
    suffix = style_suffix(weight, italic)
    dest = UPSTREAM_DIR / "jetbrains-mono" / f"JetBrainsMono-{suffix}.ttf"
    return _extract_member(JETBRAINS_MONO_URL, f"fonts/ttf/JetBrainsMono-{suffix}.ttf", dest)


def noto_cjk_variable_path(locale: str) -> Path:
    url = (
        f"https://github.com/notofonts/noto-cjk/releases/download/"
        f"{NOTO_CJK_RELEASE_TAG}/{NOTO_CJK_VF_ASSET}"
    )
    member = NOTO_CJK_VF_MEMBERS[locale]
    dest = UPSTREAM_DIR / "noto-sans-cjk-vf" / f"NotoSansCJK{locale}-VF.ttf"
    return _extract_member(url, member, dest)


def noto_cjk_weight_instance_path(locale: str, weight_value: int) -> Path:
    """Instantiate one static weight from the Noto Sans CJK variable font, cached."""
    dest = UPSTREAM_DIR / "noto-sans-cjk-instances" / f"NotoSansCJK{locale}-{weight_value}.ttf"
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = TTFont(str(noto_cjk_variable_path(locale)))
    instance = instantiateVariableFont(source, {"wght": float(weight_value)}, inplace=False)
    return save_font_atomic(instance, dest)


def maple_mono_path(weight: str, italic: bool = False) -> Path:
    suffix = style_suffix(weight, italic)
    url = (
        f"https://github.com/subframe7536/maple-font/releases/download/"
        f"v{MAPLE_MONO_VERSION}/{MAPLE_MONO_ASSET}"
    )
    dest = UPSTREAM_DIR / "maple-mono" / f"MapleMono-{suffix}.ttf"
    return _extract_member(url, f"MapleMono-{suffix}.ttf", dest)


NERD_FONT_VERSION = _upstream_versions["nerd_fonts"]
NERD_FONT_ASSET = "NerdFontsSymbolsOnly.zip"


def nerd_font_symbols_path() -> Path:
    url = (
        f"https://github.com/ryanoasis/nerd-fonts/releases/download/"
        f"{NERD_FONT_VERSION}/{NERD_FONT_ASSET}"
    )
    dest = UPSTREAM_DIR / "nerd-fonts" / "SymbolsNerdFontMono-Regular.ttf"
    return _extract_member(url, "SymbolsNerdFontMono-Regular.ttf", dest)
