#!/usr/bin/env python3
"""Live checks against a real herdr session (docs/design.md §7).

    python3 test/e2e_live.py

Needs the plugin linked and a running herdr. Everything happens inside a
scratch tab this script creates and closes, so it never touches the tab you
are looking at and never moves focus. It leaves the session exactly as it
found it — including after the failure-injection checks, which is the point:
reshape is the only code here that moves someone's running process.

Not picked up by `unittest discover` (the pattern is test*.py), and it cannot
run in CI.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))

import herdr
import layouts
import reshape

LABEL = "panes-e2e"
PASSED = []


def check(name):
    def wrap(fn):
        PASSED.append((name, fn))
        return fn
    return wrap


def shape(node):
    if layouts.is_pane(node):
        return node["pane_id"]
    return "(%s %s %s)" % (node["direction"], shape(node["first"]), shape(node["second"]))


def tab_labels():
    return sorted(t["label"] or "" for t in herdr.call("tab.list")["tabs"])


def staging_tabs():
    return [t for t in herdr.call("tab.list")["tabs"] if t["label"] == reshape.STAGING_LABEL]


def layout_of(tab_id):
    return herdr.export(tab_id=tab_id)["layout"]


def pids(tab_id):
    return dict((p, herdr.call("pane.process_info", pane_id=p)["process_info"]["shell_pid"])
                for p in layouts.pane_ids(layout_of(tab_id)["root"]))


def failing_move(fail_on):
    """Wrap reshape._move so the given 1-based call numbers raise instead."""
    real = reshape._move
    calls = {"n": 0}

    def flaky(pane_id, **destination):
        calls["n"] += 1
        if calls["n"] in fail_on:
            raise reshape.ReshapeFailed("injected failure #%d" % calls["n"])
        return real(pane_id, **destination)

    return real, flaky, calls


@check("reshape rebuilds the target shape and keeps every process")
def _reshape_round_trip(tab):
    before = pids(tab)
    ids = layouts.pane_ids(layout_of(tab)["root"])
    for direction in ("down", "right"):
        target = layouts.tiled(ids, direction)
        assert reshape.reshape(layout_of(tab), target) is True, "expected panes to move"
        root = layout_of(tab)["root"]
        assert shape(root) == shape(target), "%s != %s" % (shape(root), shape(target))
        assert layouts.pane_ids(root) == ids, "pane order changed"
        assert pids(tab) == before, "a shell was restarted"
        assert not staging_tabs(), "staging tab left behind"


@check("a target the tab already matches moves nothing")
def _no_op(tab):
    current = layout_of(tab)
    real, flaky, calls = failing_move(fail_on=[1])          # any move at all is a failure
    reshape._move = flaky
    try:
        assert reshape.reshape(current, layouts.balanced(current["root"])) is False
    finally:
        reshape._move = real
    assert calls["n"] == 0, "it moved a pane for a shape it already had"


@check("a target that displaces the master pane is refused")
def _anchor_guard(tab):
    root = layout_of(tab)["root"]
    before = shape(root)
    reversed_ids = list(reversed(layouts.pane_ids(root)))
    try:
        reshape.reshape(layout_of(tab), layouts.tiled(reversed_ids, "right"))
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    assert shape(layout_of(tab)["root"]) == before, "the tab was touched anyway"


@check("a failure part way back rolls the tab all the way back")
def _rollback(tab):
    current = layout_of(tab)
    before_shape, before_pids = shape(current["root"]), pids(tab)
    before_ratios = [n["ratio"] for _, n in layouts.splits(current["root"])]
    ids = layouts.pane_ids(current["root"])
    other = "down" if current["root"]["direction"] == "right" else "right"

    # call 4 is the second move of the rebuild: one pane is back, one is parked
    real, flaky, calls = failing_move(fail_on=[4])
    reshape._move = flaky
    try:
        reshape.reshape(current, layouts.tiled(ids, other))
    except reshape.ReshapeFailed:
        pass
    else:
        raise AssertionError("expected ReshapeFailed")
    finally:
        reshape._move = real

    root = layout_of(tab)["root"]
    assert shape(root) == before_shape, "shape not restored: %s" % shape(root)
    assert [n["ratio"] for _, n in layouts.splits(root)] == before_ratios, "ratios not restored"
    assert pids(tab) == before_pids, "a shell was restarted"
    assert not staging_tabs(), "staging tab left behind"
    assert calls["n"] > 4, "rollback never ran"


@check("a failed rollback keeps the staging tab instead of closing it on a pane")
def _rollback_failure_keeps_staging(tab):
    current = layout_of(tab)
    ids = layouts.pane_ids(current["root"])
    other = "down" if current["root"]["direction"] == "right" else "right"
    anchor = layouts.first_pane(current["root"])

    real, flaky, _ = failing_move(fail_on=[4, 7])          # the rebuild and the rollback both fail
    reshape._move = flaky
    try:
        reshape.reshape(current, layouts.tiled(ids, other))
    except reshape.ReshapeFailed as exc:
        message = str(exc)
    else:
        raise AssertionError("expected ReshapeFailed")
    finally:
        reshape._move = real

    stranded = staging_tabs()
    assert stranded, "staging tab was closed with a pane still in it"
    assert stranded[0]["tab_id"] in message, "the error does not name the staging tab"

    # recover by hand, the way the message tells a user to
    staging_id = stranded[0]["tab_id"]
    for pane_id in layouts.pane_ids(layout_of(staging_id)["root"]):
        if pane_id in ids:
            herdr.call("pane.move", pane_id=pane_id,
                       destination={"type": "tab", "tab_id": tab, "split": "right",
                                    "target_pane_id": anchor})
    for tab_info in staging_tabs():
        herdr.call("tab.close", tab_id=tab_info["tab_id"])
    assert sorted(layouts.pane_ids(layout_of(tab)["root"])) == sorted(ids), "a pane was lost"


@check("a zoomed tab is reshaped and left zoomed")
def _zoomed(tab):
    ids = layouts.pane_ids(layout_of(tab)["root"])
    herdr.call("pane.focus", pane_id=ids[0])
    herdr.call("pane.zoom", pane_id=ids[0], mode="on")
    current = layout_of(tab)
    assert current["zoomed"], "the tab did not zoom"
    other = "down" if current["root"]["direction"] == "right" else "right"
    assert reshape.reshape(current, layouts.tiled(ids, other)) is True
    after = layout_of(tab)
    assert after["zoomed"], "zoom was not restored"
    assert layouts.pane_ids(after["root"]) == ids, "pane order changed"
    herdr.call("pane.zoom", pane_id=ids[0], mode="off")


def build_scratch_tab():
    created = herdr.call("tab.create", label=LABEL, focus=False)
    tab_id = created["tab"]["tab_id"]
    root = created["root_pane"]["pane_id"]
    first = herdr.call("pane.split", target_pane_id=root, direction="right", cwd="/tmp")
    herdr.call("pane.split", target_pane_id=first["pane"]["pane_id"], direction="down", cwd="/tmp")
    return tab_id


def main():
    if os.environ.get("HERDR_ENV") != "1" and not os.path.exists(herdr.SOCKET_PATH):
        print("needs a running herdr session", file=sys.stderr)
        return 2

    tabs_before = tab_labels()
    focus_before = herdr.export()["layout"]["focused_pane_id"]
    tab = build_scratch_tab()
    failures = 0
    try:
        for name, fn in PASSED:
            try:
                fn(tab)
                print("ok   %s" % name)
            except Exception as exc:
                failures += 1
                print("FAIL %s\n     %s: %s" % (name, type(exc).__name__, exc))
    finally:
        for leftover in staging_tabs():
            print("note: closing leftover staging tab %s" % leftover["tab_id"])
            herdr.call("tab.close", tab_id=leftover["tab_id"])
        herdr.call("tab.close", tab_id=tab)
        herdr.call("pane.focus", pane_id=focus_before)

    if tab_labels() != tabs_before:
        print("FAIL the session did not come back clean: %s" % tabs_before)
        failures += 1
    print("%d/%d checks passed" % (len(PASSED) - failures, len(PASSED)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
