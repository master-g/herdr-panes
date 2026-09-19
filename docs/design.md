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
| 移动 pane | `pane.move` | 跨 tab / 新 tab / 新 workspace，目的地可带 `target_pane_id` + `split` + `ratio`，移动的 pane 落在新 split 的第二侧。**拒绝写在返回体里而不是抛错**：`changed: false` 加 `reason`，同 tab 是 `same_tab`，两端任一 zoomed 是 `zoomed_tab`。调用方必须查 `changed` |
| 读几何 | `pane.layout` | 每个 pane 的 cell 矩形 + split 矩形/比例。实测本机满屏 tab = 280×69 cells |
| 读 cwd | `pane.get` | 返回 `cwd` 和 `foreground_cwd`（后者跟着 shell 的 `cd` 走，更准） |
| 开 pane | `pane.split` | `--direction right\|down`，可带 `--ratio` `--cwd` `--env` |
| 新建 tab | `tab.create` | **自带一个 root pane**，所以 staging tab 永远不是空的。判断「可以关了」要认这个 pane |
| 关 tab | `tab.close` | tab 被搬空后 herdr 会自动关掉它，此时再 `tab.close` 报 `tab_not_found` |
| 缩放 | `pane.zoom` | 有显式 `mode: "on" / "off"`，不必只靠 toggle |

**由此推出的核心结论：**

**传输层事实（实测）：** 请求信封是 NDJSON —— 一行 `{"id", "method", "params"}`，回一行 `{"id", "result"}` 或 `{"id", "error": {"code", "message"}}`。`layout.export` 的树：`split` 节点带 `direction` / `ratio` / `first` / `second`，`pane` 节点带 `pane_id` / `cwd`。`layout.set_split_ratio` 的 `path` 是 `[bool]`，`[]` 指根 split。已在本机验证 `path=[] ratio=0.75` 精确生效、pane id 不变、改回 0.5 完全还原。

**插件动作里的 `--current` 跟随 herdr 会话焦点，不是调用者所在的 pane。** 从 A 标签页触发的动作会落在当时焦点所在的 B 标签页。绑键位时这是对的行为，但 e2e 测试不能假设动作作用于测试自己的 pane。

在保住运行中进程（agent！）的前提下，**改变拓扑的唯一手段是把 pane 移到临时 staging tab 再插回来**。`layout.apply` 不行（杀进程），同 tab `pane.move` 不行（被拒），`pane.swap` 不改拓扑。iurysza/herdr-pane-layouts 那套 staging 方案不是绕远路，是唯一解。

**反过来说：只要目标布局和当前布局的形状相同、只差比例，就完全不需要搬动任何东西**，逐个 `layout.set_split_ratio` 即可。这是我们相对现有插件最重要的改进点（§4.3）。

### 插件宿主约定

- 运行时命令的**工作目录是插件目录**，不是用户 pane 的目录。开新 pane 必须显式传 `--cwd`，否则新 pane 落在插件安装目录里。
- 注入的环境变量：`HERDR_SOCKET_PATH`、`HERDR_BIN_PATH`、`HERDR_ENV=1`、`HERDR_PLUGIN_ID`、`HERDR_PLUGIN_ROOT`、`HERDR_PLUGIN_CONFIG_DIR`、`HERDR_PLUGIN_STATE_DIR`、`HERDR_PLUGIN_CONTEXT_JSON`、`HERDR_PLUGIN_ACTION_ID`，以及可用时的 `HERDR_WORKSPACE_ID` / `HERDR_TAB_ID` / `HERDR_PANE_ID`。
- `HERDR_CONFIG_PATH` 可以覆盖 herdr 自己的 config.toml 路径（文档 Environment 一节有，`herdr --help` 里没写）。调试键位时用它比改用户的真配置安全，但正在跑的服务端已经读过自己的路径，`reload-config` 不换路径。
- 用户配置放 `HERDR_PLUGIN_CONFIG_DIR`，运行时状态（含锁文件）放 `HERDR_PLUGIN_STATE_DIR`。**不要**往 `HERDR_PLUGIN_ROOT` 写东西，GitHub 安装的插件根目录是受管 checkout。
- 动作、pane、link handler 全部在 manifest 里静态声明，v1 没有运行时注册。
- `min_herdr_version` 决定 herdr 是否放行 link/install，用了哪个方法就诚实抬到那一版。

