# herdr-panes

Dwindle-style splitting, master layout, and lossless pane geometry for [Herdr](https://herdr.dev).

早期开发中。设计见 [docs/design.md](docs/design.md)。

## Actions

| Action | Behavior | 状态 |
|---|---|---|
| `panes.smart-split` | Split the focused pane along its longer visual side | 骨架可用 |
| `panes.promote` | Swap the focused pane into the master position | 未实现 |
| `panes.master-width` | Cycle the master pane through 1/3, 1/2, 2/3 | 未实现 |
| `panes.equalize` | Equalize split ratios without moving processes when possible | 可用 |
| `panes.cycle` | Cycle the tab through layout presets | 未实现 |

## Install

```sh
herdr plugin link ~/github/herdr-panes
herdr server reload-config
```

## Keybindings

`prefix+v` 默认绑给内置的 `split_vertical`，先把它挪走：

```toml
[keys]
split_vertical = "prefix+shift+v"

[[keys.command]]
key = "prefix+v"
type = "plugin_action"
command = "panes.smart-split"
description = "smart split"

[[keys.command]]
key = "prefix+="
type = "plugin_action"
command = "panes.equalize"
description = "equalize"
```

## Test

```sh
python3 src/smart_split.py --check
python3 -m unittest discover -s test
```

## Requirements

- Herdr 0.9.0+
- Python 3.9+
- macOS or Linux
