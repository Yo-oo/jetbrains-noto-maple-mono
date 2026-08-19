"""Fetch and cache the three upstream releases this project layers together.

Every function downloads once and reuses the cached file on later runs
(cache lives under dist/upstream/, which .gitignore excludes). Re-running
the pipeline against a newer upstream version is just bumping the version
constants below -- no vendored/forked upstream code to keep in sync.
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen

from scripts.common import UPSTREAM_DIR

JETBRAINS_MONO_VERSION = "2.304"
JETBRAINS_MONO_URL = (
    f"https://github.com/JetBrains/JetBrainsMono/releases/download/"
    f"v{JETBRAINS_MONO_VERSION}/JetBrainsMono-{JETBRAINS_MONO_VERSION}.zip"
)

# Noto Sans Mono CJK: the monospace-paired variant of Noto Sans CJK -- its
# CJK advance width is already an exact 2x multiple of ITS OWN paired Latin
# advance (1000 vs 500 in a 1000-unitsPerEm font), because it's designed
# specifically for pairing with a monospace Latin font. Only Regular/Bold
# are published (no lighter/heavier weights, no italic).
NOTO_CJK_RELEASE_TAG = "Sans2.004"
NOTO_MONO_CJK_ASSETS = {
    "jp": "11_NotoSansMonoCJKjp.zip",
    "kr": "12_NotoSansMonoCJKkr.zip",
    "tc": "14_NotoSansMonoCJKtc.zip",
}

MAPLE_MONO_VERSION = "7.9"
MAPLE_MONO_ASSET = "MapleMono-TTF.zip"

WEIGHTS = ("Regular", "Bold")


def _download_zip_member(url: str, member_name: str, dest_path: Path) -> Path:
    if dest_path.exists():
        return dest_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url) as response:
        archive_bytes = response.read()
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        dest_path.write_bytes(archive.read(member_name))
    return dest_path


def jetbrains_mono_path(weight: str) -> Path:
    dest = UPSTREAM_DIR / "jetbrains-mono" / f"JetBrainsMono-{weight}.ttf"
    return _download_zip_member(
        JETBRAINS_MONO_URL, f"fonts/ttf/JetBrainsMono-{weight}.ttf", dest
    )


def noto_mono_cjk_path(locale: str, weight: str) -> Path:
    asset = NOTO_MONO_CJK_ASSETS[locale]
    url = (
        f"https://github.com/notofonts/noto-cjk/releases/download/"
        f"{NOTO_CJK_RELEASE_TAG}/{asset}"
    )
    member = f"NotoSansMonoCJK{locale}-{weight}.otf"
    dest = UPSTREAM_DIR / "noto-sans-mono-cjk" / member
    return _download_zip_member(url, member, dest)


def maple_mono_path(weight: str) -> Path:
    url = (
        f"https://github.com/subframe7536/maple-font/releases/download/"
        f"v{MAPLE_MONO_VERSION}/{MAPLE_MONO_ASSET}"
    )
    dest = UPSTREAM_DIR / "maple-mono" / f"MapleMono-{weight}.ttf"
    return _download_zip_member(url, f"MapleMono-{weight}.ttf", dest)
