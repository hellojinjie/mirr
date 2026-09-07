## Purpose

为没有 Python/uv 环境、只装了 Node/npm 的用户，提供一个独立、零依赖的 `mirr` 可执行文件，用来查看和切换用户级 npm registry，覆盖内置镜像表中最常用的查看/切换/测速场景。

## ADDED Requirements

### Requirement: 内置 npm registry 目录
系统 SHALL 提供官方 registry 及淘宝/npmmirror、腾讯、华为等国内镜像的内置条目（`npmjs`、`npmmirror`、`tencent`、`huawei`）。本能力不提供任何自定义目录管理（无 `add`/`del`/`rename`），因此目录内容固定为这些内置条目。

#### Scenario: 列出内置目录
- **WHEN** 用户运行 `mirr ls`
- **THEN** 列出所有内置条目的名称和 URL，并标记与当前生效 registry 匹配的条目

#### Scenario: 生效值不在内置目录中
- **WHEN** 当前生效 registry 的 URL 不匹配任何内置条目，用户运行 `mirr ls`
- **THEN** 正常列出内置目录，不错误标记任何条目，并额外报告当前生效的 URL

### Requirement: 用户级 registry 切换
`mirr use <name>` 命令 SHALL 将所选内置条目的 URL 设置为 `~/.npmrc` 中的 `registry`，同时保留该文件中的无关设置；本能力不提供项目级（`--local`）切换。

#### Scenario: 切换成功
- **WHEN** 用户运行 `mirr use taobao`（或其他内置条目名）
- **THEN** `~/.npmrc` 的 `registry` 更新为对应 URL，命令报告成功

#### Scenario: 选择未知条目
- **WHEN** 用户运行 `mirr use missing` 且内置目录中不存在 `missing`
- **THEN** 命令报告该条目未知、不修改 `~/.npmrc`，并以非零状态退出

#### Scenario: 缺少名称参数
- **WHEN** 用户运行不带名称的 `mirr use`（无论标准输入是否为交互终端）
- **THEN** 命令报告名称为必填参数、不修改配置、不进入任何交互式选择流程，并以非零状态退出

### Requirement: 用户级配置保留与原子性
每次 `mirr use` 切换 SHALL 保留 `~/.npmrc` 中未被本次变更直接取代的无关设置（包括 `@scope:registry=` 这类作用域覆盖）和注释；文件 SHALL 以原子方式替换（写入同目录临时文件后原子改名，不产生中间可见的半写状态）。

#### Scenario: 保留无关配置
- **WHEN** `~/.npmrc` 包含无关设置、`@scope:registry=` 覆盖条目和注释
- **THEN** 切换默认 registry 后，这些设置、条目和注释原样保留

#### Scenario: `~/.npmrc` 尚不存在
- **WHEN** 用户运行 `mirr use <name>` 时 `~/.npmrc` 不存在
- **THEN** 命令创建该文件并写入所选 `registry`，不要求额外确认

### Requirement: 报告当前生效的用户级 registry
`mirr current` 命令 SHALL 按 `npm_config_registry` 环境变量、`~/.npmrc`、官方默认值（`https://registry.npmjs.org`）的顺序解析当前生效 registry，并在可能时识别匹配的内置条目名称；本能力不读取当前工作目录下的项目级 `.npmrc`。

#### Scenario: 显示生效条目名称
- **WHEN** `~/.npmrc` 选择了某个内置条目，用户运行 `mirr current`
- **THEN** 命令报告匹配的内置条目名称

#### Scenario: 显示生效 URL
- **WHEN** 用户运行 `mirr current --show-url` 或 `mirr current -u`
- **THEN** 命令显示实际生效的 registry URL，而不是条目名称

#### Scenario: 环境变量覆盖生效
- **WHEN** `npm_config_registry` 环境变量已设置
- **THEN** `mirr current` 报告该环境变量指定的 registry，且 `--verbose`/`-v` 输出将环境变量标识为来源

#### Scenario: 忽略项目级配置
- **WHEN** 当前工作目录存在项目级 `.npmrc` 且其中设置了与用户级不同的 `registry`
- **THEN** `mirr current` 的结果不受该项目级文件影响，仍按环境变量与用户级 `~/.npmrc` 解析

#### Scenario: 生效值不匹配任何内置条目
- **WHEN** 解析出的 registry URL 不在内置目录中
- **THEN** 命令清晰报告该自定义 URL，而不是报告某个内置条目名称

### Requirement: npm registry 可达性测试
`mirr test [name]` 命令 SHALL 测量一个指定内置条目或全部内置条目的 HTTPS 可达性和响应延迟，且不得修改任何配置。

#### Scenario: 测试单个条目
- **WHEN** 用户运行 `mirr test taobao`
- **THEN** 命令报告该 registry 是否成功响应，并在成功时报告耗时

#### Scenario: 测试全部条目
- **WHEN** 用户运行不带名称的 `mirr test`
- **THEN** 命令并发测试所有内置条目、分别报告每项结果，且不修改当前生效的 registry

### Requirement: 避免回显凭据
系统 SHALL NOT 在正常输出或错误信息中原样回显 registry URL 中可能存在的用户名/密码部分。

#### Scenario: 生效 URL 含凭据
- **WHEN** 解析得到的生效 registry URL 中包含用户名或密码（例如用户手动在 `~/.npmrc` 中写入的带凭据 URL）
- **THEN** 命令在 `current`/`ls`/错误信息中显示该 URL 前，对凭据部分进行脱敏
