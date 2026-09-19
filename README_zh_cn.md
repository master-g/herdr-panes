# herdr-panes

为 [Herdr](https://herdr.dev) 提供 dwindle 式切分、master 布局，以及无损的 pane 几何调整。

[English](README.md)

五个动作都可用，纯标准库，Python 3.9+。设计与实现取舍见 [docs/design.md](docs/design.md)。

## Actions

| Action | 行为 |
|---|---|
| `herdr-panes.smart-split` | 沿焦点 pane 的视觉长边切分 |
| `herdr-panes.promote` | 把焦点 pane 换到 master 位置 |
| `herdr-panes.master-width` | 让 master pane 在 1/3、1/2、2/3 之间循环 |
| `herdr-panes.equalize` | 均分各处分割比例，尽量不移动进程 |
| `herdr-panes.cycle` | 让 tab 在若干布局预设间循环 |

除 `cycle` 需要改变拓扑时会把 pane 移动到临时 tab 再插回来之外，其余动作都只改分割比例或做一次 pane 交换 —— 不重启终端、不打断正在跑的进程。`cycle` 的重排任何一步失败都会把 tab 完整回滚。

## Install

```sh
herdr plugin link ~/github/herdr-panes
herdr server reload-config
```

## Keybindings

直接绑就行 —— `prefix+v` 虽然是内置 `split_vertical` 的默认键，但插件绑定会静默顶掉内置**默认值**，不用先挪开它：

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

唯一的例外：如果你在 `[keys]` 里**显式**把某个内置动作写成了同一个键（比如 `split_vertical = "prefix+v"`），那内置的赢、插件绑定被禁用，`herdr server reload-config` 会给出诊断 `prefix+v: kept keys.split_vertical, disabled keys.command[N].key`。这种情况把内置那行改掉或删掉即可。要彻底解绑一个内置键，赋空字符串：`split_vertical = ""`。

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

## License

MIT，见 [LICENSE](LICENSE)。

## Prior art

[iurysza/herdr-pane-layouts](https://github.com/iurysza/herdr-pane-layouts) 先走通了「把 pane 移到临时 tab 再插回来」这条路，证明在不重启进程的前提下改变 tab 拓扑是可行的。本插件独立编写，没有复制它的代码；两者的重叠来自 herdr 的 API 本身 —— 同 tab 的 `pane.move` 会被拒绝，所以中转是唯一解。

## Credits

- [masterg](https://github.com/master-g)
- Claude（Anthropic Claude Code）—— 结对开发：实现、实机验证、测试与文档
