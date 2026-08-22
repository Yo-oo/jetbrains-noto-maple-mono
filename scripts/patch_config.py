"""Patch arbitrary config.jsonc keys in place, for a single CI run.

build.yml uses this instead of a bespoke --override CLI flag per config
field: every workflow input maps straight onto a config.jsonc dotted path,
so tags.list (a JSON array, or null to disable) and tags.corner_radius work
the same way as every other field, with no argparse type-conversion
mismatch between "blank means don't override" and "null means disable".

Each --set value must be valid JSON (numbers/booleans/null bare, strings
quoted, e.g. --set tags.badge_weight='"SemiBold"' --set tags.list=null).
Rewrites config.jsonc as plain JSON -- comments are not preserved, which is
fine for a throwaway CI checkout that's never committed back.

Run:
    python -m scripts.patch_config --set cjk.fill_ratio=0.9 --set tags.list=null
"""

from __future__ import annotations

import argparse
import json

from scripts.common import REPO_ROOT
from scripts.config import load_config

CONFIG_PATH = REPO_ROOT / "config.jsonc"


def _set_path(config: dict, dotted_path: str, value) -> None:
    keys = dotted_path.split(".")
    node = config
    for key in keys[:-1]:
        if key not in node:
            raise KeyError(f"config.jsonc has no key {'.'.join(keys[:keys.index(key) + 1])!r}")
        node = node[key]
    if keys[-1] not in node:
        raise KeyError(f"config.jsonc has no key {dotted_path!r}")
    node[keys[-1]] = value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        dest="overrides",
        metavar="path.to.key=<json value>",
    )
    args = parser.parse_args()

    config = load_config()
    for item in args.overrides:
        path, sep, raw_value = item.partition("=")
        if not sep:
            raise SystemExit(f"--set value must be path=value, got {item!r}")
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError as error:
            raise SystemExit(f"--set {path}: {raw_value!r} is not valid JSON ({error})")
        _set_path(config, path, value)
        print(f"[patch_config] {path} = {value!r}")

    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
