"""CLI commands for VibeCoder."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.text import Text

from ..config import config
from ..core.engine import get_engine, Engine
from ..core.task import Task, TaskStatus
from ..storage.database import get_db


console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """VibeCoder: Autonomous AI Coding Orchestration System."""
    pass


# ============== Task Commands ==============


@cli.group()
def task():
    """Manage tasks."""
    pass


@task.command("create")
@click.option("--file", "-f", "yaml_file", type=click.Path(exists=True), help="Create from YAML file")
@click.option("--interactive", "-i", is_flag=True, help="Interactive creation mode")
@click.option("--name", "-n", help="Task name")
@click.option("--description", "-d", help="Task description")
@click.option("--working-dir", "-w", type=click.Path(), help="Working directory")
@click.option("--max-iterations", "-m", type=int, default=10, help="Max iterations")
def task_create(
    yaml_file: Optional[str],
    interactive: bool,
    name: Optional[str],
    description: Optional[str],
    working_dir: Optional[str],
    max_iterations: int,
):
    """Create a new task."""
    engine = get_engine()

    if yaml_file:
        # Create from YAML file
        try:
            task = engine.create_task_from_yaml(yaml_file)
            console.print(f"[green]✓[/green] Created task: {task.id}")
            console.print(f"  Name: {task.name}")
            console.print(f"  Working Directory: {task.working_directory}")
        except Exception as e:
            console.print(f"[red]Error creating task:[/red] {e}")
            sys.exit(1)

    elif interactive:
        # Interactive mode
        console.print("[bold]Create New Task[/bold]\n")

        name = click.prompt("Task name")
        description = click.prompt("Description", default="")
        working_dir = click.prompt("Working directory", default=str(Path.cwd()))
        max_iterations = click.prompt("Max iterations", default=10, type=int)

        # Requirements
        console.print("\nEnter requirements (one per line, empty line to finish):")
        requirements = []
        while True:
            req = click.prompt("", default="", show_default=False)
            if not req:
                break
            requirements.append(req)

        # Verification commands
        console.print("\nEnter verification commands (one per line, empty line to finish):")
        verification_commands = []
        while True:
            cmd = click.prompt("", default="", show_default=False)
            if not cmd:
                break
            verification_commands.append(cmd)

        # Create the task
        task = engine.create_task(
            name=name,
            description=description,
            requirements=requirements,
            verification_commands=verification_commands,
            working_directory=working_dir,
            max_iterations=max_iterations,
        )

        console.print(f"\n[green]✓[/green] Created task: {task.id}")

    elif name:
        # Create from CLI options
        task = engine.create_task(
            name=name,
            description=description or "",
            requirements=[],
            verification_commands=[],
            working_directory=working_dir or str(Path.cwd()),
            max_iterations=max_iterations,
        )
        console.print(f"[green]✓[/green] Created task: {task.id}")

    else:
        console.print("[yellow]Please specify --file, --interactive, or --name[/yellow]")
        sys.exit(1)


@task.command("list")
@click.option("--status", "-s", help="Filter by status")
@click.option("--limit", "-l", type=int, default=20, help="Max number of tasks")
def task_list(status: Optional[str], limit: int):
    """List all tasks."""
    engine = get_engine()
    tasks = engine.list_tasks(status=status, limit=limit)

    if not tasks:
        console.print("[dim]No tasks found[/dim]")
        return

    table = Table(title="Tasks")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Iterations")
    table.add_column("Working Dir", style="dim")

    for t in tasks:
        status_style = {
            TaskStatus.PENDING: "yellow",
            TaskStatus.RUNNING: "blue",
            TaskStatus.COMPLETED: "green",
            TaskStatus.FAILED: "red",
            TaskStatus.NEEDS_APPROVAL: "magenta",
            TaskStatus.CANCELLED: "dim",
        }.get(t.status, "white")

        table.add_row(
            t.id[:8],
            t.name[:30],
            f"[{status_style}]{t.status.value}[/{status_style}]",
            f"{t.current_iteration}/{t.max_iterations}",
            t.working_directory[:30] if t.working_directory else "-",
        )

    console.print(table)


@task.command("status")
@click.argument("task_id")
def task_status(task_id: str):
    """Show detailed status of a task."""
    engine = get_engine()

    # Find task by partial ID
    tasks = engine.list_tasks()
    matching = [t for t in tasks if t.id.startswith(task_id)]

    if not matching:
        console.print(f"[red]Task not found: {task_id}[/red]")
        sys.exit(1)

    if len(matching) > 1:
        console.print(f"[yellow]Multiple tasks match, please be more specific[/yellow]")
        for t in matching:
            console.print(f"  {t.id} - {t.name}")
        sys.exit(1)

    task = matching[0]

    # Display task details
    panel_content = f"""[bold]Name:[/bold] {task.name}
[bold]ID:[/bold] {task.id}
[bold]Status:[/bold] {task.status.value}
[bold]Description:[/bold] {task.description or '(none)'}

[bold]Progress:[/bold] {task.current_iteration}/{task.max_iterations} iterations
[bold]Working Directory:[/bold] {task.working_directory}

[bold]Requirements:[/bold]
{chr(10).join(f'  - {r}' for r in task.requirements) or '  (none)'}

[bold]Verification Commands:[/bold]
{chr(10).join(f'  - {c}' for c in task.verification_commands) or '  (none)'}

