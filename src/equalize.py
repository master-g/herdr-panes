#!/usr/bin/env python3
"""Even out every split in the focused tab.

Pure metadata: the tab keeps its shape, so no pane is moved and nothing in
them is restarted (docs/design.md §4.3). Panes stay where they are even while
the tab is zoomed.
"""

import herdr
import layouts


def main():
    layout = herdr.export()["layout"]
    root = layout["root"]
    for path, ratio in layouts.ratio_plan(root, layouts.balanced(root)):
        herdr.set_split_ratio(path=path, ratio=ratio, tab_id=layout["tab_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