### 实测延迟

- `python3 src/*.py` 冷启动约 45ms。
- `herdr` CLI 单次往返 < 10ms。
- `src/herdr.py` 的 socket 单次往返同量级。实测 equalize 动作全程 21ms（进程启动 + 一次 export + 两次 set_split_ratio）。 smart-split 从三次 CLI 子进程改成四次 socket 调用后，84ms → 21ms：省的是子进程，不是网络。
- 结论：延迟不是选传输的理由，有没有 CLI 入口才是（见 §3）。只有一次要连发十几次调用的重排，才值得考虑复用连接。

## 3. 技术选型

**语言：Python 3 + 纯标准库。**herdr 官方明确语言无关（"整个 herdr CLI 就是插件 API"）。选 Python 是因为分发零摩擦——`[[build]]` 是在用户机器上跑的，Rust/Go 意味着安装时要求本地有 cargo/go 工具链，这个成本远大于 45ms 冷启动。Bash 排除，这里有布局树递归。

**兼容到 Python 3.9。**macOS 自带 `/usr/bin/python3` 是 3.9.6，加 `from __future__ import annotations` 后 `dict[str, Any]` / `str | None` 这类写法在 3.9 上可用（已在 3.9.6 上实测导入通过）。写代码时避开 `match` 和 3.10+ 的运行时特性。

**传输：CLI + socket 两条路，按方法是否有 CLI 入口划分。**（2026-09-18 修正，原来写的是「默认 CLI，只有高频才走 socket」，不成立。）

实测 herdr 0.9.1：`layout.export`、`layout.apply`、`layout.set_split_ratio` 在 socket schema 里存在，但**没有任何 CLI 入口**——`herdr layout` 不是命令，`herdr api` 只有 `snapshot` / `schema`，`herdr pane resize` 是相对的 `--direction/--amount`，不是绝对的 `path + ratio`。所以 §4.1 的 preserve_split、§4.2 的 master-width、§4.3 的无损快路径都必须走 socket，这是前置条件而不是性能优化。

`pane.*` 有完整 CLI，继续走 `HERDR_BIN_PATH`。socket 客户端见 `src/herdr.py`，纯标准库 `socket` + `json`，约 30 行，不做传输抽象层。

**Windows 升级路径：**全部动作走 CLI 即可支持，代价是重排类动作变慢。等有人要再说，manifest 里先只写 `["linux", "macos"]`。

## 4. 功能设计

### 4.1 smart-split（已实现骨架）

hyprland dwindle 规则：按焦点 pane 的**视觉**长边切。终端 cell 高宽比约 2:1，所以判据是 `width_cells >= height_cells * CELL_ASPECT`，而不是直接比 cell 数。

`CELL_ASPECT` 通过环境变量暴露，默认 2.0——字体和行距会影响真实比例，这个旋钮必须留着。

实现见 `src/smart_split.py`，四次 socket 调用（`layout.export` → `pane.layout` → `pane.get` → `pane.split`），纯函数 `direction_for()` 带 `--check` 自检。

`preserve_split` 已实现：`HERDR_PANES_PRESERVE_SPLIT=1` 打开后，用 `layouts.parent_split()` 从导出树里找焦点 pane 的父 split，继承它的 `direction`；焦点 pane 独占整个 tab（没有父 split）时回落到长边判据。默认关，和 hyprland 一致。实测同一个 41×45 的 pane：默认切 `down`，打开后切 `right`。

### 4.2 master 布局

- `promote`（`src/promote.py`）：把焦点 pane 和主位置 pane 做一次 `pane.swap`（显式 source/target 形式）。同 tab、保留进程、保留形状，零风险。主位置就是 `pane_ids(root)[0]`。焦点 pane 已经在主位置时，和 `pane_ids(root)[1]` 交换，也就是降回栈里——hyprland 的 master 布局就是这个行为。实测三 pane 连按两次：`[A,B,C]` 焦点 C → `[C,B,A]` → `[B,C,A]`，**焦点始终跟着进程走而不是跟着位置走**。
- `master-width`（`src/master_width.py`）：`layouts.next_in_cycle()` 挑下一个比例，`layout.set_split_ratio(path=[])` 改根节点。无损，pane 顺序不变。预设走 `HERDR_PANES_MASTER_WIDTHS`，默认 `0.333,0.5,0.667`。用户手拖到 0.43 之后按一次会落到 0.5，而不是先跳回 0.333。
  - 根节点是 `down` split 时，改的其实是 master 的高度。同一个概念转 90°，没有为此分支。

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

