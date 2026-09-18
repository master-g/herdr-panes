"""Unit tests for the layout tree algebra."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "src"))

import cycle
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


class TestParentSplit(unittest.TestCase):
    def test_finds_the_split_a_nested_pane_hangs_off(self):
        self.assertIs(layouts.parent_split(LIVE, "w1C:p8Z"), LIVE["first"])

    def test_finds_the_root_for_a_top_level_pane(self):
        self.assertIs(layouts.parent_split(LIVE, "w1C:p8Y"), LIVE)

    def test_a_lone_pane_has_no_parent(self):
        self.assertIsNone(layouts.parent_split(pane("a"), "a"))

    def test_an_unknown_pane_has_no_parent(self):
        self.assertIsNone(layouts.parent_split(LIVE, "w1C:nope"))


class TestNextInCycle(unittest.TestCase):
    PRESETS = [1 / 3.0, 0.5, 2 / 3.0]

    def test_an_exact_preset_advances_by_one(self):
        self.assertEqual(layouts.next_in_cycle(0.5, self.PRESETS), 2 / 3.0)

    def test_the_last_preset_wraps(self):
        self.assertEqual(layouts.next_in_cycle(2 / 3.0, self.PRESETS), 1 / 3.0)

    def test_a_hand_dragged_ratio_lands_on_the_next_one_up(self):
        self.assertEqual(layouts.next_in_cycle(0.43, self.PRESETS), 0.5)

    def test_a_ratio_above_every_preset_wraps(self):
        self.assertEqual(layouts.next_in_cycle(0.9, self.PRESETS), 1 / 3.0)

    def test_float_noise_does_not_stall_the_cycle(self):
        self.assertEqual(layouts.next_in_cycle(1 / 3.0 + 1e-9, self.PRESETS), 0.5)


class TestInsertPlan(unittest.TestCase):
    """The plan has to rebuild the tree exactly, or a reshape scrambles the tab."""

    TREES = {
        "lone pane": pane("a"),
        "one split": split("right", pane("a"), pane("b"), ratio=0.4),
        "nested right": split("right", pane("a"), split("down", pane("b"), pane("c"))),
        # the shape naive left-to-right insertion cannot reach: the outer split's
        # first branch is itself a split
        "nested left": split("right", split("down", pane("a"), pane("b")), pane("c")),
        "deep both sides": split("down",
                                 split("right", pane("a"), pane("b"), ratio=0.2),
                                 split("right", pane("c"), split("down", pane("d"), pane("e"))),
                                 ratio=0.6),
        "live tab": LIVE,
    }

    def rebuild(self, target):
        tree = pane(layouts.first_pane(target))
        for pane_id, target_id, direction, ratio in layouts.insert_plan(target):
            tree = layouts.apply_insert(tree, pane_id, target_id, direction, ratio)
        return tree

    def test_every_tree_is_rebuilt_exactly(self):
        for name, target in self.TREES.items():
            self.assertEqual(self.rebuild(target), target, name)

    def test_a_lone_pane_needs_no_moves(self):
        self.assertEqual(layouts.insert_plan(pane("a")), [])

    def test_one_move_per_pane_beyond_the_anchor(self):
        for name, target in self.TREES.items():
            self.assertEqual(len(layouts.insert_plan(target)),
                             len(layouts.pane_ids(target)) - 1, name)

    def test_the_anchor_is_never_moved(self):
        for name, target in self.TREES.items():
            moved = [pane_id for pane_id, _, _, _ in layouts.insert_plan(target)]
            self.assertNotIn(layouts.first_pane(target), moved, name)

    def test_a_pane_only_splits_off_one_already_placed(self):
        for name, target in self.TREES.items():
            placed = set([layouts.first_pane(target)])
            for pane_id, target_id, _, _ in layouts.insert_plan(target):
                self.assertIn(target_id, placed, "%s: %s" % (name, target_id))
                placed.add(pane_id)


class TestNextTarget(unittest.TestCase):
    IDS = ["a", "b", "c"]
    COLUMNS = layouts.tiled(IDS, "right")
    ROWS = layouts.tiled(IDS, "down")

    def test_a_tab_already_in_a_preset_advances(self):
        self.assertEqual(cycle.next_target(self.COLUMNS, [self.COLUMNS, self.ROWS]), self.ROWS)

    def test_the_last_preset_wraps(self):
        self.assertEqual(cycle.next_target(self.ROWS, [self.COLUMNS, self.ROWS]), self.COLUMNS)

    def test_an_unrecognised_shape_starts_over(self):
        odd = split("right", split("down", pane("a"), pane("b")), pane("c"))
        self.assertEqual(cycle.next_target(odd, [self.COLUMNS, self.ROWS]), self.COLUMNS)

    def test_ratios_do_not_stop_a_preset_from_matching(self):
        stretched = layouts.balanced(self.COLUMNS, ratio=0.8)
        self.assertEqual(cycle.next_target(stretched, [self.COLUMNS, self.ROWS]), self.ROWS)

    def test_a_single_preset_cycles_to_itself(self):
        # the shape already matches, so the caller takes the ratio-only fast path
        self.assertEqual(cycle.next_target(self.COLUMNS, [self.COLUMNS]), self.COLUMNS)


if __name__ == "__main__":
    unittest.main()
