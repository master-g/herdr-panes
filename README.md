# herdr-panes

Dwindle-style splitting, master layout, and lossless pane geometry for [Herdr](https://herdr.dev).

[中文说明 / Chinese](README_zh_cn.md)

All five actions work, standard library only, Python 3.9+. Design and implementation trade-offs are in [docs/design.md](docs/design.md).

## Actions

| Action | Behavior |
|---|---|
| `herdr-panes.smart-split` | Split the focused pane along its longer visual side |
| `herdr-panes.promote` | Swap the focused pane into the master position |
| `herdr-panes.master-width` | Cycle the master pane through 1/3, 1/2, 2/3 |
| `herdr-panes.equalize` | Equalize split ratios without moving processes when possible |
| `herdr-panes.cycle` | Cycle the tab through layout presets |

Except for `cycle`, which moves panes to a scratch tab and back when the topology has to change, every action only adjusts split ratios or performs a single pane swap — no terminal restarts, no interrupted processes. If any step of a `cycle` reshape fails, the whole tab is rolled back.

## Install

```sh
herdr plugin link ~/github/herdr-panes
herdr server reload-config
```

## Keybindings

Just bind them. `prefix+v` is the default key for the built-in `split_vertical`, but a plugin binding silently overrides a built-in **default**, so you don't have to move it out of the way first:

```toml
[[keys.command]]
key = "prefix+v"
type = "plugin_action"
command = "herdr-panes.smart-split"
description = "smart split"

[[keys.command]]
key = "prefix+="
type = "plugin_action"
command = "herdr-panes.equalize"
description = "equalize"
```

The one exception: if you **explicitly** assigned the same key to a built-in action under `[keys]` (say `split_vertical = "prefix+v"`), the built-in wins and the plugin binding is disabled. `herdr server reload-config` then reports `prefix+v: kept keys.split_vertical, disabled keys.command[N].key`. Change or delete that built-in line to fix it. To unbind a built-in key entirely, assign an empty string: `split_vertical = ""`.

## Configuration

Optional. Put a `config.json` in the directory printed by `herdr plugin config-dir panes`. Defaults apply when the file is absent; edits take effect immediately, no herdr restart needed.

```json
{
  "cell_aspect": 2.0,
  "preserve_split": false,
  "master_widths": [0.333, 0.5, 0.667],
  "cycle": ["columns", "rows"]
}
```

| Key | Default | Purpose |
|---|---|---|
| `cell_aspect` | `2.0` | Height-to-width ratio of a terminal cell, which sets the threshold smart-split uses to decide the "longer visual side". Font and line spacing affect the real ratio |
| `preserve_split` | `false` | When on, a new split inherits the direction of the split the focused pane lives in — a column stays a column instead of being recomputed from the longer side |
| `master_widths` | `[0.333, 0.5, 0.667]` | Ratios master-width cycles through |
| `cycle` | `["columns", "rows"]` | Layout presets cycle walks through. Available: `columns` (one row of columns) and `rows` (one stack of rows) |

An unknown key or broken JSON makes the action fail outright and explains which file and which entry is wrong in `herdr plugin log`, rather than being silently ignored.

Environment variables don't work for configuration: plugin actions are launched by the herdr server and inherit the server's environment, not your shell's.

## Test

```sh
python3 src/smart_split.py --check          # pure-function self-check
python3 -m unittest discover -s test        # unit tests, the only thing CI runs
python3 test/e2e_live.py                    # live check, needs herdr running and the plugin linked
```

`e2e_live.py` runs in a scratch tab it creates itself: it never touches the tab you are looking at, never moves focus, and closes the scratch tab and restores focus when it finishes. It includes two deliberately injected failures to confirm a failed reshape rolls back completely.

## Requirements

- Herdr 0.9.0+
- Python 3.9+
- macOS or Linux

## License

MIT, see [LICENSE](LICENSE).

## Prior art

[iurysza/herdr-pane-layouts](https://github.com/iurysza/herdr-pane-layouts) first made the "move panes to a scratch tab and back" route work, proving a tab's topology can change without restarting processes. This plugin was written independently and copies none of its code; the overlap comes from herdr's API itself — `pane.move` within the same tab is rejected, so a detour is the only option.

## Credits

- [masterg](https://github.com/master-g)
- Claude (Anthropic Claude Code) — pair development: implementation, live verification, tests and docs