**重排的实现（`src/reshape.py`）。**`pane.move` 可以带 `target_pane_id` + `split` + `ratio`，所以插回位置是可控的；被移动的 pane 永远落在新 split 的**第二**侧。由此推出插入顺序必须自外向内：开启一个 split 的，是这个 split 第二分支里的第一个 pane，它从当前占着这块区域的 pane 上切出去。`layouts.insert_plan()` 按这个规则出计划，`apply_insert()` 是它的镜像，单测拿两者对拍，确认任意目标树都能精确复原——包括朴素的从左往右插入到不了的「第一分支本身是 split」那种形状。

**anchor 不动。**主位置那个 pane 全程留在原 tab（tab 不能空），其余 pane 先全部停到 staging tab，再按计划插回。因此目标布局必须保持同一个 pane 在主位置，`reshape()` 会校验这一点。

**失败就全回滚。**任何一步失败，先把原 tab 里除 anchor 外的 pane 重新停到 staging，再按**原布局**的插入计划重建，然后才把异常抛出去。回滚本身也失败时**不关 staging tab**——里面是用户还在跑的进程，关掉就没了——错误消息里点名 tab id 供人工恢复。两种情况都实测过（见 §8）。

### 4.4 zoom 处理

**只有重排路径需要这个，现在由 `reshape.reshape()` 处理：**移动前 `mode="off"`，成功或回滚之后 `mode="on"`。实测（2026-09-18）：zoomed tab 上 `layout.set_split_ratio` 正常生效，zoom 状态也不变——比例是纯元数据，跟哪个 pane 正在放大无关。所以 §4.3 的快路径不用管 zoom，equalize 在 zoomed tab 上直接可用。

真要搬 pane 时（`pane.move` 对 zoomed 的源或目标回 `zoomed_tab`），才用 `pane.zoom mode=off` → 重排 → `mode=on`，两次多余调用换掉一个用户要手动处理的错误。现有插件是遇到 zoomed 就直接报错让用户手动 unzoom。

### 4.5 用户配置

`HERDR_PLUGIN_CONFIG_DIR/config.json`，实现见 `src/config.py`。四个键：`cell_aspect`、`preserve_split`、`master_widths`、`cycle`。不要硬编码 0.6 这类数字。

**改成 JSON 不是 TOML**（原计划是 TOML）：`tomllib` 是 3.11 才进标准库，`/usr/bin/python3` 3.9.6 上实测没有，而 §3 既要 3.9 又不许加依赖，自己写 TOML 子集解析器为了格式好看不划算。`json` 在 3.9 就有。

**不用环境变量**：manifest 的 action 只接受 `command` / `contexts` / `description` / `platforms` / `title`，没有 `env` 键；`plugin.action.invoke` 也只收 `action_id` / `context` / `plugin_id`。动作由服务端拉起继承服务端环境，用户设不了。这一点和 §2 宿主约定里「用户配置放 `HERDR_PLUGIN_CONFIG_DIR`」是一致的。

**坏配置直接报错**，不静默回落默认值：未知键会列出所有已知键，类型不符会指到具体项（列表还带下标），坏 JSON 会带上解析器的位置信息。消息里都有文件全路径，`herdr plugin log` 能看到。悄悄忽略用户写下的设置，比一个说清楚哪里错了的失败更糟。实测两种坏配置都会让动作 exit 1 并在日志里给出可操作的消息。

## 5. 明确不做的事，以及原因

**niri 的滚动式平铺。**herdr 的 tab 布局是一棵填满可视区域的 BSP 树，`layout.export` / `pane.layout` 的所有矩形都在 tab 的 `area` 之内，没有视口偏移、没有 off-screen 坐标。niri 的前提是"无限长条带 + 滑动视口"，这在 API 层面没有对应物。

