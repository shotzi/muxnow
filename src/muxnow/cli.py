"""Command line interface for muxnow."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import click

from muxnow import __version__
from muxnow.config import MuxnowConfig
from muxnow.i18n import t
from muxnow.tmux import (
    TmuxError,
    create_sidecar_layout,
    execute_command_in_pane,
    find_shell_pane,
    get_current_pane_id,
    get_current_session_name,
    insert_command_to_pane,
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
    """muxnow - AI sidecar for tmux with reliable pause and fail-closed secret redaction."""
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
@click.option("--session", "-s", default="muxnow", help="Name of tmux session")
@click.option("--restart", "-r", is_flag=True, help="Terminate existing session beforehand")
def start(session: str, restart: bool) -> None:
    """Start a new muxnow session or attach to an existing one."""
    cfg = MuxnowConfig.load()
    lang = cfg.language

    if session_exists(session):
        if restart:
            click.echo(t("session_stopping", lang, session=session))
            run_tmux("kill-session", "-t", session, check=False)
        else:
            click.echo(t("session_exists", lang, session=session))
            os.execvp("tmux", ["tmux", "attach-session", "-t", session])

    DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = DEFAULT_LOG_DIR / f"{session}_capture.log"

    # Start new detached tmux session
    try:
        run_tmux("new-session", "-d", "-s", session)
    except TmuxError as e:
        click.echo(f"Error creating session: {e}", err=True)
        sys.exit(1)

    # Get bottom shell pane id
    shell_pane = run_tmux("display-message", "-t", session, "-p", "#{pane_id}")

    # Start capture pipe on shell pane
    start_capture_pipe(shell_pane, str(log_file))

    # Split window for sidecar top pane
    assistant_cmd = f"muxnow sidecar --pane '{shell_pane}' --log '{log_file}'"
    run_tmux("split-window", "-t", session, "-b", "-v", "-l", "14", assistant_cmd)

    # Switch focus back to shell pane
    run_tmux("select-pane", "-t", shell_pane)

    click.echo(t("session_started", lang, session=session))
    # Attach to session
    os.execvp("tmux", ["tmux", "attach-session", "-t", session])


@main.command()
@click.option("--session", "-s", default="muxnow", help="Name of tmux session")
def stop(session: str) -> None:
    """Terminate running muxnow session."""
    cfg = MuxnowConfig.load()
    lang = cfg.language
    if not session_exists(session):
        click.echo(t("no_session", lang, session=session))
        return
    try:
        run_tmux("kill-session", "-t", session)
        click.echo(t("session_stopped", lang, session=session))
    except Exception as e:
        click.echo(f"Error stopping session: {e}", err=True)


@main.command()
@click.option("--session", "-s", default="muxnow", help="Name of tmux session")
def kill(session: str) -> None:
    """Terminate running muxnow session (alias for stop)."""
    cfg = MuxnowConfig.load()
    lang = cfg.language
    if not session_exists(session):
        click.echo(t("no_session", lang, session=session))
        return
    try:
        run_tmux("kill-session", "-t", session)
        click.echo(t("session_stopped", lang, session=session))
    except Exception as e:
        click.echo(f"Error stopping session: {e}", err=True)


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
    run_tmux("split-window", "-b", "-v", "-l", "14", assistant_cmd)
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
@click.option("--pane", "-p", default=None, help="Target pane ID")
def toggle(pane: Optional[str]) -> None:
    """Pause or resume capture pipe."""
    if not is_inside_tmux():
        click.echo("Not inside tmux.", err=True)
        return

    cfg = MuxnowConfig.load()
    lang = cfg.language
    target_pane = pane or find_shell_pane()
    session = get_current_session_name()
    log_file = DEFAULT_LOG_DIR / f"{session}_capture.log"

    if is_capture_active(target_pane):
        stop_capture_pipe(target_pane)
        run_tmux("display-message", "-d", "1500", t("toast_paused", lang), check=False)
    else:
        start_capture_pipe(target_pane, str(log_file))
        run_tmux("display-message", "-d", "1500", t("toast_active", lang), check=False)


@main.command()
@click.option("--pane", "-p", default=None, help="Target pane ID")
def insert(pane: Optional[str]) -> None:
    """Insert suggestion into active shell prompt without executing."""
    if not is_inside_tmux():
        click.echo("Not inside tmux.", err=True)
        return

    target_pane = pane or find_shell_pane()
    sugg_file = DEFAULT_LOG_DIR / f"{target_pane.replace('%', 'p')}_suggestion.txt"
    if sugg_file.exists():
        cmd = sugg_file.read_text(encoding="utf-8").strip()
        if cmd:
            insert_command_to_pane(target_pane, cmd)
            run_tmux("display-message", "-d", "1500", f"muxnow: {cmd}", check=False)
            return
    run_tmux("display-message", "-d", "1500", "muxnow: (no suggestion)", check=False)


@main.command()
@click.option("--pane", "-p", default=None, help="Target pane ID")
def execute(pane: Optional[str]) -> None:
    """Execute suggestion directly in shell."""
    if not is_inside_tmux():
        click.echo("Not inside tmux.", err=True)
        return

    target_pane = pane or find_shell_pane()
    sugg_file = DEFAULT_LOG_DIR / f"{target_pane.replace('%', 'p')}_suggestion.txt"
    if sugg_file.exists():
        cmd = sugg_file.read_text(encoding="utf-8").strip()
        if cmd:
            execute_command_in_pane(target_pane, cmd)
            return
    run_tmux("display-message", "-d", "1500", "muxnow: (no suggestion)", check=False)


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
