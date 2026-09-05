# conda-channel-management Specification

## Purpose

让用户查看并测试 conda channel 镜像源的可达性，复用 mirr 已验证的目录展示和并发测速体验；本能力第一期为只读，channel 的有序列表写入语义留待后续版本。

## Requirements

### Requirement: conda 内置 channel 目录
系统 SHALL 为 conda backend 提供官方 `defaults` 及清华、中科大、华为云等内置 channel 条目。

#### Scenario: 列出内置目录
- **WHEN** 用户运行 `mirr conda ls`
- **THEN** 列出所有内置 channel 条目及其名称和 URL

### Requirement: conda 目录列表不标记生效项
`mirr conda ls` 命令 SHALL 列出所有目录条目，且 SHALL NOT 尝试标记其中某一项为当前生效 channel，因为本能力不解析或跟踪用户的 `.condarc`。

#### Scenario: 列出目录且不做生效判断
- **WHEN** 用户运行 `mirr conda ls`
- **THEN** mirr 列出全部内置 channel 条目，不显示"当前生效"标记，也不读取用户的 `.condarc`

### Requirement: conda channel 可达性测试
`mirr conda test [name]` 命令 SHALL 测量一个指定 channel 或全部目录条目的 HTTPS 可达性和响应延迟，不得修改任何配置或下载完整的 `repodata.json`；探测策略针对 `{channel}/noarch/repodata.json` 端点，优先发出无响应体的 `HEAD` 请求，仅在服务器明确不支持 `HEAD` 时回退到受字节限制的 `GET`。

#### Scenario: 测试单个 channel
- **WHEN** 用户运行 `mirr conda test tsinghua`
- **THEN** mirr 报告其 `noarch/repodata.json` 端点是否成功响应，并在成功时包含耗时

#### Scenario: 测试全部 channel
- **WHEN** 用户运行不带名称的 `mirr conda test`
- **THEN** mirr 并发测试目录条目、分别报告每项结果

#### Scenario: 避免下载完整索引
- **WHEN** mirr 测试的 channel 其 `repodata.json` 体积较大
- **THEN** mirr 不读取无界响应体，仅确认端点可达

### Requirement: conda 写入操作明确报告未支持
`mirr conda use`、`mirr conda add`、`mirr conda del`、`mirr conda rename` 和 `mirr conda current` 命令 SHALL 明确报告该操作在当前版本不受支持，并返回非零退出状态，而不是报出通用的"未知命令"错误或静默失败。

#### Scenario: 请求切换 channel
- **WHEN** 用户运行 `mirr conda use tsinghua`
- **THEN** mirr 报告 conda 的 channel 切换尚不支持，且不修改任何文件

#### Scenario: 请求管理自定义 channel
- **WHEN** 用户运行 `mirr conda add`、`mirr conda del` 或 `mirr conda rename`
- **THEN** mirr 报告该操作尚不支持，且不修改任何文件

### Requirement: conda 秘密安全行为
系统 SHALL NOT 在正常输出中回显 URL 凭据，且诊断错误 SHALL 在显示前对嵌入的敏感 URL 信息进行脱敏。

#### Scenario: 诊断错误包含敏感 URL
- **WHEN** HTTP 或解析错误引用包含敏感用户信息的 channel URL
- **THEN** mirr 在显示错误前对敏感部分进行脱敏
