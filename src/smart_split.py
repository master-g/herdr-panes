#!/usr/bin/env python3
"""Split the focused pane along its longer visual side (hyprland dwindle rule)."""

import sys

import config
import herdr
import layouts


def direction_for(rect, cell_aspect=config.DEFAULTS["cell_aspect"]):
    """Wider than tall on screen -> split right, otherwise down."""
    return "right" if rect["width"] >= rect["height"] * cell_aspect else "down"


def main():
    # ponytail: cell_aspect is a knob because fonts and line spacing move the
    # real ratio; preserve_split is off by default, like hyprland's
    settings = config.load()
    layout = herdr.export()["layout"]
    focused = layout["focused_pane_id"]

    direction = None
    if settings["preserve_split"]:
        parent = layouts.parent_split(layout["root"], focused)
        direction = parent["direction"] if parent else None   # lone pane: fall through
    if direction is None:
        panes = herdr.call("pane.layout", pane_id=focused)["layout"]["panes"]
        direction = direction_for(next(p for p in panes if p["pane_id"] == focused)["rect"],
                                  settings["cell_aspect"])

    pane = herdr.call("pane.get", pane_id=focused)["pane"]
    herdr.call("pane.split", target_pane_id=focused, direction=direction,
               cwd=pane.get("foreground_cwd") or pane["cwd"])
    return 0


def check():
    assert direction_for({"width": 280, "height": 69}) == "right"   # full-width tab
    assert direction_for({"width": 140, "height": 69}) == "right"   # visually square, ties go right
    assert direction_for({"width": 137, "height": 69}) == "down"    # just past square
    assert direction_for({"width": 80, "height": 69}) == "down"     # tall column
    assert direction_for({"width": 80, "height": 69}, cell_aspect=1.0) == "right"
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(check() if "--check" in sys.argv else main())
