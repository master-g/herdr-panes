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

可选，放在 `herdr plugin config-dir panes` 打印的目录里，文件名 `config.json`。不存在就用默认值；改完立即生效，不用重启 herdr。

```json
{
  "cell_aspect": 2.0,
  "preserve_split": false,
  "master_widths": [0.333, 0.5, 0.667],
  "cycle": ["columns", "rows"]
}
```

| 键 | 默认 | 作用 |
|---|---|---|
| `cell_aspect` | `2.0` | 终端 cell 的高宽比，决定 smart-split 判断「视觉长边」的阈值。字体和行距会影响真实比例 |
| `preserve_split` | `false` | 打开后新切分继承焦点 pane 所在 split 的方向，列保持是列，而不是按长边重算 |
| `master_widths` | `[0.333, 0.5, 0.667]` | master-width 循环经过的比例 |
| `cycle` | `["columns", "rows"]` | cycle 经过的布局预设。可选 `columns`（一排列）和 `rows`（一叠行） |

写错的键或坏掉的 JSON 会让动作直接失败并在 `herdr plugin log` 里说明哪个文件、哪一项不对，而不是悄悄忽略。

用环境变量配置行不通：插件动作由 herdr 服务端拉起，继承的是服务端环境，不是你 shell 的。

## Test

```sh
python3 src/smart_split.py --check          # 纯函数自检
python3 -m unittest discover -s test        # 单测，CI 只跑这个
python3 test/e2e_live.py                    # 实机检查，需要 herdr 在跑且插件已 link
```

`e2e_live.py` 在自己新建的临时 tab 里跑，不碰你正在看的 tab、不移动焦点，结束后关掉临时 tab 并把焦点还回原处。它包含两次故意注入的失败，用来确认重排出错时会完整回滚。

## Requirements

- Herdr 0.9.0+
- Python 3.9+
- macOS or Linux
