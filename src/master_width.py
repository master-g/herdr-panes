#!/usr/bin/env python3
"""Cycle the master pane through a few widths (docs/design.md §4.2).

The master area is the root split's first branch, so this moves one ratio and
nothing else: no pane is touched. When the root splits down rather than right
this cycles the master's height instead, which is the same idea turned 90°.
"""

import os

import herdr
import layouts

# ponytail: a knob, not a constant — thirds suit a wide monitor, halves a laptop
WIDTHS = [float(w) for w in
          os.environ.get("HERDR_PANES_MASTER_WIDTHS", "0.333,0.5,0.667").split(",")]


def main():
    layout = herdr.export()["layout"]
    root = layout["root"]
    if layouts.is_pane(root):
        return 0                       # a single pane fills the tab; nothing to size
    herdr.set_split_ratio(path=[], ratio=layouts.next_in_cycle(root["ratio"], WIDTHS),
                          tab_id=layout["tab_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
