# herdr-panes 设计文档

状态：初稿（2026-09-18）。目标是把上一轮调研的结论固化下来，下个会话不用重新查 API。

## 1. 这个插件要解决什么

herdr 开新 pane 必须显式选方向（`prefix+v` / `prefix+minus`），布局比例乱了只能进 resize mode 一格一格调。我们想要的是 hyprland / niri 那种"按一个键，方向自己算对"的手感，以及无损的几何调整。

**目标：**

- 一个键开 pane，方向按焦点 pane 的长边自动决定（hyprland dwindle 规则）。
- 主从布局：提升焦点 pane 为 master，master 宽度可循环。
- 无损的比例调整：能不搬进程就不搬。

**非目标（明确不做，理由见 §5）：**

- niri 的滚动式平铺。
- 用 `[[events]]` 做"新 pane 自动重排"。
- Windows 支持（v1 不做，升级路径见 §3）。

## 2. 已验证的 herdr API 事实

以下都在本机 herdr 0.9.1 / socket protocol 22 上核对过（`herdr api schema --json`），或来自 herdr.dev 官方文档。**这一节是后续所有设计决策的依据，改动前先回看。**

| 能力 | 方法 | 关键语义 |
|---|---|---|
| 导出布局树 | `layout.export` | 返回 BSP 树（`pane` / `split` 节点，方向只有 `right` / `down`），含 `zoomed`、`focused_pane_id` |
| 应用布局树 | `layout.apply` | **会杀进程。**先建新 tab 再关旧 tab，不保留 PTY、scrollback、运行中的进程。只能用于"从模板开新 tab" |
| 改分割比例 | `layout.set_split_ratio` | 参数 `{tab_id, path: [bool], ratio}`。**无损**，纯元数据，不动任何进程 |
| 交换 pane | `pane.swap` | **无损**。同 tab only，保留进程、pane id、split 形状和比例。支持方向式和显式 `source_pane_id`/`target_pane_id` |
| 移动 pane | `pane.move` | 跨 tab / 新 tab / 新 workspace。**同 tab 移动被拒**（`changed: false`, `reason: "same_tab"`）。zoomed 的源或目标返回 `reason: "zoomed_tab"` |
| 读几何 | `pane.layout` | 每个 pane 的 cell 矩形 + split 矩形/比例。实测本机满屏 tab = 280×69 cells |
| 读 cwd | `pane.get` | 返回 `cwd` 和 `foreground_cwd`（后者跟着 shell 的 `cd` 走，更准） |
| 开 pane | `pane.split` | `--direction right\|down`，可带 `--ratio` `--cwd` `--env` |
| 缩放 | `pane.zoom` | 有显式 `mode: "on" / "off"`，不必只靠 toggle |

**由此推出的核心结论：**

在保住运行中进程（agent！）的前提下，**改变拓扑的唯一手段是把 pane 移到临时 staging tab 再插回来**。`layout.apply` 不行（杀进程），同 tab `pane.move` 不行（被拒），`pane.swap` 不改拓扑。iurysza/herdr-pane-layouts 那套 staging 方案不是绕远路，是唯一解。

**反过来说：只要目标布局和当前布局的形状相同、只差比例，就完全不需要搬动任何东西**，逐个 `layout.set_split_ratio` 即可。这是我们相对现有插件最重要的改进点（§4.3）。

### 插件宿主约定

- 运行时命令的**工作目录是插件目录**，不是用户 pane 的目录。开新 pane 必须显式传 `--cwd`，否则新 pane 落在插件安装目录里。
- 注入的环境变量：`HERDR_SOCKET_PATH`、`HERDR_BIN_PATH`、`HERDR_ENV=1`、`HERDR_PLUGIN_ID`、`HERDR_PLUGIN_ROOT`、`HERDR_PLUGIN_CONFIG_DIR`、`HERDR_PLUGIN_STATE_DIR`、`HERDR_PLUGIN_CONTEXT_JSON`、`HERDR_PLUGIN_ACTION_ID`，以及可用时的 `HERDR_WORKSPACE_ID` / `HERDR_TAB_ID` / `HERDR_PANE_ID`。
- 用户配置放 `HERDR_PLUGIN_CONFIG_DIR`，运行时状态（含锁文件）放 `HERDR_PLUGIN_STATE_DIR`。**不要**往 `HERDR_PLUGIN_ROOT` 写东西，GitHub 安装的插件根目录是受管 checkout。
- 动作、pane、link handler 全部在 manifest 里静态声明，v1 没有运行时注册。
- `min_herdr_version` 决定 herdr 是否放行 link/install，用了哪个方法就诚实抬到那一版。

