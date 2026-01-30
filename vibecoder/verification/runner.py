"""Shell command execution for verification."""

import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..storage.logger import logger


@dataclass
class CommandResult:
    """Result of a command execution."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def success(self) -> bool:
        """Check if the command succeeded."""
        return self.exit_code == 0 and not self.timed_out

    @property
    def output(self) -> str:
        """Get combined output."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"STDERR:\n{self.stderr}")
        if self.timed_out:
            parts.append("TIMED OUT")
        return "\n".join(parts)


class CommandRunner:
    """Execute shell commands for verification."""

    def __init__(
        self,
        working_directory: str,
        timeout: int = 300,
        env: Optional[dict] = None,
    ) -> None:
        """Initialize the command runner.

        Args:
            working_directory: Directory to run commands in
            timeout: Default timeout in seconds
            env: Additional environment variables
        """
        self.working_directory = Path(working_directory)
        self.timeout = timeout
        self.env = {**os.environ, **(env or {})}

    async def run(
        self,
        command: str,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """Run a shell command asynchronously.

        Args:
            command: The command to run
            timeout: Override default timeout

        Returns:
            CommandResult with the execution results
        """
        timeout = timeout or self.timeout

        logger.debug(
            f"Running command: {command}",
            details={"working_directory": str(self.working_directory)},
        )

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_directory,
                env=self.env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )

                result = CommandResult(
                    command=command,
                    exit_code=process.returncode or 0,
                    stdout=stdout.decode("utf-8", errors="replace"),
                    stderr=stderr.decode("utf-8", errors="replace"),
                )

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                result = CommandResult(
                    command=command,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Command timed out after {timeout} seconds",
                    timed_out=True,
                )

        except Exception as e:
            logger.error(f"Error running command: {e}", exc_info=True)
            result = CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=str(e),
            )

        logger.debug(
            f"Command completed: exit_code={result.exit_code}",
            details={
                "command": command,
                "success": result.success,
                "timed_out": result.timed_out,
            },
        )

        return result

    def run_sync(
        self,
        command: str,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """Run a shell command synchronously.

        Args:
            command: The command to run
            timeout: Override default timeout

        Returns:
            CommandResult with the execution results
        """
        timeout = timeout or self.timeout

        logger.debug(
            f"Running command (sync): {command}",
            details={"working_directory": str(self.working_directory)},
        )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                timeout=timeout,
                cwd=self.working_directory,
                env=self.env,
            )

            return CommandResult(
                command=command,
                exit_code=result.returncode,
                stdout=result.stdout.decode("utf-8", errors="replace"),
                stderr=result.stderr.decode("utf-8", errors="replace"),
            )

        except subprocess.TimeoutExpired:
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                timed_out=True,
            )

        except Exception as e:
            logger.error(f"Error running command: {e}", exc_info=True)
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=str(e),
            )

    async def run_verification_commands(
        self,
        commands: list[str],
        stop_on_failure: bool = True,
    ) -> list[CommandResult]:
        """Run a list of verification commands.

        Args:
            commands: List of commands to run
            stop_on_failure: Stop on first failure if True

        Returns:
            List of CommandResults
        """
        results = []

        for command in commands:
            result = await self.run(command)
            results.append(result)

            if stop_on_failure and not result.success:
                break

        return results

    def get_verification_summary(
        self, results: list[CommandResult]
    ) -> tuple[bool, str]:
        """Generate a summary of verification results.

        Args:
            results: List of CommandResults

        Returns:
            Tuple of (all_passed, summary_text)
        """
        all_passed = all(r.success for r in results)
        lines = []

        for i, result in enumerate(results, 1):
            status = "✓ PASS" if result.success else "✗ FAIL"
            lines.append(f"{i}. [{status}] {result.command}")

            if not result.success:
                # Include truncated output for failures
                output = result.output
                if len(output) > 1000:
                    output = output[:1000] + "\n... (truncated)"
                lines.append(f"   Output:\n{self._indent(output, '   ')}")

        summary = "\n".join(lines)
        return all_passed, summary

    def _indent(self, text: str, prefix: str) -> str:
        """Indent text with a prefix."""
        return "\n".join(prefix + line for line in text.split("\n"))
