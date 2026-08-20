"""Compose this project's font family name / release file prefix.

Single source of truth for "what does this build's name look like" -- used
by build.py (baked into the font's own name table) and release.yml (to name
the release zip/asset files), so renaming the project is one edit to
config.json's family_name, not a hunt through hardcoded strings scattered
across a workflow file.

The Han-priority locale is always folded into the name (e.g. "... Mono TC",
not just "... Mono") even though tc is the default today -- this project
only ships one locale variant right now, but baking the locale into the
name from day one means a future sc/jp/kr/hk release variant gets its own
distinct name for free, instead of requiring another rename across every
file that touches naming.

Family name (space-separated, for the font's own name table) and file
prefix (hyphen-separated, for filenames) use the same segment order --
"{base} {LOCALE} [NF]" / "{base}-{LOCALE}[-NF]" -- just a different
separator/spacing convention, so the two never drift apart. config.json's
family_name already includes "Mono" (e.g. "Blanda JNM Mono") since that's
part of this project's identity, not a suffix naming.py should own.
"""

from __future__ import annotations

import argparse

from scripts.config import load_config

_config = load_config()
BASE_FAMILY_NAME = _config["family_name"]
HAN_PRIORITY_DEFAULT = _config["cjk"]["han_priority"]


def compose_family_name(han_priority: str = HAN_PRIORITY_DEFAULT, nerd_font: bool = False) -> str:
    name = f"{BASE_FAMILY_NAME} {han_priority.upper()}"
    return f"{name} NF" if nerd_font else name


def compose_file_prefix(han_priority: str = HAN_PRIORITY_DEFAULT, nerd_font: bool = False) -> str:
    base = BASE_FAMILY_NAME.replace(" ", "")
    prefix = f"{base}-{han_priority.upper()}"
    return f"{prefix}-NF" if nerd_font else prefix


def main() -> None:
    parser = argparse.ArgumentParser(description="Print this build's file prefix (for use in shell scripts).")
    parser.add_argument("--han-priority", default=HAN_PRIORITY_DEFAULT)
    parser.add_argument("--nerd-font", action="store_true")
    args = parser.parse_args()
    print(compose_file_prefix(args.han_priority, args.nerd_font))


if __name__ == "__main__":
    main()
