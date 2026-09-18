#!/usr/bin/env python3
"""Cycle the tab through layout presets (docs/design.md §4.3).

Two paths: when the next preset has the shape the tab already has, only the
split ratios move and nothing is touched. Otherwise the panes go through a
staging tab, which is the only way to change a tab's shape without killing what
runs in it.
"""

import config
import herdr
import layouts
import reshape

PRESETS = {
    "columns": lambda ids: layouts.tiled(ids, "right"),
    "rows": lambda ids: layouts.tiled(ids, "down"),
}


def next_target(current, targets):
    """The preset after the one the tab is already in; the first one otherwise."""
    for index, target in enumerate(targets):
        if layouts.shape_equal(current, target):
            return targets[(index + 1) % len(targets)]
    return targets[0]


def main():
    layout = herdr.export()["layout"]
    root = layout["root"]
    ids = layouts.pane_ids(root)
    if len(ids) < 2:
        return 0

    order = config.load()["cycle"]
    unknown = [name for name in order if name not in PRESETS]
    if unknown:
        raise ValueError("%s: unknown preset(s) in \"cycle\": %s; known: %s"
                         % (config.path(), ", ".join(unknown), ", ".join(sorted(PRESETS))))

    target = next_target(root, [PRESETS[name](ids) for name in order])
    if layouts.shape_equal(root, target):
        for path, ratio in layouts.ratio_plan(root, target):
            herdr.set_split_ratio(path=path, ratio=ratio, tab_id=layout["tab_id"])
    else:
        reshape.reshape(layout, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