[bold]Artifacts:[/bold]
{chr(10).join(f'  - {a}' for a in task.artifacts) or '  (none)'}
"""
    console.print(Panel(panel_content, title=f"Task: {task.name}"))


@task.command("logs")
@click.argument("task_id")
@click.option("--limit", "-l", type=int, default=50, help="Max number of logs")
def task_logs(task_id: str, limit: int):
    """View logs for a task."""
    engine = get_engine()

    # Find task by partial ID
    tasks = engine.list_tasks()
    matching = [t for t in tasks if t.id.startswith(task_id)]

    if not matching:
        console.print(f"[red]Task not found: {task_id}[/red]")
        sys.exit(1)

    task = matching[0]
    logs = engine.get_logs(task_id=task.id, limit=limit)

    if not logs:
        console.print("[dim]No logs found[/dim]")
        return

    for log in reversed(logs):  # Show oldest first
        level_style = {
            "DEBUG": "dim",
            "INFO": "blue",
            "WARNING": "yellow",
            "ERROR": "red",
        }.get(log.level, "white")

        timestamp = log.created_at.strftime("%H:%M:%S") if log.created_at else ""
        console.print(f"[dim]{timestamp}[/dim] [{level_style}]{log.level:7}[/{level_style}] {log.message}")


@task.command("cancel")
@click.argument("task_id")
def task_cancel(task_id: str):
    """Cancel a running task."""
    engine = get_engine()

    tasks = engine.list_tasks()
    matching = [t for t in tasks if t.id.startswith(task_id)]

    if not matching:
        console.print(f"[red]Task not found: {task_id}[/red]")
        sys.exit(1)

    task = matching[0]
    if engine.cancel_task(task.id):
        console.print(f"[green]✓[/green] Task cancelled: {task.id}")
    else:
        console.print(f"[red]Failed to cancel task[/red]")


# ============== Queue Commands ==============


@cli.group()
def queue():
    """Manage the task queue."""
    pass


@queue.command("start")
def queue_start():
    """Start processing the queue."""
    engine = get_engine()

    console.print("[bold]Starting VibeCoder queue processor...[/bold]")
    console.print("Press Ctrl+C to stop\n")

    def on_complete(task):
        console.print(f"[green]✓[/green] Task completed: {task.name}")

    def on_failed(task, reason):
        console.print(f"[red]✗[/red] Task failed: {task.name} ({reason})")

    engine.on_task_complete(on_complete)
    engine.on_task_failed(on_failed)

    try:
        asyncio.run(engine.start())
    except KeyboardInterrupt:
        engine.stop()
        console.print("\n[yellow]Queue processing stopped[/yellow]")


@queue.command("stop")
def queue_stop():
    """Stop processing the queue."""
    # This would need IPC to communicate with a running process
    console.print("[yellow]Note: Use Ctrl+C to stop a running queue process[/yellow]")


@queue.command("status")
def queue_status():
    """Show queue status."""
    engine = get_engine()
    stats = engine.get_status()

    console.print(f"[bold]Queue Status:[/bold] {stats.status.value}")
    console.print(f"  Pending: {stats.pending_count}")
    console.print(f"  Running: {stats.running_count}")
    console.print(f"  Completed: {stats.completed_count}")
    console.print(f"  Failed: {stats.failed_count}")
    console.print(f"  Total Processed: {stats.total_processed}")


# ============== Approval Commands ==============


@cli.group()
def approve():
    """Manage approvals."""
    pass


@approve.command("list")
def approve_list():
    """List pending approvals."""
    engine = get_engine()
    approvals = engine.get_pending_approvals()

    if not approvals:
        console.print("[dim]No pending approvals[/dim]")
        return

    table = Table(title="Pending Approvals")
    table.add_column("ID")
    table.add_column("Task")
    table.add_column("Type")
    table.add_column("Description")

    for a in approvals:
        table.add_row(
            str(a.id),
            a.task_id[:8],
            a.action_type.value,
            a.description[:50],
        )

    console.print(table)


@approve.command("accept")
@click.argument("approval_id", type=int)
def approve_accept(approval_id: int):
    """Approve an action."""
    engine = get_engine()

    if engine.approve(approval_id):
        console.print(f"[green]✓[/green] Approved: {approval_id}")
    else:
        console.print(f"[red]Approval not found: {approval_id}[/red]")


@cli.command("deny")
@click.argument("approval_id", type=int)
def deny_action(approval_id: int):
    """Deny an action."""
    engine = get_engine()

    if engine.deny(approval_id):
        console.print(f"[green]✓[/green] Denied: {approval_id}")
    else:
        console.print(f"[red]Approval not found: {approval_id}[/red]")


# ============== Server Commands ==============


@cli.group()
def server():
    """Manage the web server."""
    pass


@server.command("start")
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to")
@click.option("--port", "-p", type=int, default=8000, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def server_start(host: str, port: int, reload: bool):
    """Start the web dashboard server."""
    import uvicorn

    console.print(f"[bold]Starting VibeCoder web server...[/bold]")
    console.print(f"Dashboard: http://{host}:{port}")
    console.print("Press Ctrl+C to stop\n")

    uvicorn.run(
        "vibecoder.api.server:app",
        host=host,
        port=port,
        reload=reload,
    )


@server.command("stop")
def server_stop():
    """Stop the web server."""
    console.print("[yellow]Note: Use Ctrl+C to stop a running server[/yellow]")


if __name__ == "__main__":
    cli()
