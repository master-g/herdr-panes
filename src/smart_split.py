#!/usr/bin/env python3
"""Split the focused pane along its longer visual side (hyprland dwindle rule)."""

import json
import os
import subprocess
import sys

# ponytail: terminal cells are taller than wide; tune per font (Hack 14pt ≈ 2.0)
CELL_ASPECT = float(os.environ.get("HERDR_CELL_ASPECT", "2.0"))


def direction_for(rect, cell_aspect=CELL_ASPECT):
    """Wider than tall on screen -> split right, otherwise down."""
    return "right" if rect["width"] >= rect["height"] * cell_aspect else "down"


def herdr(*args):
    binary = os.environ.get("HERDR_BIN_PATH", "herdr")
    out = subprocess.run([binary, *args], capture_output=True, text=True, check=True).stdout
    return json.loads(out)["result"]


def main():
    layout = herdr("pane", "layout", "--current")["layout"]
    focused_id = layout["focused_pane_id"]
    rect = next(p for p in layout["panes"] if p["pane_id"] == focused_id)["rect"]
    pane = herdr("pane", "get", focused_id)["pane"]
    herdr(
        "pane", "split", "--current",
        "--direction", direction_for(rect),
        "--cwd", pane.get("foreground_cwd") or pane["cwd"],
    )
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
