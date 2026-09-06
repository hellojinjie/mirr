# mirr

[GitHub](https://github.com/hellojinjie/mirr) | 简体中文 | [English](README.en.md)

默认的包源(PyPI、npm 官方仓库等)在有些网络环境下又慢又不稳定,很多人会切换到镜像源,
但 uv、pip、npm、conda 配置镜像的方式各不相同。

`mirr`(mirror 的简写,命令风格参考自 [nrm](https://github.com/Pana/nrm))用统一的一套命令
(`ls`/`use`/`add`/`del`/`rename`/`home`/`test`/`current`)管理这几个工具的镜像/索引配置,
目前支持 [uv](https://docs.astral.sh/uv/)、pip、npm 和 conda(只读),同时尊重每个工具在
用户级、项目级、环境变量及多索引配置上各自的语义。

## 快速开始

需要 Python 3.9 及以上版本。

```console
$ uv tool install mirr
```

### 为 uv 测速并切换到最快的镜像

```console
$ mirr uv test
[uv] * pypi -------- 187 ms
[uv]   tsinghua ---- 43 ms
[uv]   aliyun ------ 96 ms
[uv]   tencent ----- 121 ms
[uv]   huawei ------ 88 ms
[uv]   ustc -------- 104 ms

$ mirr uv use tsinghua
[uv] SUCCESS The index has been changed to 'tsinghua'.

$ mirr uv current
[uv] You are using tsinghua index.
```

每条输出都带着 `[tool]` 前缀,标明这次改动的是哪个工具的镜像配置(上面的 `uv` 也可以省略,
见下文"多工具支持")。

在交互式终端中不带名称执行 `mirr use` 可以从索引列表中选择;
在脚本中请始终显式指定名称。

## 安装

mirr 本身是一个 Python 命令行工具——无论你主要用 pip、npm 还是 conda,都只需要装一次
mirr(如上,或者 `pip install mirr`),之后管理这几个工具的镜像不需要再额外装什么。

不想安装也可以用 [`uvx`](https://docs.astral.sh/uv/guides/tools/) 临时运行,把命令换成
`uvx mirr ...` 即可。从源码安装(用于开发):

```console
git clone https://github.com/hellojinjie/mirr
cd mirr
uv tool install .
mirr --version
```

## 多工具支持(uv / pip / npm / conda)

命令默认操作 uv(不带前缀的命令始终等价于 `mirr uv <verb>`),同时也支持显式的
`mirr <tool> <verb>` 形式,用来指定 pip、npm 或 conda:

```console
mirr uv use tsinghua      # 等价于 mirr use tsinghua
mirr pip use tsinghua
mirr pip use tsinghua --local   # 写入当前激活 virtualenv 的 pip.conf
mirr npm use npmmirror
mirr npm use npmmirror --local  # 写入当前目录的 .npmrc
mirr conda ls
mirr conda test
```

| 工具 | 支持的命令 | `--local` 作用域 | 说明 |
| --- | --- | --- | --- |
| `uv` | 全部 | 项目 `uv.toml`/`pyproject.toml` | 与不带前缀的命令完全一致 |
| `pip` | 全部 | 当前激活的 virtualenv | pip 没有项目级配置;未激活 venv 时 `--local` 会报错 |
| `npm` | 全部 | 当前目录的 `.npmrc` | scope 覆盖条目(如 `@corp:registry=`)始终保留 |
| `conda` | 仅 `ls`、`test` | 不适用 | channel 是有序列表而非单一默认值,写入语义留待后续版本;`use`/`add`/`del`/`rename`/`current`/`home` 会明确报告暂不支持 |

`mirr <tool> --help` 只会列出该工具当前实际支持的命令。

认证、发布、npm scope,以及针对特定包的 uv source 绑定,目前初始版本的 mirr 尚未涉及。

## 命令

以下命令以不带前缀的形式(默认操作 uv)描述;pip 和 npm 的命令参数与输出格式相同,
只需把命令换成 `mirr pip <verb>` 或 `mirr npm <verb>`,区别在于各自的配置文件位置、
环境变量名称、`--local` 的作用域(见上表),以及 `mirr test` 探测请求的构造方式(见该小节)。

### `mirr ls`

```console
$ mirr uv ls
[uv]   pypi     --- https://pypi.org/simple
[uv] * tsinghua --- https://pypi.tuna.tsinghua.edu.cn/simple
[uv]   aliyun   --- https://mirrors.aliyun.com/pypi/simple
[uv]   tencent  --- https://mirrors.cloud.tencent.com/pypi/simple
[uv]   huawei   --- https://repo.huaweicloud.com/repository/pypi/simple
[uv]   ustc     --- https://mirrors.ustc.edu.cn/pypi/simple
```

列出内置和自定义的索引条目。`*` 标记的是当前目录下实际生效的索引,而不仅仅是上一次用户级的选择。

### `mirr current`

以自然语句的形式输出当前生效的索引。已知有效 URL 对应的索引名称时会直接显示该名称,
`--show-url` 会改为显示 URL,若当前 URL 不在索引列表中,则会附带提示所需的 `mirr add` 命令。

```console
mirr current --show-url
mirr current -u
mirr current --verbose
```

详细模式(verbose)会附加显示来源以及相应的配置文件路径(如适用)。

### `mirr use [name]`

修改 uv 的用户级默认索引(写入结构化的 `[[index]] default = true` 条目),同时保留其他
不相关的设置及已命名的附加索引。

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

### 自定义索引条目

```console
mirr add company https://packages.example.com/simple https://packages.example.com
mirr rename company internal
mirr del internal
```

`mirr add <name> <url> [home]`:`url` 是索引地址(必填),`home` 是主页地址,用于 `mirr home`
(选填,省略则 `mirr home` 对该条目不可用)。内置条目无法被重命名或删除。删除一个正在生效的
自定义条目前,必须先切换到其他条目。

### 主页与可达性

```console
mirr home pypi
mirr home pypi firefox   # 第二个参数指定用哪个浏览器打开
mirr test pypi
mirr test
mirr test --timeout 10
```

`mirr test`(uv/pip)会对每个 Simple Repository 端点下的 `pip/` 项目页面发起一次轻量级、
经过 TLS 校验的 `HEAD` 请求,绝不会下载根索引;npm 改为探测 registry 根路径,conda 探测
channel 的 `noarch/repodata.json`,原理相同但端点不同。如果服务器不支持 `HEAD`,mirr 会
改为发起 GET 请求并只读取最多一个字节。批量测试所有条目时采用有限并发,并按索引列表的顺序
打印结果。`*` 标记当前生效的索引,各列对齐显示,最快的成功结果会被高亮。这是一次可达性
与延迟检测,而非包下载吞吐量基准测试。

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

`mirr pip current` 和 `mirr npm current` 遵循同样的"环境变量 > 就近作用域 > 用户 >
系统/全局"结构,只是变量名称和文件不同:

| | 环境变量 | 就近作用域 | 用户级文件 |
| --- | --- | --- | --- |
| pip | `PIP_INDEX_URL` | 当前激活的 virtualenv (`$VIRTUAL_ENV/pip.conf`) | `pip.conf`(平台相关路径) |
| npm | `npm_config_registry` | 当前目录的 `.npmrc` | `~/.npmrc` |

每个工具的自定义条目各自独立存放,Linux/macOS 上为 `~/.config/mirr/{uv,pip,npm,conda}.toml`,
Windows 上为 `%APPDATA%\mirr\{uv,pip,npm,conda}.toml`。如果你之前用过只支持 uv 的旧版本
mirr,遗留下来的 `config.toml` 会被原样识别为 uv 的条目文件,无需手动迁移。

## 写入格式与冲突处理

以下规则专属于 uv 的 TOML 配置——pip 的 `pip.conf` 和 npm 的 `.npmrc` 都只是单个键值对
(`index-url`/`registry`),mirr 直接覆盖该值,没有这里说的命名条目和冲突检测。

mirr 写入的是 uv 推荐的结构化形式 `[[index]] default = true`,而不是 uv 官方文档标记为
legacy 的标量 `index-url`。注意 `default-index` 本身从来都不是合法的配置文件字段——它只是
`--default-index` 命令行参数和 `UV_DEFAULT_INDEX` 环境变量的名字,写入它会导致 uv 解析配置
时报错。若切换前已经存在遗留的 `index-url` 标量,会在写入新的结构化默认值时一并删除,避免
同一份配置里出现两个相互冲突的默认索引。

在用户级 `uv.toml` 中,mirr 会给它写入的条目带上名称(如 `name = "tsinghua"`),
下次 `mirr use <name>` 时按名原地更新,不会不断追加新条目:

```toml
[[index]]
name = "tsinghua"
url = "https://pypi.tuna.tsinghua.edu.cn/simple"
default = true
```

`pyproject.toml` 通常由团队共享、经过审查,因此 mirr 在其中写入的默认值**不带名字**
(`[[tool.uv.index]] url = "..." default = true`),并且从不自动修改或重命名一个已经
带 `name` 的默认值——那属于冲突,需要人工处理。

以下情况 mirr 都会拒绝自动处理、保持原文件不变,把冲突留给人工解决:

- 现有的默认值除了 `name`、`url`、`default` 之外还带有其他字段(`explicit`、
  `authenticate` 等未知语义)
- 存在多个 `default = true` 条目
- 切换后会与另一个已命名条目重名
- TOML 本身解析、校验或原子替换失败(格式错误)

## 安全边界

- 拒绝包含内嵌用户名、密码或令牌的索引 URL。
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
