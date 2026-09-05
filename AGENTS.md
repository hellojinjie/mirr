# Agent 使用说明

## 文档语言

本仓库的文档(`AGENTS.md`、`CLAUDE.md`、`README` 之外的说明性文档等)优先使用中文撰写。代码本身的标识符、注释、commit message 不受此约束。

## 跨平台(Windows/macOS/Linux)测试正确性

CI 会在 `ubuntu-latest`、`macos-latest`、`windows-latest` 三个矩阵上跑测试。本地开发环境只有 Linux,所以跨平台的 bug 在本地完全看不出来,只会在 CI 里(或者更糟,在 macOS/Windows 用户的生产环境里)暴露。同一个类别的问题在一次发布里连续出了 3 个 bug,每个都单独耗费了一轮 CI 排查。避免重蹈覆辙:

1. **只固定环境变量不够,还要固定 `sys.platform`。** 像 `user_pip_config_path(*, env=None, platform=None, home=None)` 这类函数,只要没显式传 `platform` 参数,内部就会读真实的 `sys.platform`。测试里用 `monkeypatch.setenv` mock 了 `HOME`/`XDG_CONFIG_HOME`,但如果调用链里没有把 `platform` 传下去,函数在 `windows-latest`/`macos-latest` 的 runner 上还是会按真实宿主系统解析,走到跟测试假设不同的分支,而且是静默出错。修法:在测试里 `monkeypatch.setattr(sys, "platform", "linux")`,或者在函数签名支持的地方显式传 `platform=`。

2. **`pathlib.Path.home()` 在真实 Windows 上不认 `$HOME`,只认 `USERPROFILE`。** 这是标准库 pathlib 在 Windows 分支下的实现差异,固定 `sys.platform` 也解决不了。任何最终会落到 `Path.home()` 兜底、且该分支没有环境变量覆盖机制的代码(比如 npm 的 `user_npmrc_path()`,因为真实 npm 本身也没有 XDG/APPDATA 这类覆盖机制),测试里必须把 `USERPROFILE` 和 `HOME` 一起设置,否则读到的是 CI runner 真实的用户目录而不是隔离的 `tmp_path`。两个一起设在 POSIX 上完全无害(`USERPROFILE` 在那边直接被忽略)——直接养成习惯两个一起设。

3. **在说"这次应该修好了"之前,把每一个"函数签名里 `platform=None`/`home=None` 走默认值"的测试都列一遍,确认该分支实际读取的每一个环境变量在测试里都真的被覆盖了——不要只看眼前这一个。** 这次会话里分几次推送、每次只修好一部分(修了 macOS 却漏了 Windows,或反过来),每一次都白白耗费一整轮 CI。应该一次性做完系统性排查,而不是逐个試錯。

4. **CI 在本地跑不了的平台上失败时,不要连续好几轮靠猜——先想办法拿到真实的报错输出。** GitHub REST API 的 job 日志接口就算是公开仓库也需要更高权限的 token,直接 403;check-run 的 annotations 只会给"Process completed with exit code 1"这种毫无信息量的内容。如果没有 token/`gh` CLI,应该直接请用户把失败的测试输出贴过来,而不是继续猜——这次正是用户贴出的报错日志,让排查在几轮空猜之后立刻定位到了真正的根因。

## 核对路径解析逻辑是否符合目标工具的真实行为

当 `mirr` 的路径解析代码声称要复刻 uv/pip/npm/conda 某个配置文件的位置时,不要凭记忆或者"约定俗成"的印象(比如"Linux 用 XDG,macOS 用 Application Support")就下结论,动手前先去查这个工具自己的源码或官方文档。例子:pip 自己的 `pip._internal.utils.appdirs._macos_user_config_dir` 只有在 `~/Library/Application Support/pip` 目录已经存在时才会用它,不存在则退回硬编码的 `~/.config/pip`(这个兜底分支甚至不看 `$XDG_CONFIG_HOME`)——这种细节光凭记忆很容易漏掉或搞错。当时是直接拉了 pip 的真实源码确认的(`curl https://raw.githubusercontent.com/pypa/pip/main/src/pip/_internal/utils/appdirs.py`),而不是凭印象假设。
