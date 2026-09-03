## Purpose

提供类似 nrm 的命令行工作流，在用户级和项目级安全管理 uv 软件包索引，同时保留无关的 uv 配置。

## ADDED Requirements

### Requirement: 可安装的 uim 命令
项目 SHALL 提供可在 CPython 3.9 及以上受支持版本运行的 `uim` 命令，并且无需项目环境即可显示帮助和版本信息。

#### Scenario: 调用已安装命令
- **WHEN** 用户安装软件包并运行 `uim --help`
- **THEN** 命令显示可用命令并成功退出

#### Scenario: 显示版本
- **WHEN** 用户运行 `uim --version`
- **THEN** 命令显示已安装的 uim 版本并成功退出

### Requirement: 与 nrm 兼容的核心命令界面
CLI SHALL 提供 `ls`、`current`、`use`、`add`、`del`、`rename`、`home` 和 `test` 命令；凡 uv 存在等价行为时，其位置参数形式和常用选项应与 nrm 保持一致。

#### Scenario: 发现熟悉的命令
- **WHEN** nrm 用户运行 `uim --help`
- **THEN** 帮助以 nrm 的命令名列出核心命令

#### Scenario: 请求命令专属帮助
- **WHEN** 用户对核心命令运行 `uim <command> --help`
- **THEN** 命令显示其参数和选项并成功退出

### Requirement: 内置索引目录
系统 SHALL 提供 PyPI、清华、阿里云、腾讯、华为和中科大的内置条目，并使用 HTTPS PEP 503 Simple Repository 端点。

#### Scenario: 列出全新安装的目录
- **WHEN** 没有 uim 目录配置的用户运行 `uim ls`
- **THEN** 列出所有内置条目及其名称和 URL

#### Scenario: 保护内置条目
- **WHEN** 用户尝试删除或重命名内置条目
- **THEN** uim 拒绝操作、保持目录不变并返回非零退出状态

### Requirement: 自定义索引目录管理
系统 SHALL 允许用户在符合平台规范的用户级 uim 配置文件中添加、删除和重命名自定义索引条目，并可选配置主页。

#### Scenario: 添加自定义索引
- **WHEN** 用户运行 `uim add company https://packages.example.com/simple https://packages.example.com`
- **THEN** uim 校验并保存该自定义条目，使后续命令可以使用它

#### Scenario: 拒绝无效自定义索引
- **WHEN** 添加或重命名操作提供无效 URL、无效名称或重复的目标名称
- **THEN** uim 报告校验错误、不修改目录并返回非零退出状态

#### Scenario: 删除自定义索引
- **WHEN** 用户对未被任何受管理作用域选中的现有自定义条目运行 `uim del company`
- **THEN** uim 从目录中删除该条目

#### Scenario: 保护使用中的自定义索引
- **WHEN** 用户尝试删除 uim 管理配置当前选中的自定义条目
- **THEN** uim 拒绝删除，并说明必须先选择其他索引

### Requirement: 用户级索引切换
`uim use <name>` 命令 SHALL 将所选目录 URL 设置为 uv 的用户级默认索引，同时保留同一配置文件中的无关设置和索引。

#### Scenario: 切换用户默认索引
- **WHEN** 用户运行 `uim use tsinghua` 且不存在不安全的配置冲突
- **THEN** uv 用户配置使用清华 URL 作为默认索引，且 uim 报告成功

#### Scenario: 原地更新简单命名默认索引
- **WHEN** 用户级 `uv.toml` 的默认 `[[index]]` 只包含 `name`、`url` 和 `default = true`，且用户运行 `uim use aliyun`
- **THEN** uim 原地更新该条目的名称和 URL、保留结构化形式及无关配置，并报告成功

#### Scenario: 选择未知条目
- **WHEN** 用户运行 `uim use missing` 且目录中不存在 `missing`
- **THEN** uim 报告该条目未知、不修改配置并返回非零退出状态

#### Scenario: 交互式选择
- **WHEN** 用户在交互式终端中运行不带名称的 `uim use`
- **THEN** uim 提示用户从目录中选择并应用所选用户级索引

#### Scenario: 非交互使用时省略名称
- **WHEN** 标准输入不是交互终端且用户运行不带名称的 `uim use`
- **THEN** uim 报告名称必填、不修改配置并返回非零退出状态

### Requirement: 项目级索引切换
`uim use <name> --local` 命令 SHALL 为当前 uv 项目设置所选索引，且不修改用户级 uv 配置。

#### Scenario: 更新已有本地 uv.toml
- **WHEN** 当前项目解析到已有 `uv.toml`，且用户运行 `uim use aliyun --local`
- **THEN** uim 更新该文件的默认索引并保持用户配置不变

#### Scenario: 更新已有 pyproject.toml
- **WHEN** 不存在适用的 `uv.toml`、存在适用的 `pyproject.toml`，且用户运行 `uim use aliyun --local`
- **THEN** uim 更新该 `pyproject.toml` 中的 `[tool.uv]` 配置并保持用户配置不变

#### Scenario: 在现有项目之外创建本地配置
- **WHEN** 不存在适用的 `uv.toml` 或 `pyproject.toml`，且用户确认本地切换
- **THEN** uim 在当前目录创建包含所选默认索引的 `uv.toml`

