#!/usr/bin/env python3
"""Minimal socket client for the herdr API.

The CLI covers most of what we need, but layout.export / layout.set_split_ratio
have no CLI entry point, so lossless ratio work has to go over the socket.
"""

import json
import os
import socket
import sys

SOCKET_PATH = os.environ.get("HERDR_SOCKET_PATH", os.path.expanduser("~/.config/herdr/herdr.sock"))


def call(method, **params):
    """Send one request, return its result. Raises RuntimeError on an API error."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(SOCKET_PATH)
        sock.sendall(json.dumps({"id": method, "method": method, "params": params}).encode() + b"\n")
        buf = b""
        while b"\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                raise RuntimeError("herdr closed the socket before replying to %s" % method)
            buf += chunk
    reply = json.loads(buf.split(b"\n", 1)[0])
    if "error" in reply:
        raise RuntimeError("%s: %s" % (reply["error"]["code"], reply["error"]["message"]))
    return reply["result"]


def export(tab_id=None, pane_id=None):
    """Return the BSP tree for a tab (defaults to the focused one)."""
    return call("layout.export", tab_id=tab_id, pane_id=pane_id)


def set_split_ratio(path, ratio, tab_id=None, pane_id=None):
    """Move one split's ratio. Metadata only: no pane is moved, no process dies."""
    return call("layout.set_split_ratio", path=path, ratio=ratio, tab_id=tab_id, pane_id=pane_id)


if __name__ == "__main__":
    # ponytail: the live round trip is the check — it exercises connect, framing and parsing
    print(json.dumps(export(sys.argv[1] if len(sys.argv) > 1 else None), indent=2))
