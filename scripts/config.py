"""Load this project's tunable parameters and pinned upstream versions.

config.json at the repo root is the single source of truth for: the pinned
upstream release versions (also read by check_upstream_versions.py, and
compared against on a schedule -- see that module's docstring for why
these are pinned rather than auto-tracking latest), the CJK visual-tuning
knobs (fill_ratio, italic_angle), the output family name, and build.py's
CLI defaults. Consolidating these in one file (rather than scattered
module-level constants) makes it possible to see everything this project
pins/tunes at a glance -- useful both for maintenance and for auditing
exactly what's fixed vs. what varies per build.
"""

from __future__ import annotations

import json
from functools import lru_cache

from scripts.common import REPO_ROOT


@lru_cache(maxsize=1)
def load_config() -> dict:
    with open(REPO_ROOT / "config.json", encoding="utf-8") as f:
        return json.load(f)
