#!/usr/bin/env python3
"""User settings, read from the plugin's config dir (docs/design.md §4.5).

JSON rather than the TOML §4.5 first asked for: `tomllib` landed in 3.11 and
macOS still ships 3.9, so TOML would mean either a dependency or a hand-rolled
parser, and §3 rules out both. Environment variables are not an option either —
plugin actions are launched by the herdr server and inherit its environment, so
a user cannot set one.

A missing file means defaults. A broken one raises: silently ignoring settings
somebody wrote is worse than an action that says what is wrong.
"""

import json
import os

DEFAULTS = {
    "cell_aspect": 2.0,          # terminal cell height / width, tunes smart-split
    "preserve_split": False,     # inherit the parent split's direction instead
    "master_widths": [0.333, 0.5, 0.667],
    "cycle": ["columns", "rows"],
}


def path():
    directory = os.environ.get("HERDR_PLUGIN_CONFIG_DIR",
                               os.path.expanduser("~/.config/herdr/plugins/config/panes"))
    return os.path.join(directory, "config.json")


def _checked(where, value, default):
    """Coerce `value` to the shape of `default`, or say where it went wrong."""
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise ValueError("%s: expected true or false, got %r" % (where, value))
        return value
    if isinstance(default, float):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("%s: expected a number, got %r" % (where, value))
        return float(value)
    if isinstance(default, list):
        if not isinstance(value, list) or not value:
            raise ValueError("%s: expected a non-empty list, got %r" % (where, value))
        return [_checked("%s[%d]" % (where, index), item, default[0])
                for index, item in enumerate(value)]
    if not isinstance(value, str):
        raise ValueError("%s: expected a string, got %r" % (where, value))
    return value


def load(config_path=None):
    """Defaults merged with the user's file. Raises ValueError on a bad one."""
    config_path = config_path or path()
    try:
        handle = open(config_path)
    except (IOError, OSError):
        return dict(DEFAULTS)
    try:
        user = json.load(handle)
    except ValueError as exc:
        raise ValueError("%s is not valid JSON: %s" % (config_path, exc))
    finally:
        handle.close()

    if not isinstance(user, dict):
        raise ValueError("%s: expected an object at the top level" % config_path)
    unknown = sorted(set(user) - set(DEFAULTS))
    if unknown:
        raise ValueError("%s: unknown setting(s) %s; known: %s"
                         % (config_path, ", ".join(unknown), ", ".join(sorted(DEFAULTS))))

    settings = dict(DEFAULTS)
    for key, value in user.items():
        settings[key] = _checked("%s: %s" % (config_path, key), value, DEFAULTS[key])
    return settings
