## Purpose

让用户以 mirr 已经为 uv 验证过的目录管理、原子写入和并发测速体验，安全地管理 npm 的 registry 配置（用户级与项目级）。

## ADDED Requirements

### Requirement: npm 内置 registry 目录
系统 SHALL 为 npm backend 提供官方 registry 及淘宝/npmmirror、腾讯、华为等国内镜像的内置条目。

#### Scenario: 列出全新安装的目录
- **WHEN** 没有 npm 自定义目录配置的用户运行 `mirr npm ls`
- **THEN** 列出所有内置条目及其名称和 URL

#### Scenario: 保护内置条目
- **WHEN** 用户尝试删除或重命名 npm 内置条目
- **THEN** mirr 拒绝操作、保持目录不变并返回非零退出状态

### Requirement: npm 自定义 registry 目录管理
系统 SHALL 允许用户在独立于其他工具的 npm 专属 mirr 配置文件中添加、删除和重命名自定义 registry 条目，并可选配置主页。

#### Scenario: 添加自定义 registry
- **WHEN** 用户运行 `mirr npm add company https://npm.example.com https://npm.example.com/home`
- **THEN** mirr 校验并保存该自定义条目到 npm 专属目录文件，使后续命令可以使用它

#### Scenario: 拒绝无效自定义 registry
- **WHEN** 添加或重命名操作提供无效 URL、无效名称或重复的目标名称
- **THEN** mirr 报告校验错误、不修改目录并返回非零退出状态

#### Scenario: 删除自定义 registry
- **WHEN** 用户对未被任何受管理作用域选中的现有自定义条目运行 `mirr npm del company`
- **THEN** mirr 从 npm 目录中删除该条目

#### Scenario: 保护使用中的自定义 registry
- **WHEN** 用户尝试删除 mirr 管理配置当前选中的 npm 自定义条目
- **THEN** mirr 拒绝删除，并说明必须先选择其他 registry

### Requirement: npm 用户级 registry 切换
`mirr npm use <name>` 命令 SHALL 将所选目录 URL 设置为 `~/.npmrc` 中的 `registry`，同时保留同一文件中的无关设置。

#### Scenario: 切换用户默认 registry
- **WHEN** 用户运行 `mirr npm use taobao` 且不存在不安全的配置冲突
- **THEN** 用户级 `.npmrc` 的 `registry` 更新为对应 URL，且 mirr 报告成功

#### Scenario: 选择未知条目
- **WHEN** 用户运行 `mirr npm use missing` 且目录中不存在 `missing`
- **THEN** mirr 报告该条目未知、不修改配置并返回非零退出状态

#### Scenario: 交互式选择
- **WHEN** 用户在交互式终端中运行不带名称的 `mirr npm use`
- **THEN** mirr 提示用户从目录中选择并应用所选用户级 registry

#### Scenario: 非交互使用时省略名称
- **WHEN** 标准输入不是交互终端且用户运行不带名称的 `mirr npm use`
- **THEN** mirr 报告名称必填、不修改配置并返回非零退出状态

### Requirement: npm 项目级 registry 切换
`mirr npm use <name> --local` 命令 SHALL 为当前目录的项目级 `.npmrc` 设置所选 registry，且不修改用户级 `.npmrc`。

#### Scenario: 更新已有项目 .npmrc
- **WHEN** 当前目录已存在 `.npmrc`，且用户运行 `mirr npm use taobao --local`
- **THEN** mirr 更新该文件的 `registry` 并保持用户级配置不变

#### Scenario: 在当前目录创建项目 .npmrc
- **WHEN** 当前目录不存在 `.npmrc`，且用户确认创建
- **THEN** mirr 在当前目录创建包含所选 registry 的 `.npmrc`

### Requirement: npm 配置保留与原子性
每次切换 SHALL 保留目标 `.npmrc` 中未被所请求 registry 变更直接取代的无关设置（包括 scope 覆盖条目，如 `@corp:registry=`）和注释；目标文件 SHALL 以原子方式替换。

#### Scenario: 保留无关配置
- **WHEN** 目标 `.npmrc` 包含无关设置、scope 覆盖条目和注释
- **THEN** 切换默认 registry 后仍保留这些设置、条目和注释

#### Scenario: 中止失败写入
- **WHEN** 切换期间校验或文件系统替换失败
- **THEN** 原目标文件仍可使用，且 mirr 返回非零退出状态

### Requirement: 报告 npm 实际生效的当前 registry
`mirr npm current` 命令 SHALL 按 npm 的环境变量、项目、用户和全局优先级确定当前目录实际生效的 registry，并在可能时识别匹配的目录名称。

#### Scenario: 项目 registry 覆盖用户 registry
- **WHEN** 当前项目 `.npmrc` 选择淘宝，而用户 `.npmrc` 选择官方源
- **THEN** `mirr npm current` 报告 `taobao`

#### Scenario: 显示生效 URL
- **WHEN** 用户运行 `mirr npm current --show-url` 或 `mirr npm current -u`
- **THEN** mirr 显示实际生效的 registry URL，而不是目录名称

#### Scenario: 环境变量覆盖生效
- **WHEN** `npm_config_registry` 环境变量覆盖持久配置
- **THEN** `mirr npm current` 报告环境变量所选 registry，且详细输出将环境变量标识为来源

### Requirement: npm 目录列表标识实际生效项
`mirr npm ls` 命令 SHALL 显示所有目录条目，并标记与当前实际生效 registry 匹配的条目。

#### Scenario: 标记已选条目
- **WHEN** 生效 registry 与某个目录条目匹配且用户运行 `mirr npm ls`
- **THEN** 只将该条目标记为当前项

#### Scenario: 没有目录条目匹配
- **WHEN** 生效 registry 不在目录中且用户运行 `mirr npm ls`
- **THEN** 列出目录但不错误标记任何条目，并清晰报告生效的自定义 URL

### Requirement: npm registry 可达性测试
`mirr npm test [name]` 命令 SHALL 测量一个指定 registry 或全部目录条目的 HTTPS 可达性和响应延迟，不得修改配置；探测策略优先 `HEAD`，仅在服务器明确不支持时回退到受字节限制的 `GET`。

#### Scenario: 测试单个 registry
- **WHEN** 用户运行 `mirr npm test taobao`
- **THEN** mirr 报告其注册表根端点是否成功响应，并在成功时包含耗时

#### Scenario: 测试全部 registry
- **WHEN** 用户运行不带名称的 `mirr npm test`
- **THEN** mirr 并发测试目录条目、分别报告每项结果，并且不修改已选 registry

### Requirement: npm 秘密安全行为
系统 SHALL NOT 将凭据（包括 `_authToken` 等 npm 专属凭据字段）持久化到 npm 目录、在正常输出中回显 URL 或凭据字段，或在初始版本中实现独立的凭据存储。

#### Scenario: URL 包含凭据
- **WHEN** 用户尝试添加包含用户信息的 npm registry URL
- **THEN** mirr 拒绝该 URL，并引导用户使用 npm 支持的认证方式（如 `.npmrc` 中的 `_authToken`）

#### Scenario: 诊断错误包含敏感 URL
- **WHEN** HTTP 或解析错误引用包含敏感用户信息的 URL
- **THEN** mirr 在显示错误前对敏感部分进行脱敏
