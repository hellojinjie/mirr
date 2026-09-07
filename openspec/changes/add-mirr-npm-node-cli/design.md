## Context

见 proposal.md - Why。约束来自现有 Python 实现 `src/mirr/backends/npm.py`，其行为已被现有 `npm-registry-management` spec 固化，本设计只挑其中 ls/current/use/test 这部分子集在 Node 里重做一份独立实现，不修改、不依赖那份 Python 代码或其 spec。

## Goals / Non-Goals

**Goals:**
- `mirr-npm/` 下的 Node 包能独立安装（`npm install -g`），提供 `mirr ls|current|use <name>|test [name]`。
- `.npmrc` 编辑行为（只替换 `registry=` 那一行、保留注释和 `@scope:registry=` 覆盖、原子替换）与 Python 版一致，用户可放心两边混用同一个 `.npmrc`。

**Non-Goals（第一版明确不做，均已与用户确认）：**
- 不做 `add`/`del`/`rename`/`home`，因此也不需要任何自定义目录存储格式。
- 不做 `--local` 项目级切换，不读当前目录的项目 `.npmrc`。
- 不做交互式选择器（`use` 不传名字直接报错，不引入 readline）。
- 不引入任何第三方 npm 依赖。

## Decisions

**1. 零依赖、手写 `process.argv` 解析**
四个动词、参数形态都很简单（`use` 一个位置参数，`test` 一个可选位置参数），用一个小的 switch/if 分发即可。避免给"管理 npm 镜像源"的工具本身引入一条 npm 依赖链。若未来动词/参数变多再评估引入 `commander`。

**2. 独立目录 `mirr-npm/`，不建 Node workspace**
只有一个 Node 包，暂不需要 `packages/` + workspace 配置的额外复杂度；`mirr-npm/` 与 `src/mirr/`（Python）完全隔离，各自有自己的 `package.json`/`pyproject.toml`，互不影响构建、测试、发布。

**3. 可执行文件名就叫 `mirr`（用户已确认）**
保持与 Python 版 `mirr npm <verb>` 相同的心智模型，直接 `mirr <verb>`（因为这个包本身就是 npm-only，不需要再套一层 `npm` 子命令）。
- 权衡：两者都装在同一环境会抢占 `mirr` 命令名。不做运行时冲突检测，只在 README/发布说明里注明"这是给纯 Node 环境用的独立实现，和 Python 版 `mirr` 二选一安装"。

**4. `.npmrc` 编辑策略照搬 Python 版**
- 只匹配、替换独立成行的 `registry\s*=\s*...`；跳过以 `#`/`;` 开头的注释行；不动 `@scope:registry=` 这类作用域覆盖。
- 写入用"临时文件（同目录）+ `fs.renameSync` 原子替换"，对应 Python 侧 `tempfile.NamedTemporaryFile` + `os.replace` 的崩溃安全写法。

**5. 生效值解析链：`npm_config_registry` 环境变量 → `~/.npmrc` → 兜底 `https://registry.npmjs.org`（用户已确认）**
不读项目目录 `.npmrc`、不支持 `npm_config_userconfig` 覆盖用户配置路径——这是刻意的第一版简化，`ls`/`current`/`test` 全部基于这条链路判断"当前生效镜像"。

**6. 内置镜像表用纯 JS 常量对象**
```
{ npmjs: "https://registry.npmjs.org", npmmirror: "...", tencent: "...", huawei: "..." }
```
不需要任何解析器（TOML/JSON 文件），因为没有 `add`/`del`。

**7. `test` 命令用 Node 18+ 全局 `fetch`，先 `HEAD` 后 `GET` 兜底**
要求 `engines.node >= 18`，避免手写 `http`/`https` 模块请求逻辑或引入 `undici` 依赖。策略：先发 `HEAD <registry>/-/ping`，若响应状态表明服务端不支持 `HEAD`（如 405/501）则退化为 `GET` 并在拿到响应头后立即中止读取 body（`AbortController`），只关心状态码和耗时，不做 Python 版那种字节范围限制的精确度。

**8. 输出格式沿用 `[npm] ...` 前缀与 `*` 当前项标记**
让熟悉 Python 版输出的用户读起来是同一套东西，即使内部实现完全独立。

## Risks / Trade-offs

- [`mirr` 命令名与 Python 版冲突] → 缓解：文档中明确这是二选一的独立实现，不做自动检测或协商。
- [`current`/`ls` 忽略项目级 `.npmrc`，在有项目配置的目录下可能显示"不准确"的当前值] → 缓解：`current` 的输出/帮助文本明确说明"仅看环境变量与用户级配置"，不假装是 npm 完整优先级。
- [`test` 的 HEAD→GET 兜底比 Python 版的字节范围 GET 更粗糙] → 缓解：可接受的第一版精度损失，后续若需要更贴近可再对齐。

## Migration Plan

新增功能，不涉及已有配置迁移；不安装这个新包对现有 Python `mirr` 用户没有任何影响。
