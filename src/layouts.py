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