### 实测延迟

- `python3 src/*.py` 冷启动约 45ms。
- `herdr` CLI 单次往返 < 10ms。
- 结论：开 pane、equalize 这类低频动作走 CLI 完全够用；只有需要连发十几次调用的重排才值得直连 socket。

## 3. 技术选型

**语言：Python 3 + 纯标准库。**herdr 官方明确语言无关（"整个 herdr CLI 就是插件 API"）。选 Python 是因为分发零摩擦——`[[build]]` 是在用户机器上跑的，Rust/Go 意味着安装时要求本地有 cargo/go 工具链，这个成本远大于 45ms 冷启动。Bash 排除，这里有布局树递归。

**兼容到 Python 3.9。**macOS 自带 `/usr/bin/python3` 是 3.9.6，加 `from __future__ import annotations` 后 `dict[str, Any]` / `str | None` 这类写法在 3.9 上可用（已在 3.9.6 上实测导入通过）。写代码时避开 `match` 和 3.10+ 的运行时特性。

**传输：默认走 `HERDR_BIN_PATH` 调 CLI。**官方推荐，且跨 Unix socket / Windows 命名管道。只有当某个动作需要连续十几次调用时，才为那条路径引入裸 socket 客户端。**不要一上来就写传输抽象层**——那是为一个还不支持的平台做的抽象。

**Windows 升级路径：**全部动作走 CLI 即可支持，代价是重排类动作变慢。等有人要再说，manifest 里先只写 `["linux", "macos"]`。

## 4. 功能设计

### 4.1 smart-split（已实现骨架）

hyprland dwindle 规则：按焦点 pane 的**视觉**长边切。终端 cell 高宽比约 2:1，所以判据是 `width_cells >= height_cells * CELL_ASPECT`，而不是直接比 cell 数。

`CELL_ASPECT` 通过环境变量暴露，默认 2.0——字体和行距会影响真实比例，这个旋钮必须留着。

实现见 `src/smart_split.py`，三次 CLI 调用（`pane layout` → `pane get` → `pane split`），纯函数 `direction_for()` 带 `--check` 自检。

待做：`preserve_split`（新切分继承父级 split 方向，从 `layout.export` 找焦点 pane 的父节点读 `direction`）。

### 4.2 master 布局

- `promote`：把焦点 pane 和主位置 pane 做一次 `pane.swap`（显式 source/target 形式）。同 tab、保留进程、保留形状，零风险。这是 hyprland master 布局的核心交互。
- `master-width`：循环 1/3 → 1/2 → 2/3，走 `layout.set_split_ratio` 改根节点比例。同样无损。

### 4.3 equalize / cycle 的无损快路径

这是相对现有插件最大的改进。分派逻辑：

```
if shape_equal(current_root, target):      # 方向 + pane 顺序一致，只差比例
    for path, ratio in ratio_plan(target):
        layout.set_split_ratio(tab_id, path, ratio)     # 零迁移、零风险
else:
    reshape_via_staging(...)               # 只有拓扑真的变了才搬进程
```

命中的是最高频场景：连着向右 split 了三次、比例乱了，按 equalize——拓扑本来就对，只需要改比例。现有插件在这种情况下也会把 pane 搬进 staging tab 再搬回来。

`shape_equal` 和 `ratio_plan` 是新的非平凡纯函数，必须有单测。

### 4.4 zoom 处理

