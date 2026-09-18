#!/usr/bin/env python3
"""Cycle the master pane through a few widths (docs/design.md §4.2).

The master area is the root split's first branch, so this moves one ratio and
nothing else: no pane is touched. When the root splits down rather than right
this cycles the master's height instead, which is the same idea turned 90°.
"""

import config
import herdr
import layouts


def main():
    # ponytail: a knob, not a constant — thirds suit a wide monitor, halves a laptop
    widths = config.load()["master_widths"]
    layout = herdr.export()["layout"]
    root = layout["root"]
    if layouts.is_pane(root):
        return 0                       # a single pane fills the tab; nothing to size
    herdr.set_split_ratio(path=[], ratio=layouts.next_in_cycle(root["ratio"], widths),
                          tab_id=layout["tab_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
