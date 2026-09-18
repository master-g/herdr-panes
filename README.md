# herdr-panes

Dwindle-style splitting, master layout, and lossless pane geometry for [Herdr](https://herdr.dev).

早期开发中。设计见 [docs/design.md](docs/design.md)。

## Actions

| Action | Behavior | 状态 |
|---|---|---|
| `panes.smart-split` | Split the focused pane along its longer visual side | 骨架可用 |
| `panes.promote` | Swap the focused pane into the master position | 可用 |
| `panes.master-width` | Cycle the master pane through 1/3, 1/2, 2/3 | 可用 |
| `panes.equalize` | Equalize split ratios without moving processes when possible | 可用 |
| `panes.cycle` | Cycle the tab through layout presets | 可用 |

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

## Configuration

配置文件还没做，先用环境变量：

| 变量 | 默认 | 作用 |
|---|---|---|
| `HERDR_CELL_ASPECT` | `2.0` | 终端 cell 的高宽比，决定 smart-split 判断「视觉长边」的阈值。字体和行距会影响真实比例 |
| `HERDR_PANES_PRESERVE_SPLIT` | 关 | 打开后新切分继承焦点 pane 所在 split 的方向，列保持是列，而不是按长边重算 |
| `HERDR_PANES_MASTER_WIDTHS` | `0.333,0.5,0.667` | master-width 循环经过的比例，逗号分隔 |
| `HERDR_PANES_CYCLE` | `columns,rows` | cycle 经过的布局预设，逗号分隔。可选 `columns`（一排列）和 `rows`（一叠行） |

## Test

```sh
python3 src/smart_split.py --check
python3 -m unittest discover -s test
```

## Requirements

- Herdr 0.9.0+
- Python 3.9+
- macOS or Linux
