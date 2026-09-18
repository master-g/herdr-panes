"""Unit tests for reading the user's config file."""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "src"))

import config


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.path = os.path.join(self.directory, "config.json")

    def tearDown(self):
        shutil.rmtree(self.directory)

    def write(self, text):
        with open(self.path, "w") as handle:
            handle.write(text)

    def load(self, value):
        self.write(json.dumps(value))
        return config.load(self.path)

    def refuses(self, value, *fragments):
        self.write(value if isinstance(value, str) else json.dumps(value))
        with self.assertRaises(ValueError) as caught:
            config.load(self.path)
        for fragment in fragments:
            self.assertIn(fragment, str(caught.exception))


class TestDefaults(ConfigTestCase):
    def test_no_file_means_defaults(self):
        self.assertEqual(config.load(self.path), config.DEFAULTS)

    def test_the_defaults_are_not_handed_out_to_be_mutated(self):
        loaded = config.load(self.path)
        loaded["cell_aspect"] = 99
        self.assertEqual(config.DEFAULTS["cell_aspect"], 2.0)

    def test_unset_keys_keep_their_default(self):
        self.assertEqual(self.load({"cell_aspect": 1.5})["cycle"], config.DEFAULTS["cycle"])

    def test_the_config_dir_comes_from_the_host(self):
        os.environ["HERDR_PLUGIN_CONFIG_DIR"] = self.directory
        try:
            self.assertEqual(config.path(), self.path)
        finally:
            del os.environ["HERDR_PLUGIN_CONFIG_DIR"]


class TestAccepted(ConfigTestCase):
    def test_a_whole_number_is_fine_for_a_ratio(self):
        self.assertEqual(self.load({"cell_aspect": 2})["cell_aspect"], 2.0)

    def test_list_items_are_coerced_too(self):
        self.assertEqual(self.load({"master_widths": [1, 0.5]})["master_widths"], [1.0, 0.5])

    def test_a_flag_is_taken_as_written(self):
        self.assertIs(self.load({"preserve_split": True})["preserve_split"], True)


class TestRefused(ConfigTestCase):
    def test_broken_json_names_the_file(self):
        self.refuses("{not json", self.path, "not valid JSON")

    def test_a_list_at_the_top_level(self):
        self.refuses([1, 2], "expected an object")

    def test_an_unknown_setting_lists_the_known_ones(self):
        self.refuses({"cell_aspekt": 2.0}, "cell_aspekt", "cell_aspect")

    def test_a_number_where_a_flag_belongs(self):
        self.refuses({"preserve_split": 1}, "preserve_split", "true or false")

    def test_a_flag_where_a_number_belongs(self):
        self.refuses({"cell_aspect": True}, "cell_aspect", "expected a number")

    def test_a_string_where_a_number_belongs(self):
        self.refuses({"cell_aspect": "2.0"}, "cell_aspect", "expected a number")

    def test_an_empty_list(self):
        self.refuses({"cycle": []}, "cycle", "non-empty list")

    def test_a_bad_item_points_at_its_index(self):
        self.refuses({"master_widths": [0.5, "wide"]}, "master_widths[1]", "expected a number")


if __name__ == "__main__":
    unittest.main()
