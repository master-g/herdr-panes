#!/usr/bin/env python3
"""Layout tree algebra for herdr's BSP trees (docs/design.md §4.3).

A node is the same dict shape layout.export returns:
    {"type": "pane", "pane_id": ..., "cwd": ...}
    {"type": "split", "direction": "right"|"down", "ratio": float, "first": ..., "second": ...}

A split path is a list of bools, as layout.set_split_ratio takes it: [] is the
root split, False descends into "first", True into "second". Verified against
herdr 0.9.1 — a path that names no split comes back as `split_not_found`.
"""

RATIO_EPSILON = 1e-6


def pane(pane_id=None, cwd=None):
    node = {"type": "pane"}
    if pane_id is not None:
        node["pane_id"] = pane_id
    if cwd is not None:
        node["cwd"] = cwd
    return node


def split(direction, first, second, ratio=0.5):
    return {"type": "split", "direction": direction, "ratio": ratio,
            "first": first, "second": second}


def is_pane(node):
    return node["type"] == "pane"


def pane_ids(node):
    """Pane ids in visual order: first branch before second."""
    if is_pane(node):
        return [node.get("pane_id")]
    return pane_ids(node["first"]) + pane_ids(node["second"])


def splits(node, path=()):
    """Yield (path, split_node) for every split, parents before children."""
    if is_pane(node):
        return
    yield list(path), node
    for branch, key in ((False, "first"), (True, "second")):
        for item in splits(node[key], tuple(path) + (branch,)):
            yield item


def shape_equal(a, b):
    """True when the two trees differ only in ratios (and pane metadata)."""
    if is_pane(a) or is_pane(b):
        return is_pane(a) and is_pane(b) and a.get("pane_id") == b.get("pane_id")
    return (a["direction"] == b["direction"]
            and shape_equal(a["first"], b["first"])
            and shape_equal(a["second"], b["second"]))


def ratio_plan(current, target):
    """[(path, ratio)] turning current into target without moving a pane.

    Raises ValueError when the shapes differ — the caller has to reshape via
    staging instead (docs/design.md §4.3). Splits already at the target ratio
    are left out, so an equalized tab replans to an empty list.
    """
    if not shape_equal(current, target):
        raise ValueError("shapes differ; ratio_plan cannot get there without moving panes")
    now = dict((tuple(path), node["ratio"]) for path, node in splits(current))
    return [(path, node["ratio"]) for path, node in splits(target)
            if abs(now[tuple(path)] - node["ratio"]) > RATIO_EPSILON]


def balanced(node, ratio=0.5):
    """Same shape, every split at `ratio`. The equalize target."""
    if is_pane(node):
        return node
    return split(node["direction"], balanced(node["first"], ratio),
                 balanced(node["second"], ratio), ratio)


def tiled(ids, direction="right"):
    """One spine: every split the same direction. Columns, or rows for "down"."""
    if not ids:
        raise ValueError("tiled needs at least one pane")
    node = pane(ids[-1])
    for pane_id in reversed(ids[:-1]):
        node = split(direction, pane(pane_id), node)
    return node


def parent_split(node, pane_id):
    """The split a pane hangs off, or None when the pane is the whole tab."""
    if is_pane(node):
        return None
    for key in ("first", "second"):
        child = node[key]
        if is_pane(child):
            if child.get("pane_id") == pane_id:
                return node
        else:
            found = parent_split(child, pane_id)
            if found is not None:
                return found
    return None


def next_in_cycle(current, values):
    """The first value above `current`, wrapping around.

    Cycling from a ratio the user dragged to by hand lands on the next preset
    up rather than snapping backwards, and an exact preset advances by one.
    """
    for value in values:
        if value > current + RATIO_EPSILON:
            return value
    return values[0]


def first_pane(node):
    """The pane in the master position: leftmost, then topmost."""
    return pane_ids(node)[0]


def insert_plan(node):
    """[(pane_id, target_pane_id, direction, ratio)] rebuilding `node` by insertion.

    pane.move puts the moved pane on the *second* side of a new split at the
    target pane, so a tree has to be built outermost split first: the pane that
    opens a split is the first pane of that split's second branch, and it splits
    off the pane that already holds the region. Applying the plan in order to a
    tab holding only first_pane(node) reproduces `node` exactly.
    """
    anchor = first_pane(node)
    plan = []

    def walk(current, held_by):
        if is_pane(current):
            return
        opener = first_pane(current["second"])
        plan.append((opener, held_by, current["direction"], current["ratio"]))
        walk(current["first"], held_by)
        walk(current["second"], opener)

    walk(node, anchor)
    return plan


def apply_insert(node, pane_id, target_pane_id, direction, ratio):
    """Where a pane lands when moved next to `target_pane_id`. Mirrors pane.move."""
    if is_pane(node):
        if node.get("pane_id") != target_pane_id:
            return node
        return split(direction, node, pane(pane_id), ratio)
    return split(node["direction"],
                 apply_insert(node["first"], pane_id, target_pane_id, direction, ratio),
                 apply_insert(node["second"], pane_id, target_pane_id, direction, ratio),
                 node["ratio"])
