## Why

已经熟悉 nrm 的用户应当无需学习一套差异明显的命令，也无需手动编辑 TOML 文件，就能管理 uv 软件包索引。专用的 `uim` CLI 可以在尊重 uv 分层、多索引配置模型的同时，提供熟悉的操作方式。

## What Changes

- 新增可安装的 `uim` 命令，支持 Python 3.9 及以上版本。
- 提供与 nrm 兼容的核心命令，用于列出、查看、切换、添加、删除、重命名、打开和测试软件包索引。
- 默认支持用户级切换，并通过 `uim use --local` 支持项目级切换。
- 内置常用 PyPI 镜像目录，同时允许用户维护自定义条目。
- 解析并报告当前目录实际生效的索引，包括配置覆盖关系。
- 保留无关的 uv 配置；遇到不安全冲突时明确拒绝，而不是静默替换未受 uim 管理的索引设置。
- 初始版本不处理认证、发布、npm scope 和软件包级来源绑定。

## Capabilities

### New Capabilities

- `uv-index-management`：通过类似 nrm 的 CLI，在用户级和项目级管理 uv 兼容的软件包索引目录，并安全地查看、切换和测试索引。

### Modified Capabilities

无。

## Impact

- 将占位应用入口替换为以 `uim` 暴露的 Python CLI 软件包。
- 将 Python 最低版本从 3.13 降至 3.9。
- 按需引入 CLI 交互、HTTP 探测和保留注释的 TOML 更新依赖。
- 读取和更新 uv 用户配置，以及项目的 `uv.toml` 或 `pyproject.toml`。
- 在符合平台规范的 uim 配置目录中保存自定义索引目录数据。
- 要求在 Linux、macOS 和 Windows 的路径与配置约定上具备跨平台行为和测试。