唯一能让 pane 离开可视区又不杀进程的手段是 `pane.move` 到别的 tab，而滚动是连续高频操作：每滚一列就搬一次 pane，被搬的 pane 按新 tab 几何 resize，里面的 vim/agent 收到 SIGWINCH 重排，scrollback 按新宽度重新折行——滚回来时画面已经不是离开时那个了。这不是性能问题，是语义问题。加上没有动画 API，niri 的"滑动"感本身就不存在。

`consume` / `expel`（把 pane 并入/移出当前列）同理：同 tab move 被拒，必须走 staging 中转，每次操作都有失败窗口。

**`[[events]] on = "pane.created"` 自动重排。**事件是事后通知，而 split 没有 undo，补救手段只有再 move 一次，有竞态。会在用户没预期的时刻搬动正在跑的 agent。一个保护不住的自动化比手动按键差。

**接管 herdr 的布局引擎。**插件接管的是"你按的那个键"。其他路径创建的 pane——鼠标右键菜单、`herdr pane split`、`agent start`、worktree 打开——仍走 herdr 自己的逻辑。这是 v1 插件模型的边界，要全局改布局引擎得进 herdr 核心。

## 6. 键位接管

插件动作通过 `[[keys.command]] type = "plugin_action"` 绑定。**不需要先挪开内置键。**（2026-09-19 查证；原来这里写「先把 `split_vertical` 挪走」，是多余的一步。）

herdr 0.9.1 的键位解析（`src/config/keybinds.rs`）按 `for source in [User, Default]` 两轮注册，`[[keys.command]]` 在 User 轮注册。冲突处理在 `reject_binding()`：

```rust
if let Some(first_binding) = registry.conflict(binding) {
    if source == BindingSource::Default && first_binding.source == BindingSource::User {
        return true;            // 静默丢掉默认值，不产生诊断
    }
    // 其余情况：诊断 "<key>: kept <first_field>, disabled <field>"
}
```

由此得到三条规则，都实机核对过：

| 情况 | 结果 |
|---|---|
| 内置键保持默认 + 插件绑同一个键 | **插件赢**，内置默认值被静默丢弃，`reload-config` 零诊断 |
| `[keys]` 里显式把内置动作写成同一个键 + 插件也绑它 | **内置赢**，插件绑定被禁用，诊断 `prefix+v: kept keys.split_vertical, disabled keys.command[2].key` |
| `split_vertical = ""` | **确实能解绑**有默认值的内置键 |

第三条的机制：TOML 里写了这个键（哪怕值是空串）就会进 `KeysConfig::user_fields`（`src/config/model.rs` 的 `apply_field!` 用 `if let Some(value) = input.$field`），该字段因此是 User 来源；User 轮的 `parse_action_bindings()` 遇到空串 `continue`，产出零个绑定；Default 轮又被 `field_source!` 挡住不再套用默认值。键位于是空了。

原来的推断错在类比：`remote_image_paste` 的注释写了 "empty disables"，但它在 config reference 里的类型是 `string`，而 `split_vertical` / `last_pane` 是 `keybinding`，两者不是一回事。结论对，推理过程不成立。

**验证方式：**herdr 仓库在对应 tag 上是公开的（`raw.githubusercontent.com/herdrdev/herdr/v0.9.1/src/...`），读解析代码比试键位可靠。自动化试不出来：没有查询生效键位的 socket 方法；`pane.send_keys` 走 PTY 不经过键位层（实测发 `ctrl+backslash` 不会触发绑在它上面的插件动作）；`reload-config` 对默认值冲突也不报诊断。人工核对可以按 `prefix+?` 看帮助面板里的生效键位。

## 7. 测试

沿用分层：纯函数（`direction_for`、`shape_equal`、`ratio_plan`、`insert_plan`、布局树代数）走 `unittest`，51 个；真实 session 行为走 `test/e2e_live.py`，6 项检查，必须在 herdr 里 link 后运行。e2e 进不了 CI —— 文件名不匹配 `discover` 的 `test*.py`，所以 CI 命令不会误收它。

CI 只跑 `python3 -m unittest discover -s test`。

**e2e 的约束：**在自己新建的临时 tab 里跑，不碰用户正在看的 tab、不移动焦点，结束时关掉临时 tab、把焦点还回去，并核对 tab 列表与开始时一致。检查失败时清理照常执行。

