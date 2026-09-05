# mirr-cli-dispatch Specification

## Purpose

定义 `mirr <tool> <verb>` 的统一命令路由框架，以及历史上无 tool 前缀命令继续等价于 `mirr uv <verb>` 的向后兼容别名行为，让用户和已有脚本在新旧命令形态之间自由切换而不改变结果。

## Requirements

### Requirement: 支持的工具集合
mirr SHALL 将 `uv`、`pip`、`npm`、`conda` 识别为有效的 `<tool>` 值。

#### Scenario: 请求未知工具
- **WHEN** 用户运行 `mirr foo ls`，其中 `foo` 不是已识别的工具
- **THEN** mirr 报告 `foo` 不是受支持的工具、列出受支持的工具名称，并返回非零退出状态

### Requirement: 工具前缀命令路由
`mirr <tool> <verb> [args]` SHALL 将执行委派给对应工具的 backend 实现；每个工具 SHALL 仅暴露自己实际支持的 verb 子集。

#### Scenario: 执行受支持的 verb
- **WHEN** 用户运行 `mirr npm use taobao`
- **THEN** mirr 调用 npm backend 的 `use` 实现，产生的效果与该 backend 独立描述的行为一致

#### Scenario: 请求某工具未实现的 verb
- **WHEN** 用户运行某工具未实现的 verb（例如本版本中 `mirr conda use`）
- **THEN** mirr 返回该 verb 对应工具的明确"暂不支持"消息和非零退出状态，而不是通用的命令未找到错误

### Requirement: 向后兼容别名
无 `<tool>` 前缀的历史命令（`ls`、`current`、`use`、`add`、`del`、`rename`、`home`、`test`）SHALL 继续可用，且其行为 SHALL 与 `mirr uv <verb>` 完全一致，包括参数形式、输出格式和退出状态。

#### Scenario: 别名与显式前缀等价
- **WHEN** 用户分别运行 `mirr use tsinghua` 和 `mirr uv use tsinghua`（在相同的初始状态下）
- **THEN** 两者对 uv 配置产生完全相同的结果，且输出信息一致

#### Scenario: 别名不被视为废弃
- **WHEN** 用户运行 `mirr --help`
- **THEN** 帮助信息既展示无前缀的别名命令，也展示 `uv`/`pip`/`npm`/`conda` 工具入口，不将别名标记为已弃用

### Requirement: 工具专属帮助
`mirr <tool> --help` SHALL 只列出该工具实际支持的 verb 及其参数说明。

#### Scenario: 查看部分支持工具的帮助
- **WHEN** 用户运行 `mirr conda --help`
- **THEN** 帮助信息只列出 `ls` 和 `test`，不列出该工具本版本未实现的 verb

### Requirement: 输出标注所属工具
命令产生的每一行提示、状态和错误消息 SHALL 以 `[<tool>] ` 为前缀标注其所属工具，让用户能够区分同时操作多个工具时各条输出对应哪一个；无 `<tool>` 前缀的历史命令 SHALL 标注为 `[uv]`，与 `mirr uv <verb>` 保持一致。

#### Scenario: 状态消息标注工具
- **WHEN** 用户运行 `mirr npm use npmmirror`
- **THEN** mirr 输出以 `[npm] ` 开头的成功消息

#### Scenario: 列表与测速的每一行都标注工具
- **WHEN** 用户运行 `mirr pip ls` 或 `mirr pip test`
- **THEN** 输出的每一行(包括每个目录条目)都以 `[pip] ` 开头

#### Scenario: 历史别名标注为 uv
- **WHEN** 用户运行不带前缀的 `mirr use tsinghua`
- **THEN** mirr 输出以 `[uv] ` 开头，与 `mirr uv use tsinghua` 完全一致

### Requirement: 顶层帮助展示工具分组与默认工具
`mirr --help` SHALL 在 `Usage:` 行中将工具槽位显式命名为 `[PACKAGE TOOL]`（而非 Click 默认的通用 `COMMAND [ARGS]...`），SHALL 将命令列表分为"Package tools"（工具入口）和"Commands"（无前缀别名）两组分别展示，并 SHALL 附带说明支持哪些工具、省略 `[PACKAGE TOOL]` 时默认使用哪个工具的提示文字。

#### Scenario: Usage 行显式命名工具槽位
- **WHEN** 用户运行 `mirr --help`
- **THEN** 输出的 `Usage:` 行为 `mirr [OPTIONS] [PACKAGE TOOL] COMMAND [ARGS]...`

#### Scenario: 命令列表按工具入口与别名分组
- **WHEN** 用户运行 `mirr --help`
- **THEN** 输出包含标题为 `Package tools`（列出 `uv`/`pip`/`npm`/`conda`）和标题为 `Commands`（列出 `ls`/`current`/`use`/`add`/`del`/`rename`/`home`/`test`）的两个分组，而不是单一的字母序混合列表

#### Scenario: 提示支持的工具与默认工具
- **WHEN** 用户运行 `mirr --help`
- **THEN** 输出说明支持的工具集合（`uv`/`pip`/`npm`/`conda`）、省略 `[PACKAGE TOOL]` 时默认使用 `uv`，并指出可用 `mirr <tool> --help` 查看该工具实际支持的命令