现有插件遇到 zoomed tab 直接报错让用户手动 unzoom。我们用 `pane.zoom mode=off` → 重排 → `mode=on`，两次多余调用换掉一个用户要手动处理的错误。

### 4.5 用户配置

`HERDR_PLUGIN_CONFIG_DIR/config.toml`：cell 高宽比、master 宽度预设列表、cycle 经过哪几个布局。不要硬编码 0.6 这类数字。

## 5. 明确不做的事，以及原因

**niri 的滚动式平铺。**herdr 的 tab 布局是一棵填满可视区域的 BSP 树，`layout.export` / `pane.layout` 的所有矩形都在 tab 的 `area` 之内，没有视口偏移、没有 off-screen 坐标。niri 的前提是"无限长条带 + 滑动视口"，这在 API 层面没有对应物。

唯一能让 pane 离开可视区又不杀进程的手段是 `pane.move` 到别的 tab，而滚动是连续高频操作：每滚一列就搬一次 pane，被搬的 pane 按新 tab 几何 resize，里面的 vim/agent 收到 SIGWINCH 重排，scrollback 按新宽度重新折行——滚回来时画面已经不是离开时那个了。这不是性能问题，是语义问题。加上没有动画 API，niri 的"滑动"感本身就不存在。

`consume` / `expel`（把 pane 并入/移出当前列）同理：同 tab move 被拒，必须走 staging 中转，每次操作都有失败窗口。

**`[[events]] on = "pane.created"` 自动重排。**事件是事后通知，而 split 没有 undo，补救手段只有再 move 一次，有竞态。会在用户没预期的时刻搬动正在跑的 agent。一个保护不住的自动化比手动按键差。

**接管 herdr 的布局引擎。**插件接管的是"你按的那个键"。其他路径创建的 pane——鼠标右键菜单、`herdr pane split`、`agent start`、worktree 打开——仍走 herdr 自己的逻辑。这是 v1 插件模型的边界，要全局改布局引擎得进 herdr 核心。

## 6. 键位接管

插件动作通过 `[[keys.command]] type = "plugin_action"` 绑定。要用 `prefix+v` 的话，把内置的 `split_vertical` 挪走（比如 `prefix+shift+v`）再绑插件动作。

> 待验证：`split_vertical = ""` 是否能解绑一个有默认值的内置键。文档里 `""` 用在"默认就没绑"的可选键上（`last_pane`、`next_workspace`），`remote_image_paste` 的注释写了 "empty disables"，但对有默认值的键没实测。改绑一定安全，优先用改绑。

## 7. 测试

沿用分层：纯函数（`direction_for`、`shape_equal`、`ratio_plan`、布局树代数）走 `unittest`，真实 session 行为走 `test/e2e_live.py`，必须在 herdr 里 link 后运行，验证重排后进程存活。e2e 进不了 CI。

CI 只跑 `python3 -m unittest discover -s test`。

## 8. 下个会话的待办

1. 实现 `layouts.py` 布局树代数 + `shape_equal` / `ratio_plan`。**从零写，不抄 iurysza/herdr-pane-layouts**——那个仓库没有 LICENSE 文件，而且 `shape_equal` / `ratio_plan` 本来就是新东西，重写成本低于确认授权。需要的函数：`pane` / `split` 构造器、`balanced`、`tiled`、`pane_ids`、`first_pane`、`same`、`shape_equal`、`ratio_plan`、`presets`。
2. 实现 equalize / cycle 的双路径分派（§4.3）。
3. 实现 promote / master-width（§4.2）。
4. 补 `preserve_split`（§4.1）。
5. 验证 §6 的解绑问题。
6. 决定许可证，写 README，打 GitHub topic `herdr-plugin` 上 marketplace。

## 9. 参考

- 插件授权指南：https://herdr.dev/docs/plugins/
- Socket API：https://herdr.dev/docs/socket-api/
- 本机 schema：`herdr api schema --json`
- 现有同类插件：https://github.com/iurysza/herdr-pane-layouts —— 只作为行为参照（它的 staging 重排方案验证了 §2 的结论），**不复制代码**，仓库无 LICENSE