**覆盖的是 `reshape.py`**，因为它是这个仓库里唯一会搬动别人运行中进程的代码：往返重排后形状精确匹配且 `pane.process_info` 的 `shell_pid` 全部不变（进程存活的直接证据）、形状已相同时一次 `pane.move` 都不发、目标挪走 anchor 时拒绝且不碰 tab、插回中途失败时形状和比例完全还原、回滚也失败时保留 staging tab 且错误消息点名它、zoomed tab 重排后 zoom 状态还原。

后两项靠猴补 `reshape._move` 在指定第几次调用上抛异常来触发。**这套检查本身验证过有效性**：把 `_rollback` 改成直接返回后重跑，第 4、5 项如期报 FAIL 并指出形状没还原，exit 1。

## 8. 下个会话的待办

已完成（2026-09-18）：

- smart-split 在真实 session 里跑通（link → invoke，exit 0，方向和 cwd 都正确）。
- `src/herdr.py` socket 客户端可用，`layout.export` / `layout.set_split_ratio` 都实测过。
- §6 的键位问题查清了（见该节）：不需要挪开内置键，插件绑定会顶掉内置默认值；`split_vertical = ""` 确实能解绑。
- `src/config.py` + 单测 15 个（§4.5）：JSON 配置取代环境变量，实测写文件后不重启服务端即生效（`master_widths` 换成 `[0.25, 0.75]`，动作走的就是新预设）。
- `src/reshape.py` + `src/cycle.py` + `panes.cycle` 动作（§4.3 §4.4）。真实会话实测：`(right A (down B C))` 连按三次 → columns → rows → columns，pane 顺序和进程都不变，没有 staging 残留，每次约 55ms。注入失败也实测过两种：插回阶段中途失败 → 形状和比例完全还原、staging 关掉；连回滚都失败 → staging 保留（错误消息点名 tab id），原 tab 不被进一步破坏。
- `src/promote.py` / `src/master_width.py` + 对应动作（§4.2），以及 `smart_split.py` 的 `preserve_split`（§4.1）。`layouts.py` 补了 `parent_split` / `next_in_cycle`。
- `src/equalize.py` + manifest 的 `panes.equalize` 动作：走 §4.3 快路径，真实会话里把 0.82/0.17 拉回 0.5/0.5，pane 顺序不变、进程不动，zoomed 下同样生效。动作耗时 21ms。
- `src/layouts.py` 布局树代数从零写完（没抄 iurysza/herdr-pane-layouts，那仓库无 LICENSE）：`pane` / `split` 构造器、`pane_ids`、`splits`、`shape_equal`、`ratio_plan`、`balanced`、`tiled`。单测（现 26 个）在 3.14.7 和 3.9.6 上都通过，并已在真实 tab 上闭环验证：`ratio_plan` 的计划逐条发给 `set_split_ratio` 后 ratio 精确命中、pane 顺序不变、重跑得空计划。
  - 原清单里的 `first_pane` / `same` / `presets` 没写。`first_pane` 就是 `pane_ids(root)[0]`，`same` 被 `shape_equal` 覆盖，`presets` 要等 §4.5 的配置格式定下来才有内容。
  - 也没写 `dwindle` 预设：smart-split 本来就按 dwindle 规则长出来，不需要再把它构造成目标树。

1. 上 marketplace。许可证已定：MIT（`LICENSE`，2026 masterg）。marketplace 的条件是**公开仓库** + GitHub topic `herdr-plugin` + 默认分支上有能解析出必需元数据的 `herdr-plugin.toml`（可在根目录或子目录），索引每 30 分钟自动刷新。manifest 没有 `license` 字段，所以不用改 manifest。剩下的都是仓库层面的动作：建远端、推上去、打 topic。

## 9. 参考

- 插件授权指南：https://herdr.dev/docs/plugins/
- Socket API：https://herdr.dev/docs/socket-api/
- 本机 schema：`herdr api schema --json`
- 现有同类插件：https://github.com/iurysza/herdr-pane-layouts —— 只作为行为参照（它的 staging 重排方案验证了 §2 的结论），**不复制代码**，仓库无 LICENSE
