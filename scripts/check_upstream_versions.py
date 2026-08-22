"""Check whether any pinned upstream release has a newer version available.

This project deliberately pins exact upstream versions (config.jsonc's
upstream_versions, surfaced as download.py's JETBRAINS_MONO_VERSION/
NOTO_CJK_RELEASE_TAG/NERD_FONT_VERSION) for reproducible builds -- nothing
auto-updates them. This script is the other half of that
tradeoff: a cheap way to find out
when a bump is available, without silently rebuilding against a moving
target. Wired into a scheduled workflow that opens a GitHub Issue rather
than auto-bumping, since a new upstream release could change enough (a
renamed asset, a different weight range) to need a human look anyway --
several of this project's own overlay assumptions were discovered exactly
that way.

Run:

    python -m scripts.check_upstream_versions
"""

from __future__ import annotations

import json
import sys
from urllib.request import Request, urlopen

from scripts.download import (
    JETBRAINS_MONO_VERSION,
    NERD_FONT_VERSION,
    NOTO_CJK_RELEASE_TAG,
)


def _get_json(url: str):
    request = Request(url, headers={"Accept": "application/vnd.github+json"})
    with urlopen(request) as response:
        return json.loads(response.read())


def _latest_release_tag(repo: str) -> str:
    return _get_json(f"https://api.github.com/repos/{repo}/releases/latest")["tag_name"]


def _latest_matching_release_tag(repo: str, prefix: str) -> str:
    """Noto's CJK releases interleave Sans/Serif/versioned tags in one repo."""
    releases = _get_json(f"https://api.github.com/repos/{repo}/releases")
    for release in releases:
        if release["tag_name"].startswith(prefix):
            return release["tag_name"]
    raise RuntimeError(f"no release tag starting with {prefix!r} found in {repo}")


CHECKS = (
    ("JetBrains Mono", f"v{JETBRAINS_MONO_VERSION}", lambda: _latest_release_tag("JetBrains/JetBrainsMono")),
    ("Noto Sans CJK", NOTO_CJK_RELEASE_TAG, lambda: _latest_matching_release_tag("notofonts/noto-cjk", "Sans")),
    ("Nerd Fonts", NERD_FONT_VERSION, lambda: _latest_release_tag("ryanoasis/nerd-fonts")),
)


def main() -> None:
    outdated = []
    for name, pinned, fetch_latest in CHECKS:
        try:
            latest = fetch_latest()
        except Exception as error:  # network hiccup, API shape change, etc.
            print(f"[check] {name}: could not check latest release ({error})")
            continue
        if latest == pinned:
            print(f"[check] {name}: up to date ({pinned})")
        else:
            print(f"[check] {name}: OUTDATED -- pinned {pinned}, latest is {latest}")
            outdated.append((name, pinned, latest))

    if outdated:
        print(f"\n{len(outdated)} upstream(s) have a newer release available.")
        sys.exit(1)
    print("\nAll pinned upstream versions are current.")


if __name__ == "__main__":
    main()
