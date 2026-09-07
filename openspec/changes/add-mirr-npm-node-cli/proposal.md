## Why

目前 `mirr` 是纯 Python 实现，切换 npm registry 也必须先装 Python/uv 才能用。为完全没有 Python 环境、只装了 Node/npm 的用户提供一条更轻的路径，同时验证 mirr 的核心思路（内置镜像表 + 原子改写 `.npmrc`）在 Node 生态下是否可行，先做一个覆盖最常用场景的最小子集。

## What Changes

- 新增独立目录 `mirr-npm/`，作为一个单独的 Node 包（不影响现有 Python 包的结构、依赖或发布流程）。
- 可执行文件命名为 `mirr`，用法与现有 `mirr npm <verb>` 保持一致的动词/参数形态。
- 第一版只实现四个动词：`ls`、`current`、`use <name>`、`test [name]`。不做 `add`/`del`/`rename`/`home`，也不做 `--local` 项目级切换——只管用户级（全局）`~/.npmrc`。
- 内置镜像表直接复用现有 Python 版的 URL：`npmjs`、`npmmirror`、`tencent`、`huawei`；因为没有 `add`，第一版不需要任何自定义目录存储/解析。
- `current`/`ls` 只按 `npm_config_registry` 环境变量 → `~/.npmrc` → 兜底 `https://registry.npmjs.org` 这条链路解析，不读当前目录的项目级 `.npmrc`。
- 零第三方依赖，手写 `process.argv` 解析。

## Capabilities

### New Capabilities
- `mirr-npm-node-cli`: 独立 Node 实现的 npm registry 查看/切换/测速最小子集（ls/current/use/test，仅用户级作用域，内置镜像表，不含自定义目录管理）

### Modified Capabilities
(none — 现有 `npm-registry-management` 描述的是 Python 版 `mirr npm` 的完整契约，其行为不受本变更影响)

## Impact

- 新增代码：`mirr-npm/`（`package.json`、`bin/mirr.js`、`src/registry.js`），与现有 `src/mirr/` Python 代码完全隔离，不共享构建、测试或发布流程。
- 不影响现有 CI 矩阵、`pyproject.toml`、`uv.lock` 或任何现有 Python 测试。
- 新增的 `mirr` 可执行文件名与 Python 项目的 `mirr` 命令同名；两者是分别安装的独立包（`pip install`/`uv tool install` vs `npm install -g`），预期不会同时装在同一环境，但用户需要知道两者会争用同一个命令名。
