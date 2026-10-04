"""Command line interface for muxnow."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import click

from muxnow import __version__
from muxnow.config import MuxnowConfig
from muxnow.tmux import (
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
from muxnow.tui import SidecarApp

DEFAULT_LOG_DIR = Path.home() / ".local" / "state" / "muxnow"


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """muxnow - AI-Sidecar für tmux mit verlässlicher Pause und Fail-Closed Redaktion."""
    pass


def session_exists(session_name: str) -> bool:
    """Check if a tmux session already exists."""
    import subprocess
    res = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return res.returncode == 0


@main.command()
@click.option("--session", "-s", default="muxnow", help="Name der tmux Session")
@click.option("--restart", "-r", is_flag=True, help="Bestehende Session vorher beenden")
def start(session: str, restart: bool) -> None:
    """Neue muxnow-Session starten oder mit bestehender Session verbinden."""
    if session_exists(session):
        if restart:
            click.echo(f"Beende bestehende Session '{session}'...")
            run_tmux("kill-session", "-t", session, check=False)
        else:
            click.echo(f"muxnow Session '{session}' existiert bereits. Verbinde...")
            os.execvp("tmux", ["tmux", "attach-session", "-t", session])

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
    assistant_cmd = f"muxnow sidecar --pane '{shell_pane}' --log '{log_file}'"
    run_tmux("split-window", "-t", session, "-b", "-v", "-l", "12", assistant_cmd)

    # Switch focus back to shell pane
    run_tmux("select-pane", "-t", shell_pane)

    click.echo(f"muxnow Session '{session}' gestartet. Verbinde...")
    # Attach to session
    os.execvp("tmux", ["tmux", "attach-session", "-t", session])


@main.command()
@click.option("--session", "-s", default="muxnow", help="Name der tmux Session")
def stop(session: str) -> None:
    """Laufende muxnow-Session beenden."""
    if not session_exists(session):
        click.echo(f"Keine laufende Session '{session}' gefunden.")
        return
    try:
        run_tmux("kill-session", "-t", session)
        click.echo(f"muxnow Session '{session}' wurde beendet.")
    except Exception as e:
        click.echo(f"Fehler beim Beenden der Session: {e}", err=True)


@main.command()
@click.option("--session", "-s", default="muxnow", help="Name der tmux Session")
def kill(session: str) -> None:
    """Laufende muxnow-Session beenden (Alias für stop)."""
    if not session_exists(session):
        click.echo(f"Keine laufende Session '{session}' gefunden.")
        return
    try:
        run_tmux("kill-session", "-t", session)
        click.echo(f"muxnow Session '{session}' wurde beendet.")
    except Exception as e:
        click.echo(f"Fehler beim Beenden der Session: {e}", err=True)


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

    assistant_cmd = f"muxnow sidecar --pane '{target_pane}' --log '{log_file}'"
    run_tmux("split-window", "-b", "-v", "-l", "12", assistant_cmd)
    run_tmux("select-pane", "-t", target_pane)
    click.echo(f"muxnow Sidecar für Pane {target_pane} aktiviert.")


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
        click.echo(f"muxnow: Mitschnitt für Pane {target_pane} PAUSIERT ⏸")
    else:
        start_capture_pipe(target_pane, str(log_file))
        click.echo(f"muxnow: Mitschnitt für Pane {target_pane} AKTIV ⏺")


@main.command()
@click.option("--pane", "-p", default=None, help="Ziel-Pane ID")
def status(pane: Optional[str]) -> None:
    """Status des Mitschnitts für tmux-Statuszeile oder Scripts."""
    if not is_inside_tmux():
        click.echo("inactive")
        return

    target_pane = pane or get_current_pane_id()
    if is_capture_active(target_pane):
        click.echo("#[fg=green]⏺ [muxnow: ON]#[default]")
    else:
        click.echo("#[fg=yellow]⏸ [muxnow: PAUSED]#[default]")


if __name__ == "__main__":
    main()
