"""Unit tests for the layout tree algebra."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "src"))

import layouts
from layouts import pane, split


# Exported from a live herdr 0.9.1 tab: root splits right, its first branch
# splits down. Trimmed of cwd, which the algebra ignores.
LIVE = split("right",
             split("down", pane("w1C:p8R"), pane("w1C:p8Z"), ratio=0.3),
             pane("w1C:p8Y"),
             ratio=0.7)


class TestTraversal(unittest.TestCase):
    def test_pane_ids_are_in_visual_order(self):
        self.assertEqual(layouts.pane_ids(LIVE), ["w1C:p8R", "w1C:p8Z", "w1C:p8Y"])

    def test_pane_ids_of_a_lone_pane(self):
        self.assertEqual(layouts.pane_ids(pane("a")), ["a"])

    def test_split_paths_match_the_api_convention(self):
        # [] is the root, False descends into "first" — verified live against
        # set_split_ratio, where [True] here is `split_not_found`.
        self.assertEqual([(p, n["ratio"]) for p, n in layouts.splits(LIVE)],
                         [([], 0.7), ([False], 0.3)])

    def test_a_lone_pane_has_no_splits(self):
        self.assertEqual(list(layouts.splits(pane("a"))), [])


class TestShapeEqual(unittest.TestCase):
    def test_ratios_do_not_count(self):
        self.assertTrue(layouts.shape_equal(LIVE, layouts.balanced(LIVE)))

    def test_direction_counts(self):
        flipped = split("down", LIVE["first"], LIVE["second"])
        self.assertFalse(layouts.shape_equal(LIVE, flipped))

    def test_pane_order_counts(self):
        swapped = split("right", LIVE["second"], LIVE["first"])
        self.assertFalse(layouts.shape_equal(LIVE, swapped))

    def test_depth_counts(self):
        flat = split("right", pane("w1C:p8R"), pane("w1C:p8Y"))
        self.assertFalse(layouts.shape_equal(LIVE, flat))

    def test_a_pane_never_matches_a_split(self):
        self.assertFalse(layouts.shape_equal(pane("a"), split("right", pane("a"), pane("b"))))


class TestRatioPlan(unittest.TestCase):
    def test_equalize_plan_hits_every_off_split(self):
        self.assertEqual(layouts.ratio_plan(LIVE, layouts.balanced(LIVE)),
                         [([], 0.5), ([False], 0.5)])

    def test_splits_already_on_target_are_left_out(self):
        target = layouts.balanced(LIVE)
        target["ratio"] = 0.7                      # root already there
        self.assertEqual(layouts.ratio_plan(LIVE, target), [([False], 0.5)])

    def test_an_equalized_tab_replans_to_nothing(self):
        self.assertEqual(layouts.ratio_plan(layouts.balanced(LIVE), layouts.balanced(LIVE)), [])

    def test_differing_shapes_are_rejected(self):
        flat = split("right", pane("w1C:p8R"), pane("w1C:p8Y"))
        with self.assertRaises(ValueError):
            layouts.ratio_plan(LIVE, flat)


class TestConstructors(unittest.TestCase):
    def test_balanced_keeps_shape_and_pane_order(self):
        even = layouts.balanced(LIVE)
        self.assertEqual(layouts.pane_ids(even), layouts.pane_ids(LIVE))
        self.assertEqual([r for _, r in layouts.ratio_plan(even, even)], [])
        self.assertTrue(all(n["ratio"] == 0.5 for _, n in layouts.splits(even)))

    def test_tiled_nests_into_the_second_branch(self):
        # a | (b | c), the shape repeated right-splits actually produce
        self.assertEqual(layouts.tiled(["a", "b", "c"]),
                         split("right", pane("a"), split("right", pane("b"), pane("c"))))

    def test_tiled_of_one_pane_has_no_split(self):
        self.assertEqual(layouts.tiled(["a"]), pane("a"))

    def test_tiled_rejects_an_empty_tab(self):
        with self.assertRaises(ValueError):
            layouts.tiled([])


if __name__ == "__main__":
    unittest.main()
