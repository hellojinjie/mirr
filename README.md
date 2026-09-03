# `mirr`or

简体中文 | [English](README.en.md)

`mirr` 是一个仿照 nrm 风格设计的 [uv](https://docs.astral.sh/uv/) 包索引管理器。
它保留了熟悉的命令形式,同时尊重 uv 在用户级、项目级、环境变量及多索引配置上的语义。

## 安装

mirr 需要 Python 3.9 及以上版本。无需安装,直接用 [`uvx`](https://docs.astral.sh/uv/guides/tools/) 运行:

```console
uvx mirr --version
```

或者安装为常驻命令:

```console
uv tool install mirr
mirr --version
```

从源码安装(用于开发):

```console
uv tool install .
mirr --version
```

## 从 nrm 迁移

核心操作使用相同的命令名:

| nrm | mirr | 作用 |
| --- | --- | --- |
| `nrm ls` | `mirr ls` | 列出所有索引,并标记当前生效的索引 |
| `nrm current -u` | `mirr current -u` | 显示当前生效的索引 URL |
| `nrm use <name>` | `mirr use <name>` | 修改用户级默认索引 |
| `nrm use <name> --local` | `mirr use <name> --local` | 修改项目级默认索引 |
| `nrm add <name> <url> [home]` | `mirr add <name> <url> [home]` | 添加自定义索引 |
| `nrm del <name>` | `mirr del <name>` | 删除自定义索引 |
| `nrm rename <name> <new-name>` | `mirr rename <name> <new-name>` | 重命名自定义索引 |
| `nrm home <name> [browser]` | `mirr home <name> [browser]` | 打开索引主页 |
| `nrm test [name]` | `mirr test [name]` | 测量端点延迟 |

认证、发布、npm scope,以及针对特定包的 uv source 绑定,目前初始版本的 mirr 尚未涉及。

## 快速开始

```console
$ mirr test
* pypi -------- 187 ms
  tsinghua ---- 43 ms
  aliyun ------ 96 ms
  tencent ----- 121 ms
  huawei ------ 88 ms
  ustc -------- 104 ms

$ mirr use tsinghua
SUCCESS The index has been changed to 'tsinghua'.

$ mirr current
You are using tsinghua index.
```

在交互式终端中不带名称执行 `mirr use` 可以从目录列表中选择;
在脚本中请始终显式指定名称。

## 命令

### `mirr ls`

列出内置和自定义的索引条目。`*` 标记的是当前目录下实际生效的索引,而不仅仅是上一次用户级的选择。

### `mirr current`

沿用 nrm 熟悉的语句式输出风格。已知有效 URL 对应的目录名称时会直接显示该名称,
`--show-url` 会改为显示 URL,若当前 URL 不在目录中,则会附带提示所需的 `mirr add` 命令。

```console
mirr current --show-url
mirr current -u
mirr current --verbose
```

详细模式(verbose)会附加显示来源以及相应的配置文件路径(如适用)。

### `mirr use [name]`

修改 uv 的用户级 `default-index`,同时保留其他不相关的设置及已命名的附加索引。

```console
mirr use pypi
mirr use tsinghua
```

如果项目级配置或 `UV_DEFAULT_INDEX` 环境变量仍然覆盖了新的用户级设置,
mirr 依然会写入所请求的用户配置,并打印警告说明当前生效的覆盖来源。

### `mirr use [name] --local`

仅修改当前项目:

1. 优先使用最近一层已存在的 `uv.toml`。
2. 否则更新最近一层 `pyproject.toml` 中的 `[tool.uv]`。
3. 如果都不存在,则在用户确认后在当前目录创建 `uv.toml`。

在非交互式脚本中允许创建新的本地 `uv.toml` 时,使用 `--yes`:

```console
mirr use aliyun --local --yes
```

当 `pyproject.toml` 存在时,mirr 不会额外创建同级的 `uv.toml`,
因为这样会导致 uv 忽略该文件中 `[tool.uv]` 的设置。

### 自定义目录条目

```console
mirr add company https://packages.example.com/simple https://packages.example.com
mirr rename company internal
mirr del internal
```

内置条目无法被重命名或删除。删除一个正在生效的自定义条目前,必须先切换到其他条目。

### 主页与可达性

```console
mirr home pypi
mirr home pypi firefox
mirr test pypi
mirr test
mirr test --timeout 10
```

`mirr test` 会对每个 Simple Repository 端点下的 `pip/` 项目页面发起一次轻量级、
经过 TLS 校验的 `HEAD` 请求,绝不会下载根索引。如果服务器不支持 `HEAD`,
mirr 会改为发起请求并只读取最多一个字节。批量测试所有条目时采用有限并发,
并按目录顺序打印结果。与 nrm 一样,`*` 标记当前生效的索引,各列对齐显示,
最快的成功结果会被高亮。这是一次可达性与延迟检测,而非包下载吞吐量基准测试。

## 配置优先级

`mirr current` 按以下顺序评估持久化配置与环境变量:

1. `UV_DEFAULT_INDEX`,以及仍受支持的旧版别名 `UV_INDEX_URL`
2. 项目级 `uv.toml` 或 `pyproject.toml` 中的 `[tool.uv]`
3. 用户级 `uv.toml`
4. 系统级 `uv.toml`
5. uv 隐式的默认值 `https://pypi.org/simple`

传递给后续 uv 调用的命令行选项是不可预测的,因此不会被 `mirr current` 纳入考虑。

用户级 uv 配置遵循 uv 的平台约定,包括 Linux 和 macOS 上支持 XDG 的
`~/.config/uv/uv.toml`,以及 Windows 上的 `%APPDATA%\uv\uv.toml`。
mirr 的自定义条目则使用对应平台上 mirr 自身的用户配置目录。

## 冲突恢复

mirr 通常写入的是标量形式的 `default-index`。类似下面这种简单的匿名结构化默认值:

```toml
[[index]]
url = "https://old.example/simple"
default = true
```

可以被安全地替换。若用户级 `uv.toml` 中的默认值只包含 `name`、`url` 和 `default`,
会被原地更新,从而使 `mirr use <name>` 与 uv 的具名索引格式保持兼容。
`pyproject.toml` 中的具名默认值、重复的目标名称、认证行为、发布 URL 及其他额外语义
则保持不变,并作为冲突提示留给人工处理。当解析、校验或原子替换失败时,
mirr 也会拒绝处理格式错误的 TOML,并保持原文件不变。

## 安全边界

- 拒绝包含内嵌用户名、密码或令牌的目录 URL。
- mirr 不维护凭证存储,也不会在错误信息中打印 URL 中的凭证。
- 私有索引的凭证请使用 uv 自身支持的认证机制配置。
- `mirr test` 期间始终保持 TLS 校验开启。
- 传入浏览器参数时,直接以参数向量启动进程,mirr 不会构造 shell 命令。

## 开发

```console
uv sync --locked
uv run pytest
uv run ruff check .
uv build
```
