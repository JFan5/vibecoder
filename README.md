# VibeCoder

Autonomous AI Coding Orchestration System - A Python-based system that orchestrates AI coding tasks with automated verification, feedback loops, and human oversight.

## Features

- **Automated Iteration Loop**: Runs coding tasks through Claude AI with automatic verification
- **Feedback-Driven Fixes**: When verification fails, provides structured feedback to the AI for corrections
- **Permission System**: Requires approval for dangerous operations (file writes outside working directory, shell commands with dangerous patterns)
- **Task Queue**: Manages multiple tasks with priority ordering
- **Web Dashboard**: Real-time monitoring with WebSocket updates
- **CLI Interface**: Full command-line control of the system

## Installation

```bash
cd vibecoder
pip install -e .
```

## Configuration

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

## Usage

### CLI Commands

#### Task Management

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

#### Queue Management

```bash
# Start processing the queue
vibecoder queue start

# View queue status
vibecoder queue status
```

#### Approvals

```bash
# List pending approvals
vibecoder approve list

# Approve an action
vibecoder approve accept <approval_id>

# Deny an action
vibecoder deny <approval_id>
```

#### Web Server

```bash
# Start the web dashboard
vibecoder server start --port 8000

# With auto-reload for development
vibecoder server start --reload
```

### Task Definition (YAML)

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

### API Endpoints

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

## Architecture

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

## Iteration Loop

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

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

### Project Structure

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

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=JFan5/vibecoder&type=Date)](https://star-history.com/#JFan5/vibecoder&Date)

## License

MIT
