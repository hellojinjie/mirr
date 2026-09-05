## 1. 共享 backend 协议与 catalog 拆分

- [x] 1.1 定义共享 backend 协议（locate/resolve/apply/probe_url/`SUPPORTED_VERBS`），落地为 `src/mirr/backends/` 下的公共类型模块；`mypy`/导入检查通过即视为完成
- [x] 1.2 将 `catalog.py` 的 `CatalogStore` 改为按 `tool` 参数选择内置表和默认路径（`default_catalog_path(tool=...)`），并验证 `default_catalog_path(tool="uv")` 与重构前路径逐字节相同（单元测试断言）
- [x] 1.3 把现有 `config.py`/`editor.py` 中 uv 专属逻辑搬迁进 `src/mirr/backends/uv.py`，`cli.py` 改为经由该 backend 调用；运行 `pytest tests/test_config.py tests/test_editor.py tests/test_named_structured_defaults.py` 全部通过
- [x] 1.4 把 `probe.py` 拆成共享 HEAD/GET/Range 循环 + backend 提供的探测 URL 构造函数；运行 `pytest tests/test_probe_lightweight.py` 全部通过

## 2. CLI 路由与向后兼容别名

- [x] 2.1 实现 `mirr <tool> <verb>` 子命令分组脚手架，每个工具只注册其 `SUPPORTED_VERBS` 中的命令；手动运行 `mirr conda --help` 验证只列出 `ls`/`test`
- [x] 2.2 为未支持的 verb（如 `mirr conda use`）注册明确报错的 stub 命令；运行 `mirr conda use x` 验证返回非零退出码和"暂不支持"提示，而非 Click 的通用未知命令错误
- [x] 2.3 将无前缀命令（`ls`/`current`/`use`/`add`/`del`/`rename`/`home`/`test`）改写为直接复用 `mirr uv <verb>` 的同一个 Click Command 对象（同一函数，两个名字挂载），逐字节相同由构造保证；`pytest tests/test_cli_commands.py` 全部通过
- [x] 2.4 为未知 `<tool>` 值实现报错分支，列出受支持工具；新增测试覆盖 `mirr foo ls` 返回非零退出码并列出 uv/pip/npm/conda

## 3. pip backend

- [x] 3.1 实现 pip 的 `locate_targets`（用户级路径 + `VIRTUAL_ENV` 检测）与 `resolve_effective`（环境变量 > venv > 用户 > 系统优先级）；单元测试覆盖优先级顺序，参照 `tests/test_config.py` 的用例结构
- [x] 3.2 实现按行 patch 的 `pip.conf` 原子编辑器（定位/替换/插入 `[global]` 下的 `index-url`，其余行原样保留）；新增回归测试验证无关设置、注释在切换后保持不变。代码审查发现一个真实 bug：当 `[global]` 是文件最后一行且没有尾随换行符时，插入新 `index-url` 行会与 `[global]` 直接粘连成 `[global]index-url = ...`，导致 pip 自己的 `configparser` 静默丢弃该设置；已修复（插入前确保 header 行以换行结尾）并补充回归测试
- [x] 3.3 未激活 venv 时 `mirr pip use <name> --local` 报错且不创建/修改任何文件；单元测试覆盖该场景
- [x] 3.4 实现 pip 探测 URL 构造（复用 uv/pip 共用的 Simple Repository 项目端点），接入共享探测循环；已通过 `tests/test_pip_backend.py` 覆盖
- [x] 3.5 定义 pip 内置目录（复用与 uv 相同的 6 个 PyPI 镜像 URL）
- [x] 3.6 在 `mirr pip` 下接线 `ls`/`current`/`use`/`add`/`del`/`rename`/`home`/`test`；对照 `pip-index-management` spec 的每条 scenario 手动或自动验证一遍

## 4. npm backend

- [x] 4.1 实现 npm 的 `locate_targets`（用户 `~/.npmrc` + 项目 `.npmrc`）与 `resolve_effective`（`npm_config_registry` > 项目 > 用户 > 全局）；单元测试覆盖优先级顺序
- [x] 4.2 实现按行 patch 的 `.npmrc` 原子编辑器（定位/替换/插入 `registry`，保留 scope 覆盖条目如 `@corp:registry=` 和注释）；回归测试验证保留行为
- [x] 4.3 确认 npm 内置镜像（npmjs 官方、npmmirror/淘宝、腾讯、华为）的真实 URL 可用，并作为内置目录写入代码；已用 curl 逐一验证 HEAD/GET 200
- [x] 4.4 针对真实镜像验证探测端点，据此实现 npm 的探测 URL 构造函数；发现镜像根路径响应不一致（腾讯根路径返回"Web接口已禁用"），改用 npm 注册表协议自带的 `{registry}/-/ping` 健康检查端点，四个内置镜像均验证 200
- [x] 4.5 在 `mirr npm` 下接线 `ls`/`current`/`use`/`add`/`del`/`rename`/`home`/`test`（`--local` 写入项目 `.npmrc`）；对照 `npm-registry-management` spec 的每条 scenario 验证一遍

## 5. conda backend（只读）

- [x] 5.1 确认 conda 内置镜像的真实 channel base URL，写入内置目录；阿里云的 `mirrors.aliyun.com/anaconda/...` 经 curl 验证已下线（根路径与 repodata.json 均 404，`developer.aliyun.com/mirror/anaconda` 页面本身也 404），替换为经验证可用的华为云 conda 镜像（`mirrors.huaweicloud.com/repository/conda/pkgs/main`），最终内置集为 defaults/清华/中科大/华为
- [x] 5.2 实现 conda 探测 URL 构造（`{channel}/noarch/repodata.json`），接入共享 HEAD 优先/Range-GET 回退探测循环；四个内置 channel 均用 curl 验证 HEAD 200（中科大为 302 重定向，`_acceptable_status` 按 2xx-3xx 均视为可达，行为符合预期）
- [x] 5.3 实现 `mirr conda ls`（列出内置条目，不做"当前生效"标记）和 `mirr conda test`；对照 `conda-channel-management` spec 验证
- [x] 5.4 为 `mirr conda use`/`add`/`del`/`rename`/`current`（以及 `home`，第 2 组通用 stub 机制自动覆盖）注册明确的"暂不支持"提示

## 6. 收尾

- [x] 6.1 更新 `README.md`/`README.en.md`，加入 `mirr <tool> <verb>` 用法示例，并注明 conda 本期只读
- [x] 6.2 确认本次变更未引入非必要新依赖（design.md 决定本期不需要 YAML 库）；检查 `pyproject.toml`/`uv.lock` diff 确认，唯一变更是会话开始前就已存在、与本变更无关的 `platformdirs` 移除
- [x] 6.3 运行完整测试套件 `pytest` 全部通过，并运行 `openspec validate multi-tool-mirror-support --strict` 通过（147 项测试全部通过，`ruff check` 与 `openspec validate --strict` 均无问题）
- [x] 6.4 用户反馈补充需求：所有命令的输出都以 `[<tool>] ` 前缀标注所属工具（含无前缀历史命令，统一标注为 `[uv]`，与 nrm 逐字节兼容的旧行为不再保留，已同步更新 `tests/test_nrm_output.py` 等受影响测试）；已补充 `mirr-cli-dispatch` spec 的对应需求与场景
