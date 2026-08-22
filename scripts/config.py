"""Load this project's tunable parameters and pinned upstream versions.

config.jsonc at the repo root is the single source of truth for: the pinned
upstream release versions (also read by check_upstream_versions.py, and
compared against on a schedule -- see that module's docstring for why
these are pinned rather than auto-tracking latest), the CJK visual-tuning
knobs (fill_ratio, italic_angle), the output family name, and build.py's
CLI defaults. Consolidating these in one file (rather than scattered
module-level constants) makes it possible to see everything this project
pins/tunes at a glance -- useful both for maintenance and for auditing
exactly what's fixed vs. what varies per build.

JSONC (JSON + // and /* */ comments) -- stdlib json can't parse those
directly, so _strip_jsonc_comments() removes them first. Written by hand
instead of pulling in a json5/commentjson dependency: comments only ever
need stripping outside of string literals, which a small character-
scanning state machine handles correctly (unlike a naive regex, which
would also strip a "//" that happens to appear inside a string value,
e.g. a URL).
"""

from __future__ import annotations

import json
from functools import lru_cache

from scripts.common import REPO_ROOT


def _strip_jsonc_comments(text: str) -> str:
    result = []
    i = 0
    n = len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            result.append(ch)
            if ch == "\\" and i + 1 < n:
                result.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            i = text.find("\n", i)
            if i == -1:
                break
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            if end == -1:
                raise ValueError("config.jsonc: unterminated /* comment")
            i = end + 2
            continue
        result.append(ch)
        i += 1
    return "".join(result)


@lru_cache(maxsize=1)
def load_config() -> dict:
    with open(REPO_ROOT / "config.jsonc", encoding="utf-8") as f:
        return json.loads(_strip_jsonc_comments(f.read()))
