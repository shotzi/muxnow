"""Command line interface for aimux."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import click

from aimux import __version__
from aimux.config import AimuxConfig
from aimux.tmux import (
    TmuxError,
    create_sidecar_layout,
    get_current_pane_id,
    get_current_session_name,
    is_capture_active,
    is_inside_tmux,
    run_tmux,
    start_capture_pipe,
    stop_capture_pipe,
)
from aimux.tui import SidecarApp

DEFAULT_LOG_DIR = Path.home() / ".local" / "state" / "aimux"


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """aimux - AI-Sidecar für tmux mit verlässlicher Pause und Fail-Closed Redaktion."""
    pass


@main.command()
@click.option("--session", "-s", default="aimux", help="Name der tmux Session")
def start(session: str) -> None:
    """Neue aimux-Session mit automatischem Sidecar-Layout starten."""
    DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = DEFAULT_LOG_DIR / f"{session}_capture.log"

    # Start new detached tmux session
    try:
        run_tmux("new-session", "-d", "-s", session)
    except TmuxError as e:
        click.echo(f"Fehler beim Erstellen der Session: {e}", err=True)
        sys.exit(1)

    # Get bottom shell pane id
    shell_pane = run_tmux("display-message", "-t", session, "-p", "#{pane_id}")

    # Start capture pipe on shell pane
    start_capture_pipe(shell_pane, str(log_file))

    # Split window for sidecar top pane
    assistant_cmd = f"aimux sidecar --pane '{shell_pane}' --log '{log_file}'"
    run_tmux("split-window", "-t", session, "-b", "-v", "-l", "12", assistant_cmd)

    # Switch focus back to shell pane
    run_tmux("select-pane", "-t", shell_pane)

    click.echo(f"aimux Session '{session}' gestartet. Verbinde...")
    # Attach to session
    os.execvp("tmux", ["tmux", "attach-session", "-t", session])


@main.command()
@click.option("--pane", "-p", default=None, help="Ziel-Pane ID")
def attach(pane: Optional[str]) -> None:
    """Sidecar in bestehender tmux-Session einhängen."""
    if not is_inside_tmux():
        click.echo("Fehler: Muss innerhalb einer tmux-Session ausgeführt werden.", err=True)
        sys.exit(1)

    target_pane = pane or get_current_pane_id()
    session = get_current_session_name()
    DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = DEFAULT_LOG_DIR / f"{session}_{target_pane.replace('%', 'p')}_capture.log"

    start_capture_pipe(target_pane, str(log_file))

    assistant_cmd = f"aimux sidecar --pane '{target_pane}' --log '{log_file}'"
    run_tmux("split-window", "-b", "-v", "-l", "12", assistant_cmd)
    run_tmux("select-pane", "-t", target_pane)
    click.echo(f"aimux Sidecar für Pane {target_pane} aktiviert.")


@main.command()
@click.option("--pane", required=True, help="Ziel-Pane ID")
@click.option("--log", required=True, help="Pfad zur Capture-Log-Datei")
def sidecar(pane: str, log: str) -> None:
    """Interner TUI-Modus für das Sidecar-Fenster."""
    app = SidecarApp(target_pane=pane, capture_log=log)
    app.run()


@main.command()
@click.option("--pane", "-p", default=None, help="Ziel-Pane ID")
def toggle(pane: Optional[str]) -> None:
    """Mitschnitt pausieren oder fortsetzen (Hardware-artiger Pipe-Stopp)."""
    if not is_inside_tmux():
        click.echo("Nicht in tmux.", err=True)
        sys.exit(1)

    target_pane = pane or get_current_pane_id()
    session = get_current_session_name()
    log_file = DEFAULT_LOG_DIR / f"{session}_{target_pane.replace('%', 'p')}_capture.log"

    if is_capture_active(target_pane):
        stop_capture_pipe(target_pane)
        click.echo(f"aimux: Mitschnitt für Pane {target_pane} PAUSIERT ⏸")
    else:
        start_capture_pipe(target_pane, str(log_file))
        click.echo(f"aimux: Mitschnitt für Pane {target_pane} AKTIV ⏺")


@main.command()
@click.option("--pane", "-p", default=None, help="Ziel-Pane ID")
def status(pane: Optional[str]) -> None:
    """Status des Mitschnitts für tmux-Statuszeile oder Scripts."""
    if not is_inside_tmux():
        click.echo("inactive")
        return

    target_pane = pane or get_current_pane_id()
    if is_capture_active(target_pane):
        click.echo("#[fg=green]⏺ [aimux: ON]#[default]")
    else:
        click.echo("#[fg=yellow]⏸ [aimux: PAUSED]#[default]")


if __name__ == "__main__":
    main()