### Requirement: 配置保留与原子性
每次切换 SHALL 保留注释、在可行范围内保留格式，并保留所有未被所请求默认索引变更直接取代的 uv 设置；目标文件 SHALL 以原子方式替换。

#### Scenario: 保留无关配置
- **WHEN** 目标配置包含无关设置、命名补充索引和注释
- **THEN** 切换默认索引后仍保留这些设置、索引和注释

#### Scenario: 中止失败写入
- **WHEN** 切换期间校验或文件系统替换失败
- **THEN** 原目标文件仍可使用，且 uim 返回非零退出状态

#### Scenario: 遇到不受管理的结构化默认项
- **WHEN** 目标包含标记为 `default = true` 且额外属性无法由简单默认索引切换安全表示的 `[[index]]` 条目
- **THEN** uim 报告冲突并保持文件不变，除非用户明确请求经过批准的覆盖模式

#### Scenario: 拒绝项目级命名默认项
- **WHEN** `pyproject.toml` 包含命名结构化默认索引，或目标索引名会与已有条目重复
- **THEN** uim 报告冲突并保持原文件逐字节不变

### Requirement: 报告实际生效的当前索引
`uim current` 命令 SHALL 按 uv 的环境、项目、用户和系统优先级确定当前目录实际生效的默认索引，并在可能时识别匹配的目录名称。

#### Scenario: 项目索引覆盖用户索引
- **WHEN** 当前项目选择阿里云，而用户配置选择 PyPI
- **THEN** `uim current` 报告 `aliyun`

#### Scenario: 显示生效 URL
- **WHEN** 用户运行 `uim current --show-url` 或 `uim current -u`
- **THEN** uim 显示实际生效的默认索引 URL，而不是目录名称

#### Scenario: 环境变量覆盖生效
- **WHEN** 受支持的 uv 默认索引环境变量覆盖持久配置
- **THEN** `uim current` 报告环境变量所选索引，且详细输出将环境变量标识为来源

#### Scenario: 生效 URL 未收录
- **WHEN** 生效的默认 URL 与任何目录条目都不匹配
- **THEN** `uim current` 显示该 URL，而不是虚构名称

### Requirement: 索引列表标识实际生效项
`uim ls` 命令 SHALL 显示所有目录条目，并标记与当前目录实际生效默认索引匹配的条目。

#### Scenario: 标记已选条目
- **WHEN** 生效索引与某个目录条目匹配且用户运行 `uim ls`
- **THEN** 只将该条目标记为当前项

#### Scenario: 没有目录条目匹配
- **WHEN** 生效索引不在目录中且用户运行 `uim ls`
- **THEN** 列出目录但不错误标记任何条目，并清晰报告生效的自定义 URL

### Requirement: 访问索引主页
`uim home <name> [browser]` 命令 SHALL 打开索引配置的主页；提供浏览器参数时使用指定浏览器，否则使用平台默认浏览器。

#### Scenario: 打开已配置主页
- **WHEN** 用户在交互式桌面环境中运行 `uim home pypi`
- **THEN** uim 请求平台打开 PyPI 配置的主页

#### Scenario: 主页不可用
- **WHEN** 索引没有主页或无法启动指定浏览器
- **THEN** uim 报告问题并返回非零退出状态

### Requirement: 索引可达性测试
`uim test [name]` 命令 SHALL 测量一个指定索引或全部目录条目的 HTTPS 可达性和响应延迟，不得修改配置或下载 Simple Repository 根索引。它 SHALL 探测配置的 Simple Repository URL 下的轻量项目端点，优先发出无响应体的 `HEAD` 请求，并且只有服务器明确不支持 `HEAD` 时才回退到受字节限制的 `GET`。

#### Scenario: 测试单个索引
- **WHEN** 用户运行 `uim test tsinghua`
- **THEN** uim 报告其 Simple Repository URL 下轻量项目端点是否成功响应，并在成功时包含耗时

#### Scenario: 测试全部索引
- **WHEN** 用户运行不带名称的 `uim test`
- **THEN** uim 并发测试目录条目、分别报告每项结果，并且不修改已选索引

#### Scenario: 避免下载根索引
- **WHEN** uim 测试的索引其 Simple Repository 根目录包含大型项目列表
- **THEN** uim 不对根索引发出 `GET`，也不读取无界响应体

#### Scenario: 服务器不支持 HEAD
- **WHEN** 轻量项目端点对 `HEAD` 返回 HTTP 405 或 501
- **THEN** uim 对同一项目端点使用 `Range: bytes=0-0` 重试 `GET`，且读取不超过一个响应字节

#### Scenario: 端点失败
- **WHEN** 端点超时、TLS 校验失败或返回不可接受的响应
- **THEN** uim 报告该条目失败，且不暴露输入 URL 中嵌入的凭据

### Requirement: 秘密安全行为
系统 SHALL NOT 将凭据持久化到 uim 目录、在正常输出中回显 URL 凭据，或在初始版本中实现独立的凭据存储。

#### Scenario: URL 包含凭据
- **WHEN** 用户尝试添加包含用户信息的索引 URL
- **THEN** uim 拒绝该 URL，并引导用户使用 uv 支持的认证方式

#### Scenario: 诊断错误包含敏感 URL
- **WHEN** HTTP 或解析错误引用包含敏感用户信息的 URL
- **THEN** uim 在显示错误前对敏感部分进行脱敏
