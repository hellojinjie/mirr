## 1. 项目脚手架

- [x] 1.1 创建 `mirr-npm/` 目录结构（`package.json`、`bin/mirr.js`、`src/registry.js`），`package.json` 设置 `bin: {"mirr": "./bin/mirr.js"}` 与 `engines.node >= 18`；验证：`node mirr-npm/bin/mirr.js` 能执行且不报错退出
- [x] 1.2 `package.json` 不声明任何运行时 `dependencies`；验证：`cat mirr-npm/package.json` 确认 `dependencies` 字段为空或不存在

## 2. 内置镜像表与生效值解析

- [x] 2.1 在 `src/registry.js` 中实现内置镜像表常量（`npmjs`/`npmmirror`/`tencent`/`huawei`，URL 与 `src/mirr/catalog.py` 中 `BUILTIN_NPM_INDEXES` 一致）；验证：单测断言四个条目的 name/url
- [x] 2.2 实现 `resolveEffectiveRegistry()`：按 `npm_config_registry` 环境变量 → 解析 `~/.npmrc` 中独立成行的 `registry=` → 兜底 `https://registry.npmjs.org` 的顺序解析；验证：单测覆盖三种优先级分支，且覆盖跳过注释行（`#`/`;`）和不匹配 `@scope:registry=` 覆盖条目的情形
- [x] 2.3 实现按 URL 反查内置条目名称的 `matchBuiltinName()`；验证：单测覆盖匹配成功与不匹配（自定义 URL）两种情况

## 3. `.npmrc` 原子写入

- [x] 3.1 实现 `applyRegistry(text, url)`：只替换独立成行的 `registry=` 那一行，保留注释行和 `@scope:registry=` 覆盖条目，若不存在该行则追加到文件末尾；验证：单测覆盖"替换已有行""保留无关设置/scope覆盖/注释""追加到空文件或不存在文件"三类场景
- [x] 3.2 实现 `atomicWriteFile(path, content)`：在同目录写入临时文件后用 `fs.renameSync` 替换目标文件，目标目录不存在时先创建；验证：单测在临时目录中确认写入后文件内容正确，且失败路径（如目录不可写）不会残留半写的目标文件

## 4. CLI 动词实现

- [x] 4.1 实现 `mirr ls`：列出内置目录并标记与当前生效值匹配的条目；不匹配任何内置条目时额外报告生效 URL；验证：CLI 集成测试比对标准输出文本，覆盖匹配与不匹配两种情形
- [x] 4.2 实现 `mirr current`，支持 `-u`/`--show-url` 与 `-v`/`--verbose`：分别验证按名称展示、按 URL 展示、以及 verbose 模式下正确报告来源（`environment:npm_config_registry` / `user:.npmrc` / `implicit:npmjs`）；验证：集成测试覆盖三种来源与两个可选参数的组合
- [x] 4.3 实现 `mirr use <name>`：校验名称存在于内置目录、写入 `~/.npmrc`、成功时打印确认信息；未知名称报错且不修改文件；缺少名称参数时直接报错退出（非零状态码），不做任何交互式选择；验证：集成测试覆盖成功、未知名称、缺少参数三条路径，并断言未知/缺参场景下 `~/.npmrc` 内容未被改动
- [x] 4.4 实现 `mirr test [name]`：对 `<registry>/-/ping` 先发 `HEAD`，若响应状态表明不支持（如 405/501）则退化为 `GET` 并在拿到响应头后立即中止；支持单个条目与全部条目并发测试；不修改任何配置文件；验证：用本地模拟 HTTP 服务器的集成测试覆盖成功、失败/超时、HEAD 被拒绝后回退 GET 三种情形

## 5. 安全与输出一致性

- [x] 5.1 实现 URL 脱敏工具函数，在 `current`/`ls`/错误信息展示任何 registry URL 前去除其中的用户名/密码部分；验证：单测覆盖带凭据 URL（如 `https://user:pass@host/`）的脱敏结果
- [x] 5.2 统一各命令输出格式为 `[npm] ...` 前缀，`ls`/`test` 用 `*` 标记当前生效条目，与 Python 版视觉风格一致；验证：CLI 集成测试断言输出前缀与标记字符

## 6. 文档

- [x] 6.1 编写 `mirr-npm/README.md`：安装方式（`npm install -g`）、支持的四个命令与参数、明确说明只做用户级作用域（不读项目 `.npmrc`）、以及与 Python 版 `mirr` 命令名冲突的提示；验证：人工检查 README 覆盖以上四点
