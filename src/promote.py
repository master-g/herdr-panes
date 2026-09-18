#!/usr/bin/env python3
"""Swap the focused pane into the master position (docs/design.md §4.2).

Master is the first pane in visual order. pane.swap keeps both processes, both
pane ids and the tab's shape, so this is lossless. Promoting the pane that is
already master demotes it into the stack, the way hyprland's master layout does.
"""

import herdr
import layouts


def main():
    layout = herdr.export()["layout"]
    ids = layouts.pane_ids(layout["root"])
    if len(ids) < 2:
        return 0
    focused = layout["focused_pane_id"]
    target = ids[1] if focused == ids[0] else ids[0]
    herdr.call("pane.swap", source_pane_id=focused, target_pane_id=target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
