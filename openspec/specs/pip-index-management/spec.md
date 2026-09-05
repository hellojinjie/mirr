# pip-index-management Specification

## Purpose

让用户以 mirr 已经为 uv 验证过的目录管理、原子写入和并发测速体验，安全地管理 pip 的包索引配置（用户级与 virtualenv 级）。

## Requirements

### Requirement: pip 内置索引目录
系统 SHALL 为 pip backend 提供 PyPI、清华、阿里云、腾讯、华为和中科大的内置条目，使用与 uv backend 相同的 HTTPS PEP 503 Simple Repository 端点。

#### Scenario: 列出全新安装的目录
- **WHEN** 没有 pip 自定义目录配置的用户运行 `mirr pip ls`
- **THEN** 列出所有内置条目及其名称和 URL

#### Scenario: 保护内置条目
- **WHEN** 用户尝试删除或重命名 pip 内置条目
- **THEN** mirr 拒绝操作、保持目录不变并返回非零退出状态

### Requirement: pip 自定义索引目录管理
系统 SHALL 允许用户在独立于其他工具的 pip 专属 mirr 配置文件中添加、删除和重命名自定义索引条目，并可选配置主页。

#### Scenario: 添加自定义索引
- **WHEN** 用户运行 `mirr pip add company https://packages.example.com/simple https://packages.example.com`
- **THEN** mirr 校验并保存该自定义条目到 pip 专属目录文件，使后续命令可以使用它

#### Scenario: 拒绝无效自定义索引
- **WHEN** 添加或重命名操作提供无效 URL、无效名称或重复的目标名称
- **THEN** mirr 报告校验错误、不修改目录并返回非零退出状态

#### Scenario: 删除自定义索引
- **WHEN** 用户对未被任何受管理作用域选中的现有自定义条目运行 `mirr pip del company`
- **THEN** mirr 从 pip 目录中删除该条目

#### Scenario: 保护使用中的自定义索引
- **WHEN** 用户尝试删除 mirr 管理配置当前选中的 pip 自定义条目
- **THEN** mirr 拒绝删除，并说明必须先选择其他索引

### Requirement: pip 用户级索引切换
`mirr pip use <name>` 命令 SHALL 将所选目录 URL 设置为 pip 的用户级 `index-url`，同时保留同一配置文件中的无关设置。

#### Scenario: 切换用户默认索引
- **WHEN** 用户运行 `mirr pip use tsinghua` 且不存在不安全的配置冲突
- **THEN** pip 用户配置文件的 `index-url` 更新为清华 URL，且 mirr 报告成功

#### Scenario: 选择未知条目
- **WHEN** 用户运行 `mirr pip use missing` 且目录中不存在 `missing`
- **THEN** mirr 报告该条目未知、不修改配置并返回非零退出状态

#### Scenario: 交互式选择
- **WHEN** 用户在交互式终端中运行不带名称的 `mirr pip use`
- **THEN** mirr 提示用户从目录中选择并应用所选用户级索引

#### Scenario: 非交互使用时省略名称
- **WHEN** 标准输入不是交互终端且用户运行不带名称的 `mirr pip use`
- **THEN** mirr 报告名称必填、不修改配置并返回非零退出状态

### Requirement: pip venv 级索引切换
`mirr pip use <name> --local` 命令 SHALL 在检测到已激活的 virtualenv 时，为该 virtualenv 设置所选索引且不修改用户级 pip 配置；未检测到已激活 virtualenv 时 SHALL 拒绝执行。

#### Scenario: 已激活 venv 时切换
- **WHEN** `VIRTUAL_ENV` 环境变量指向一个已激活的 virtualenv，且用户运行 `mirr pip use aliyun --local`
- **THEN** mirr 更新该 virtualenv 的 `pip.conf`（或平台等价文件）并保持用户级配置不变

#### Scenario: 未激活 venv 时拒绝
- **WHEN** `VIRTUAL_ENV` 环境变量未设置，且用户运行 `mirr pip use aliyun --local`
- **THEN** mirr 报告 `--local` 需要已激活的 virtualenv、不创建或修改任何文件，并返回非零退出状态

### Requirement: pip 配置保留与原子性
每次切换 SHALL 保留目标 pip 配置文件中未被所请求默认索引变更直接取代的无关设置、注释和格式；目标文件 SHALL 以原子方式替换。

#### Scenario: 保留无关配置
- **WHEN** 目标 pip 配置文件包含无关设置（如 `[global]` 下的 `timeout`）和注释
- **THEN** 切换默认索引后仍保留这些设置和注释

#### Scenario: 中止失败写入
- **WHEN** 切换期间校验或文件系统替换失败
- **THEN** 原目标文件仍可使用，且 mirr 返回非零退出状态

### Requirement: 报告 pip 实际生效的当前索引
`mirr pip current` 命令 SHALL 按 pip 的环境变量、virtualenv、用户和系统优先级确定当前目录实际生效的索引，并在可能时识别匹配的目录名称。

#### Scenario: venv 索引覆盖用户索引
- **WHEN** 当前已激活的 virtualenv 选择阿里云，而用户配置选择 PyPI
- **THEN** `mirr pip current` 报告 `aliyun`

#### Scenario: 显示生效 URL
- **WHEN** 用户运行 `mirr pip current --show-url` 或 `mirr pip current -u`
- **THEN** mirr 显示实际生效的索引 URL，而不是目录名称

#### Scenario: 环境变量覆盖生效
- **WHEN** `PIP_INDEX_URL` 或 `PIP_CONFIG_FILE` 覆盖持久配置
- **THEN** `mirr pip current` 报告环境变量所选索引，且详细输出将环境变量标识为来源

### Requirement: pip 索引列表标识实际生效项
`mirr pip ls` 命令 SHALL 显示所有目录条目，并标记与当前实际生效索引匹配的条目。

#### Scenario: 标记已选条目
- **WHEN** 生效索引与某个目录条目匹配且用户运行 `mirr pip ls`
- **THEN** 只将该条目标记为当前项

#### Scenario: 没有目录条目匹配
- **WHEN** 生效索引不在目录中且用户运行 `mirr pip ls`
- **THEN** 列出目录但不错误标记任何条目，并清晰报告生效的自定义 URL

### Requirement: pip 索引可达性测试
`mirr pip test [name]` 命令 SHALL 测量一个指定索引或全部目录条目的 HTTPS 可达性和响应延迟，不得修改配置或下载 Simple Repository 根索引；探测策略与 `mirr uv test` 一致（优先 `HEAD`，仅在服务器明确不支持时回退到受字节限制的 `GET`）。

#### Scenario: 测试单个索引
- **WHEN** 用户运行 `mirr pip test tsinghua`
- **THEN** mirr 报告其 Simple Repository URL 下轻量项目端点是否成功响应，并在成功时包含耗时

#### Scenario: 测试全部索引
- **WHEN** 用户运行不带名称的 `mirr pip test`
- **THEN** mirr 并发测试目录条目、分别报告每项结果，并且不修改已选索引

### Requirement: pip 秘密安全行为
系统 SHALL NOT 将凭据持久化到 pip 目录、在正常输出中回显 URL 凭据，或在初始版本中实现独立的凭据存储。

#### Scenario: URL 包含凭据
- **WHEN** 用户尝试添加包含用户信息的 pip 索引 URL
- **THEN** mirr 拒绝该 URL，并引导用户使用 pip 支持的认证方式

#### Scenario: 诊断错误包含敏感 URL
- **WHEN** HTTP 或解析错误引用包含敏感用户信息的 URL
- **THEN** mirr 在显示错误前对敏感部分进行脱敏
