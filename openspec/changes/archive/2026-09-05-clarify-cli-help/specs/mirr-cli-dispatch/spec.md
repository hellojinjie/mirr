## ADDED Requirements

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
