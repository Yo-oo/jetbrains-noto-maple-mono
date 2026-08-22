"""Tests for patch_config.py."""

from __future__ import annotations

import json
import unittest

from scripts.patch_config import _set_path


class SetPathTest(unittest.TestCase):
    def test_sets_a_nested_key(self):
        config = {"tags": {"corner_radius": "pill"}}
        _set_path(config, "tags.corner_radius", 0)
        self.assertEqual(config["tags"]["corner_radius"], 0)

    def test_sets_to_null(self):
        config = {"tags": {"list": ["[INFO]"]}}
        _set_path(config, "tags.list", None)
        self.assertIsNone(config["tags"]["list"])

    def test_sets_a_top_level_key(self):
        config = {"family_name": "Old"}
        _set_path(config, "family_name", "New")
        self.assertEqual(config["family_name"], "New")

    def test_unknown_path_raises(self):
        config = {"tags": {"corner_radius": "pill"}}
        with self.assertRaises(KeyError):
            _set_path(config, "tags.does_not_exist", 1)

    def test_unknown_parent_raises(self):
        config = {"tags": {"corner_radius": "pill"}}
        with self.assertRaises(KeyError):
            _set_path(config, "does_not_exist.corner_radius", 1)

    def test_json_array_round_trips(self):
        config = {"tags": {"list": None}}
        value = json.loads('["[INFO]", "[WARN]"]')
        _set_path(config, "tags.list", value)
        self.assertEqual(config["tags"]["list"], ["[INFO]", "[WARN]"])


if __name__ == "__main__":
    unittest.main()
