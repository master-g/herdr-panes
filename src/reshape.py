#!/usr/bin/env python3
"""Change a tab's shape without killing what runs in it (docs/design.md §4.3).

Same-tab pane.move is refused and layout.apply kills processes, so the only way
to move a pane within a tab is out to a staging tab and back. Every step here is
reversible, and a failure puts the tab back the way it was before raising: a
pane left parked in staging is worse than the layout the user asked to change.
"""

import herdr
import layouts

STAGING_LABEL = "panes-staging"


class ReshapeFailed(RuntimeError):
    pass


def _move(pane_id, **destination):
    # pane.move reports a refusal in the body, not as an error: same_tab when the
    # destination is where the pane already is, zoomed_tab when either end is zoomed.
    result = herdr.call("pane.move", pane_id=pane_id, destination=destination)["move_result"]
    if not result["changed"]:
        raise ReshapeFailed("pane.move %s refused: %s" % (pane_id, result.get("reason", "unknown")))


def _park(pane_ids, staging_id):
    for pane_id in pane_ids:
        _move(pane_id, type="tab", tab_id=staging_id, split="right")


def _rebuild(target, tab_id):
    for pane_id, target_pane_id, direction, ratio in layouts.insert_plan(target):
        _move(pane_id, type="tab", tab_id=tab_id, split=direction,
              target_pane_id=target_pane_id, ratio=ratio)


def _open_staging():
    created = herdr.call("tab.create", label=STAGING_LABEL, focus=False)
    # tab.create hands back a shell of its own, so staging is never empty
    return created["tab"]["tab_id"], created["root_pane"]["pane_id"]


def _close_staging(staging_id, own_pane):
    try:
        left = layouts.pane_ids(herdr.export(tab_id=staging_id)["layout"]["root"])
    except RuntimeError:
        return                                  # herdr dropped the tab already
    stranded = [p for p in left if p != own_pane]
    if stranded:
        raise ReshapeFailed("%d pane(s) stranded in staging tab %s: %s — not closing it"
                            % (len(stranded), staging_id, ", ".join(stranded)))
    herdr.call("tab.close", tab_id=staging_id)


def _rollback(tab_id, staging_id, original, anchor):
    try:
        here = layouts.pane_ids(herdr.export(tab_id=tab_id)["layout"]["root"])
        _park([p for p in here if p != anchor], staging_id)
        _rebuild(original, tab_id)
    except Exception as exc:
        raise ReshapeFailed("rollback failed (%s); panes may still be in staging tab %s"
                            % (exc, staging_id))


def reshape(layout, target):
    """Give the tab `target`'s shape. True when panes moved, False when nothing to do.

    The anchor — the pane in the master slot — is the one pane that never leaves
    the tab, so `target` has to keep it there. Every other pane is parked in a
    staging tab and moved back in insert_plan order.
    """
    tab_id, current = layout["tab_id"], layout["root"]
    anchor = layouts.first_pane(current)
    if layouts.first_pane(target) != anchor:
        raise ValueError("target would move %s out of the master slot" % anchor)
    if layouts.shape_equal(current, target):
        return False

    # a zoomed tab refuses pane.move at either end, so drop zoom and put it back
    zoomed = layout["focused_pane_id"] if layout.get("zoomed") else None
    if zoomed:
        herdr.call("pane.zoom", pane_id=zoomed, mode="off")
    staging_id, own_pane = _open_staging()
    try:
        _park([p for p in layouts.pane_ids(current) if p != anchor], staging_id)
        _rebuild(target, tab_id)
    except Exception:
        _rollback(tab_id, staging_id, current, anchor)
        _close_staging(staging_id, own_pane)
        _rezoom(zoomed)
        raise
    _close_staging(staging_id, own_pane)
    _rezoom(zoomed)
    return True


def _rezoom(pane_id):
    if pane_id:
        herdr.call("pane.zoom", pane_id=pane_id, mode="on")
