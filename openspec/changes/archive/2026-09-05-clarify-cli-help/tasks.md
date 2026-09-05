## 1. 顶层帮助分组与提示

- [x] 1.1 给 `_MirrGroup` 设置 `subcommand_metavar = "[PACKAGE TOOL] COMMAND [ARGS]..."`；运行 `mirr --help` 验证 `Usage:` 行文本。踩坑记录：`subcommand_metavar` 不能只设成类属性，`click.core.MultiCommand.__init__` 总会用构造参数（默认值）覆盖它作为实例属性；改为在 `@click.group(...)` 装饰器上传 `subcommand_metavar=...` 关键字参数
- [x] 1.2 重写 `_MirrGroup.format_commands`，把命令列表分成 `Package tools (uv is the default when [PACKAGE TOOL] is omitted):`（`uv`/`pip`/`npm`/`conda`）和 `Commands:`（其余 8 个别名）两个分组；运行 `mirr --help` 验证分组与顺序
- [x] 1.3 给 `cli` 的 `@click.group(...)` 加 `epilog`，说明支持的工具集合、`mirr <tool> --help` 用法，并以 conda 只读为例；验证 `mirr --help` 输出末尾包含该提示
- [x] 1.4 新增/更新测试断言 `mirr --help` 的完整输出（Usage 行、两个分组标题及内容、epilog 文案），确认 `mirr <tool> --help`（如 `mirr conda --help`）不受影响。踩坑记录：`CliRunner().invoke()` 不传 `prog_name` 时 Usage 行显示的是函数名 `cli` 而非真实的 `mirr`,断言 Usage 行的测试需要显式传 `prog_name="mirr"`
- [x] 1.5 运行 `pytest`、`ruff check` 全部通过，并运行 `openspec validate clarify-cli-help --strict` 通过（150 项测试全部通过）
