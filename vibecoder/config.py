"""Configuration management for VibeCoder."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Application configuration."""

    # API Keys
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )

    # Database
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "VIBECODER_DATABASE_URL",
            f"sqlite:///{Path.home()}/.vibecoder/vibecoder.db",
        )
    )

    # Server
    server_host: str = field(
        default_factory=lambda: os.getenv("VIBECODER_HOST", "127.0.0.1")
    )
    server_port: int = field(
        default_factory=lambda: int(os.getenv("VIBECODER_PORT", "8000"))
    )

    # Execution
    default_max_iterations: int = field(
        default_factory=lambda: int(os.getenv("VIBECODER_MAX_ITERATIONS", "10"))
    )
    default_timeout_per_iteration: int = field(
        default_factory=lambda: int(os.getenv("VIBECODER_ITERATION_TIMEOUT", "300"))
    )

    # Claude settings
    claude_model: str = field(
        default_factory=lambda: os.getenv("VIBECODER_CLAUDE_MODEL", "claude-sonnet-4-20250514")
    )
    claude_max_tokens: int = field(
        default_factory=lambda: int(os.getenv("VIBECODER_CLAUDE_MAX_TOKENS", "4096"))
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.getenv("VIBECODER_LOG_LEVEL", "INFO")
    )

    # Data directory
    data_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("VIBECODER_DATA_DIR", str(Path.home() / ".vibecoder"))
        )
    )

    # Dangerous command patterns that require approval
    dangerous_patterns: list[str] = field(
        default_factory=lambda: [
            "rm -rf",
            "rm -r",
            "sudo",
            "chmod 777",
            "curl.*|.*sh",
            "wget.*|.*sh",
            "> /dev/",
            "mkfs",
            "dd if=",
            ":(){ :|:& };:",
        ]
    )

    def __post_init__(self) -> None:
        """Create data directory if it doesn't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def artifacts_dir(self) -> Path:
        """Directory for storing generated artifacts."""
        path = self.data_dir / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def logs_dir(self) -> Path:
        """Directory for log files."""
        path = self.data_dir / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path


# Global configuration instance
config = Config()
