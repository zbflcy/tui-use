# tui-use

让 AI Agent 能够操控终端 TUI 程序的工具集。包含一个 CLI 工具 `tui-agent` 和一个配套的 Agent Skill `tui-use`。

## 项目结构

```
tui-use/
├── tui-agent/          # CLI 工具：通过 PTY 操控 TUI 程序
│   ├── tui_agent/      # 源码
│   │   ├── cli.py      # 命令行入口
│   │   ├── daemon.py   # Unix Socket 守护进程
│   │   ├── session.py  # 核心会话管理（PTY + pyte 虚拟终端）
│   │   ├── protocol.py # JSON 通信协议
│   │   ├── keys.py     # 键名 → 终端转义序列映射
│   │   └── mouse.py    # SGR 鼠标事件序列生成
│   ├── tests/          # 测试套件（65 个用例）
│   └── pyproject.toml
├── tui-use-skill/      # Agent Skill：教 Agent 如何使用 tui-agent
│   └── SKILL.md
└── README.md
```

## 工作原理

```
AI Agent  ──Bash──>  tui-agent CLI  ──Unix Socket──>  Daemon  ──PTY──>  TUI 程序
          <──stdout──                <──JSON 响应──            <──pyte──  (vim/htop/nano...)
```

`tui-agent` 采用 Client-Daemon 架构：
- **Daemon** 通过 PTY（伪终端）启动 TUI 子进程，使用 [pyte](https://github.com/selectel/pyte) 虚拟终端模拟器解析屏幕输出
- **CLI** 通过 Unix Domain Socket 向 Daemon 发送 JSON 请求，执行截屏、输入、按键等操作
- Daemon 在首次使用时自动启动，无需手动管理

## 安装

```bash
# 要求 Python >= 3.10
pip install -e tui-agent/
```

验证安装：
```bash
tui-agent --help
```

## 快速上手

```bash
# 1. 启动一个 bash 会话
tui-agent start --name sh -- bash --norc --noprofile

# 2. 等待就绪
tui-agent wait --name sh --stable 1.0

# 3. 执行命令
tui-agent type --name sh --enter "echo hello"

# 4. 查看屏幕
tui-agent capture --name sh

# 5. 关闭会话
tui-agent stop --name sh
```

## 命令一览

| 命令 | 功能 |
|------|------|
| `start --name NAME -- CMD` | 启动 TUI 会话 |
| `stop --name NAME` / `stop --all` | 停止会话 |
| `list` | 列出所有活跃会话 |
| `status --name NAME` | 查询会话状态 |
| `capture --name NAME [--cursor]` | 截取屏幕内容 |
| `scrollback --name NAME [--lines N]` | 读取滚回缓冲区 |
| `type --name NAME [--enter] TEXT` | 输入文本 |
| `key --name NAME KEY [KEY...]` | 发送特殊按键 |
| `paste --name NAME TEXT` | 粘贴文本（Bracketed Paste 模式） |
| `click --name NAME --row R --col C` | 鼠标点击 |
| `scroll-up/down --name NAME --row R --col C` | 鼠标滚动 |
| `wait --name NAME --text/--absent/--stable` | 等待条件满足 |
| `resize --name NAME --cols C --rows R` | 调整终端大小 |
| `diff --name NAME --snapshot SNAP` | 与快照对比差异 |

### 支持的按键

- **导航键**: `up`, `down`, `left`, `right`, `home`, `end`, `pageup`, `pagedown`
- **编辑键**: `enter`, `tab`, `backspace`, `delete`, `insert`, `space`, `escape`
- **功能键**: `f1` ~ `f12`
- **Ctrl 组合**: `ctrl-a` ~ `ctrl-z`

> `key` 命令只接受上述特殊键名。普通字符（如 `i`, `o`, `:wq`）请使用 `type` 命令发送。

## 使用示例

### 用 nano 编辑文件

```bash
tui-agent start --name ed --cols 120 --rows 40 -- nano myfile.txt
tui-agent wait --name ed --stable 1.0

# 输入内容
tui-agent type --name ed "Hello, World!"

# 保存：Ctrl-O → Enter
tui-agent key --name ed ctrl-o
tui-agent wait --name ed --stable 0.5
tui-agent key --name ed enter
tui-agent wait --name ed --text "Wrote"

# 退出：Ctrl-X
tui-agent key --name ed ctrl-x
tui-agent stop --name ed
```

### 监控系统进程

```bash
tui-agent start --name mon --cols 160 --rows 50 -- htop
tui-agent wait --name mon --stable 2.0
tui-agent capture --name mon

# 搜索进程
tui-agent key --name mon f3
tui-agent type --name mon "python"
tui-agent key --name mon enter
tui-agent capture --name mon

tui-agent type --name mon "q"
tui-agent stop --name mon
```

### 快照与 Diff

```bash
tui-agent capture --name sh --save before
tui-agent type --name sh --enter "some command"
tui-agent wait --name sh --stable 1.0
tui-agent diff --name sh --snapshot before
```

## Agent Skill

`tui-use-skill/` 目录包含一个 Agent Skill，可安装到 Claude Code / Ducc 等 Agent 框架中，让 AI Agent 自动掌握使用 `tui-agent` 操控 TUI 程序的能力。

### 安装 Skill

```bash
# 复制到 skills 目录
cp -r tui-use-skill ~/.claude/skills/tui-use
```

安装后，当你要求 Agent 操作 TUI 程序时（如 "帮我打开 htop 看看 CPU 使用情况"），Skill 会自动触发并引导 Agent 使用 `tui-agent` 完成操作。

## 运行测试

```bash
cd tui-agent
pip install -e ".[dev]"
pytest tests/ -v
```

全部 65 个测试覆盖：协议编解码、键名解析、鼠标事件生成、会话管理（PTY 生命周期、屏幕截取、输入输出、等待机制、快照 diff、滚回历史）、Daemon 请求分发、CLI 端到端。

## 依赖

- Python >= 3.10
- [pyte](https://github.com/selectel/pyte) >= 0.8 — VT100/xterm 终端模拟器
- [pexpect](https://github.com/pexpect/pexpect) >= 4.8 — PTY 子进程管理
- [click](https://github.com/pallets/click) >= 8.0 — CLI 框架

## License

MIT
