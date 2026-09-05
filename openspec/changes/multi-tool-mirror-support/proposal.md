## Why

mirr 目前只管理 uv 的包索引。国内开发者同样需要为 pip、conda、npm 配置镜像源，但这些工具各有独立的配置格式，缺乏 mirr 已经为 uv 验证过的统一体验（目录管理、原子写入、并发测速）。把 mirr 扩展成通用的镜像配置工具，可以让已验证的交互模型覆盖到其余三个高频生态。

## What Changes

- 新增 `mirr <tool> <verb>` 命令形态，`tool` 取值 `uv`/`pip`/`npm`/`conda`。
- 无 tool 前缀的现有命令（`mirr use`/`mirr ls`/`mirr current`/...）保留，作为 `mirr uv <verb>` 的向后兼容别名，行为逐字节不变。
- 现有 uv 实现原地重构进统一的 backend 协议（locate 配置路径 / resolve 生效值 / apply 原子写入 / probe_url 探测路径构造），对最终用户不可见。
- 新增 pip backend：`ls`/`current`/`use`/`add`/`del`/`rename`/`home`/`test`。`--local` 映射到当前激活 virtualenv 的 `pip.conf`；未激活 venv 时报错并引导用户先激活或去掉 `--local`。
- 新增 npm backend：同一套命令。`--local` 映射到当前目录的项目级 `.npmrc`，与现有 uv `--local` 语义一致。
- 新增 conda backend：第一期仅 `ls`/`test`（只读）。conda 的 channel 是有序列表而非单一 default，`use`/`add`/`del`/`rename` 的写入语义留待后续版本单独设计，本期不提供、调用时报告未支持。
- catalog 存储从单一 `~/.config/mirr/config.toml` 拆分为每工具一个文件：旧文件原样复用为 `uv.toml`，无需迁移；新增 `pip.toml`/`npm.toml`/`conda.toml`。
- 探测逻辑（`probe.py`）改为按 backend 可插拔的探测路径构造：uv/pip 沿用现有 Simple Repository 项目端点探测；npm 探测注册表根；conda 探测 `{channel}/noarch/repodata.json`。

## Capabilities

### New Capabilities
- `pip-index-management`：管理 pip 的 `index-url`，支持用户级/venv 级切换、自定义目录 CRUD、可达性测速。
- `npm-registry-management`：管理 npm 的 `registry`，支持用户级/项目级切换、自定义目录 CRUD、可达性测速。
- `conda-channel-management`：列出内置及自定义 conda channel 目录，并测试其可达性（第一期只读，不含写入操作）。
- `mirr-cli-dispatch`：`mirr <tool> <verb>` 路由框架，以及无 tool 前缀命令到 `mirr uv <verb>` 的向后兼容别名行为。

### Modified Capabilities
（无 — `uv-index-management` 现有需求描述的可观察行为在本次变更后保持不变，其命令仍可通过别名或 `mirr uv` 前缀达成同样效果。）

## Impact

- **重构**：`src/mirr/config.py`、`editor.py`、`probe.py`、`catalog.py`、`cli.py` 拆分为共享协议 + 每工具 backend（`src/mirr/backends/{uv,pip,npm,conda}.py`）。
- **新依赖待定**：conda 配置为 YAML 格式，是否引入 YAML 解析依赖（如 `pyyaml`）或手写最小化解析器，需在 design.md 中确认。
- **测试**：现有 `tests/` 中 uv 相关用例随重构调整 import 路径并保持通过；新增 pip/npm/conda 对应测试套件。
- **用户可见变化**：新增 `mirr <tool> <verb>` 命令形态；catalog 文件布局变化（旧 `config.toml` 被无缝识别为 `uv.toml`，用户无需手动迁移）；`mirr <tool> --help` 列出该工具支持的命令子集（conda 只列 `ls`/`test`）。
