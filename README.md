# VibeCoder

Autonomous AI Coding Orchestration System - A Python-based system that orchestrates AI coding tasks with automated verification, feedback loops, and human oversight.

[English](#english) | [中文](#中文)

---

## English

### Features

- **Automated Iteration Loop**: Runs coding tasks through Claude AI with automatic verification
- **Feedback-Driven Fixes**: When verification fails, provides structured feedback to the AI for corrections
- **Permission System**: Requires approval for dangerous operations (file writes outside working directory, shell commands with dangerous patterns)
- **Task Queue**: Manages multiple tasks with priority ordering
- **Web Dashboard**: Real-time monitoring with WebSocket updates
- **CLI Interface**: Full command-line control of the system

### Installation

```bash
cd vibecoder
pip install -e .
```

### Configuration

Set the following environment variables:

```bash
export ANTHROPIC_API_KEY="your-api-key"

# Optional settings
export VIBECODER_DATABASE_URL="sqlite:///~/.vibecoder/vibecoder.db"
export VIBECODER_HOST="127.0.0.1"
export VIBECODER_PORT="8000"
export VIBECODER_MAX_ITERATIONS="10"
export VIBECODER_CLAUDE_MODEL="claude-sonnet-4-20250514"
export VIBECODER_LOG_LEVEL="INFO"
```

### Usage

#### CLI Commands

##### Task Management

```bash
# Create a task from YAML file
vibecoder task create --file task.yaml

# Create a task interactively
vibecoder task create --interactive

# List all tasks
vibecoder task list

# Show task status
vibecoder task status <task_id>

# View task logs
vibecoder task logs <task_id>

# Cancel a task
vibecoder task cancel <task_id>
```

##### Queue Management

```bash
# Start processing the queue
vibecoder queue start

# View queue status
vibecoder queue status
```

##### Approvals

```bash
# List pending approvals
vibecoder approve list

# Approve an action
vibecoder approve accept <approval_id>

# Deny an action
vibecoder deny <approval_id>
```

##### Web Server

```bash
# Start the web dashboard
vibecoder server start --port 8000

# With auto-reload for development
vibecoder server start --reload
```

#### Task Definition (YAML)

```yaml
name: "Add user authentication"
description: |
  Implement JWT-based authentication for the REST API.

requirements:
  - Create /auth/login endpoint accepting email and password
  - Create /auth/register endpoint for new users
  - Implement JWT token generation and validation
  - Add authentication middleware

verification_commands:
  - "pytest tests/test_auth.py -v"
  - "python -c 'from app.auth import create_token; print(create_token({\"user\": 1}))'"

working_directory: "/path/to/project"
max_iterations: 10
timeout_per_iteration: 300
```

#### API Endpoints

The web server exposes a REST API:

- `GET /api/status` - System status
- `GET /api/tasks/` - List tasks
- `POST /api/tasks/` - Create task
- `GET /api/tasks/{id}` - Get task
- `POST /api/tasks/{id}/cancel` - Cancel task
- `DELETE /api/tasks/{id}` - Delete task
- `GET /api/tasks/{id}/iterations` - Get iterations
- `GET /api/approvals/` - List pending approvals
- `POST /api/approvals/{id}/approve` - Approve action
- `POST /api/approvals/{id}/deny` - Deny action
- `GET /api/logs/` - Get logs
- `POST /api/queue/pause` - Pause queue
- `POST /api/queue/resume` - Resume queue

WebSocket endpoint at `/ws` provides real-time updates.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        VibeCoder System                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │   CLI    │  │   Web    │  │   API    │  │  Webhook/Events  ││
│  │          │  │Dashboard │  │ (FastAPI)│  │                  ││
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘│
│       └─────────────┴─────────────┴─────────────────┘          │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐ │
│  │                    Core Engine                             │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐   │ │
│  │  │Task Queue  │  │ Permission │  │  Iteration Manager │   │ │
│  │  │ Manager    │  │  System    │  │  (Feedback Loop)   │   │ │
│  │  └────────────┘  └────────────┘  └────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐ │
│  │                   Execution Layer                          │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐   │ │
│  │  │Claude API  │  │Verification│  │   File Manager     │   │ │
│  │  │  Agent     │  │  Engine    │  │   (Sandboxed)      │   │ │
│  │  └────────────┘  └────────────┘  └────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐ │
│  │                   Persistence Layer                        │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐   │ │
│  │  │  SQLite    │  │   Logs     │  │   Artifacts        │   │ │
│  │  │  Database  │  │  (JSON)    │  │   (Generated Code) │   │ │
│  │  └────────────┘  └────────────┘  └────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Iteration Loop

```
┌─────────────────────────────────────────────────────────┐
│                    Iteration Cycle                       │
│                                                          │
│   ┌─────────┐    ┌─────────┐    ┌──────────────────┐   │
│   │  Task   │───▶│ Claude  │───▶│ Apply Changes    │   │
│   │  Input  │    │   API   │    │ (Write Files)    │   │
│   └─────────┘    └─────────┘    └────────┬─────────┘   │
│                                          │              │
│   ┌─────────────────────────────────────▼───────────┐  │
│   │           Run Verification Commands              │  │
│   │         (pytest, npm test, make, etc.)          │  │
│   └─────────────────────────┬───────────────────────┘  │
│                             │                           │
│              ┌──────────────┴──────────────┐           │
│              ▼                              ▼           │
│       ┌──────────┐                  ┌──────────┐       │
│       │  PASS    │                  │  FAIL    │       │
│       │  ✓ Done  │                  │          │       │
│       └──────────┘                  └────┬─────┘       │
│                                          │              │
│                                          ▼              │
│                                   ┌──────────────┐     │
│                                   │   Generate   │     │
│                                   │   Feedback   │     │
│                                   └──────┬───────┘     │
│                                          │              │
│                                          ▼              │
│                                   ┌──────────────┐     │
│                                   │ iteration++  │     │
│                                   │ Loop Back    │──┐  │
│                                   └──────────────┘  │  │
│        ▲                                            │  │
│        └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Development

#### Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

#### Project Structure

```
vibecoder/
├── pyproject.toml           # Project config
├── vibecoder/
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration
│   ├── core/                # Core components
│   │   ├── task.py          # Task model
│   │   ├── queue.py         # Task queue
│   │   ├── permission.py    # Permissions
│   │   ├── iteration.py     # Iteration loop
│   │   └── engine.py        # Main engine
│   ├── ai/                  # AI integration
│   │   ├── base.py          # Abstract provider
│   │   ├── claude.py        # Claude API
│   │   └── prompts.py       # System prompts
│   ├── verification/        # Verification
│   │   ├── runner.py        # Command runner
│   │   ├── parser.py        # Output parsing
│   │   └── feedback.py      # Feedback generation
│   ├── storage/             # Persistence
│   │   ├── database.py      # SQLite ops
│   │   ├── models.py        # SQLAlchemy models
│   │   └── logger.py        # Structured logging
│   ├── api/                 # REST API
│   │   ├── server.py        # FastAPI app
│   │   ├── routes/          # API routes
│   │   └── websocket.py     # Real-time updates
│   ├── web/static/          # Dashboard
│   └── cli/                 # CLI commands
└── tests/                   # Test suite
```

---

## 中文

### 功能特性

- **自动迭代循环**：通过 Claude AI 执行编码任务，并自动进行验证
- **反馈驱动修复**：验证失败时，向 AI 提供结构化反馈以进行修正
- **权限系统**：对危险操作（工作目录外的文件写入、含危险模式的 Shell 命令）需经审批
- **任务队列**：支持优先级排序的多任务管理
- **Web 仪表盘**：基于 WebSocket 的实时监控
- **CLI 接口**：完整的命令行系统控制

### 安装

```bash
cd vibecoder
pip install -e .
```

### 配置

设置以下环境变量：

```bash
export ANTHROPIC_API_KEY="your-api-key"

# 可选设置
export VIBECODER_DATABASE_URL="sqlite:///~/.vibecoder/vibecoder.db"
export VIBECODER_HOST="127.0.0.1"
export VIBECODER_PORT="8000"
export VIBECODER_MAX_ITERATIONS="10"
export VIBECODER_CLAUDE_MODEL="claude-sonnet-4-20250514"
export VIBECODER_LOG_LEVEL="INFO"
```

### 使用方法

#### CLI 命令

##### 任务管理

```bash
# 从 YAML 文件创建任务
vibecoder task create --file task.yaml

# 交互式创建任务
vibecoder task create --interactive

# 列出所有任务
vibecoder task list

# 查看任务状态
vibecoder task status <task_id>

# 查看任务日志
vibecoder task logs <task_id>

# 取消任务
vibecoder task cancel <task_id>
```

##### 队列管理

```bash
# 启动队列处理
vibecoder queue start

# 查看队列状态
vibecoder queue status
```

##### 审批管理

```bash
# 列出待审批项
vibecoder approve list

# 批准操作
vibecoder approve accept <approval_id>

# 拒绝操作
vibecoder deny <approval_id>
```

##### Web 服务器

```bash
# 启动 Web 仪表盘
vibecoder server start --port 8000

# 开发模式（自动重载）
vibecoder server start --reload
```

#### 任务定义（YAML）

```yaml
name: "添加用户认证"
description: |
  为 REST API 实现基于 JWT 的认证。

requirements:
  - 创建接受邮箱和密码的 /auth/login 端点
  - 创建用于新用户注册的 /auth/register 端点
  - 实现 JWT 令牌的生成与验证
  - 添加认证中间件

verification_commands:
  - "pytest tests/test_auth.py -v"
  - "python -c 'from app.auth import create_token; print(create_token({\"user\": 1}))'"

working_directory: "/path/to/project"
max_iterations: 10
timeout_per_iteration: 300
```

#### API 端点

Web 服务器提供以下 REST API：

- `GET /api/status` - 系统状态
- `GET /api/tasks/` - 任务列表
- `POST /api/tasks/` - 创建任务
- `GET /api/tasks/{id}` - 获取任务详情
- `POST /api/tasks/{id}/cancel` - 取消任务
- `DELETE /api/tasks/{id}` - 删除任务
- `GET /api/tasks/{id}/iterations` - 获取迭代记录
- `GET /api/approvals/` - 待审批列表
- `POST /api/approvals/{id}/approve` - 批准操作
- `POST /api/approvals/{id}/deny` - 拒绝操作
- `GET /api/logs/` - 获取日志
- `POST /api/queue/pause` - 暂停队列
- `POST /api/queue/resume` - 恢复队列

WebSocket 端点 `/ws` 提供实时更新。

### 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        VibeCoder 系统                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │   CLI    │  │   Web    │  │   API    │  │  Webhook/事件    ││
│  │  命令行   │  │  仪表盘   │  │ (FastAPI)│  │                  ││
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘│
│       └─────────────┴─────────────┴─────────────────┘          │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐ │
│  │                      核心引擎                              │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐   │ │
│  │  │ 任务队列    │  │  权限系统   │  │   迭代管理器       │   │ │
│  │  │  管理器     │  │           │  │  （反馈循环）       │   │ │
│  │  └────────────┘  └────────────┘  └────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐ │
│  │                      执行层                                │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐   │ │
│  │  │Claude API  │  │  验证引擎   │  │   文件管理器       │   │ │
│  │  │  代理      │  │           │  │  （沙箱化）        │   │ │
│  │  └────────────┘  └────────────┘  └────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐ │
│  │                      持久化层                              │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐   │ │
│  │  │  SQLite    │  │   日志     │  │    产出物           │   │ │
│  │  │  数据库    │  │  (JSON)    │  │  （生成的代码）     │   │ │
│  │  └────────────┘  └────────────┘  └────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 迭代循环

```
┌─────────────────────────────────────────────────────────┐
│                      迭代周期                            │
│                                                          │
│   ┌─────────┐    ┌─────────┐    ┌──────────────────┐   │
│   │  任务   │───▶│ Claude  │───▶│   应用变更        │   │
│   │  输入   │    │   API   │    │  （写入文件）      │   │
│   └─────────┘    └─────────┘    └────────┬─────────┘   │
│                                          │              │
│   ┌─────────────────────────────────────▼───────────┐  │
│   │            运行验证命令                           │  │
│   │      (pytest, npm test, make 等)                │  │
│   └─────────────────────────┬───────────────────────┘  │
│                             │                           │
│              ┌──────────────┴──────────────┐           │
│              ▼                              ▼           │
│       ┌──────────┐                  ┌──────────┐       │
│       │  通过    │                  │  失败    │       │
│       │  ✓ 完成  │                  │          │       │
│       └──────────┘                  └────┬─────┘       │
│                                          │              │
│                                          ▼              │
│                                   ┌──────────────┐     │
│                                   │   生成反馈    │     │
│                                   └──────┬───────┘     │
│                                          │              │
│                                          ▼              │
│                                   ┌──────────────┐     │
│                                   │ 迭代次数++   │     │
│                                   │ 返回循环     │──┐  │
│                                   └──────────────┘  │  │
│        ▲                                            │  │
│        └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 开发

#### 运行测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

#### 项目结构

```
vibecoder/
├── pyproject.toml           # 项目配置
├── vibecoder/
│   ├── main.py              # 入口文件
│   ├── config.py            # 配置管理
│   ├── core/                # 核心组件
│   │   ├── task.py          # 任务模型
│   │   ├── queue.py         # 任务队列
│   │   ├── permission.py    # 权限管理
│   │   ├── iteration.py     # 迭代循环
│   │   └── engine.py        # 主引擎
│   ├── ai/                  # AI 集成
│   │   ├── base.py          # 抽象提供者
│   │   ├── claude.py        # Claude API
│   │   └── prompts.py       # 系统提示词
│   ├── verification/        # 验证模块
│   │   ├── runner.py        # 命令执行器
│   │   ├── parser.py        # 输出解析器
│   │   └── feedback.py      # 反馈生成器
│   ├── storage/             # 持久化
│   │   ├── database.py      # SQLite 操作
│   │   ├── models.py        # SQLAlchemy 模型
│   │   └── logger.py        # 结构化日志
│   ├── api/                 # REST API
│   │   ├── server.py        # FastAPI 应用
│   │   ├── routes/          # API 路由
│   │   └── websocket.py     # 实时更新
│   ├── web/static/          # 仪表盘
│   └── cli/                 # CLI 命令
└── tests/                   # 测试套件
```

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=JFan5/vibecoder&type=Date)](https://star-history.com/#JFan5/vibecoder&Date)

## License

MIT
