"""tmux interaction module for muxnow."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger("muxnow.tmux")


class TmuxError(RuntimeError):
    pass


def run_tmux(*args: str, check: bool = True) -> str:
    """Execute a tmux CLI command and return stdout."""
    tmux_bin = shutil.which("tmux")
    if not tmux_bin:
        raise TmuxError("tmux executable not found on system PATH.")

    cmd = [tmux_bin] + list(args)
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip() or e.stdout.strip()
        logger.error("tmux command failed (%s): %s", cmd, err_msg)
        raise TmuxError(f"tmux command {' '.join(cmd)} failed: {err_msg}") from e


def is_inside_tmux() -> bool:
    """Check if the current process is running inside a tmux session."""
    return bool(os.environ.get("TMUX"))


def get_current_pane_id() -> str:
    """Return the current tmux pane id (%0, %1, etc.)."""
    return run_tmux("display-message", "-p", "#{pane_id}")


def get_current_session_name() -> str:
    """Return the active tmux session name."""
    return run_tmux("display-message", "-p", "#{session_name}")


def get_current_window_id() -> str:
    """Return the active tmux window id."""
    return run_tmux("display-message", "-p", "#{window_id}")


def get_pane_user_option(pane_id: str, option_name: str) -> Optional[str]:
    """Read a pane user option (e.g. @muxnow_state)."""
    try:
        val = run_tmux("show-options", "-p", "-t", pane_id, "-v", option_name, check=False)
        return val if val else None
    except Exception:
        return None


def set_pane_user_option(pane_id: str, option_name: str, value: str) -> None:
    """Set a pane user option (e.g. @muxnow_state)."""
    run_tmux("set-option", "-p", "-t", pane_id, option_name, value)


def start_capture_pipe(target_pane: str, log_path: str) -> None:
    """Start pipe-pane capture for target_pane into log_path."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    pipe_cmd = f"cat >> '{log_path}'"
    run_tmux("pipe-pane", "-t", target_pane, "-o", pipe_cmd)
    set_pane_user_option(target_pane, "@muxnow_state", "on")
    update_pane_border(target_pane, is_capturing=True)


def stop_capture_pipe(target_pane: str) -> None:
    """Stop pipe-pane capture for target_pane (hardware-like stop)."""
    # Empty string terminates the pipe
    run_tmux("pipe-pane", "-t", target_pane)
    set_pane_user_option(target_pane, "@muxnow_state", "off")
    update_pane_border(target_pane, is_capturing=False)


def is_capture_active(target_pane: str) -> bool:
    """Check whether pipe-pane capture is active on target_pane."""
    state = get_pane_user_option(target_pane, "@muxnow_state")
    return state == "on"


def update_pane_border(target_pane: str, is_capturing: bool) -> None:
    """Update border title to visibly indicate capture state."""
    status_icon = "⏺ [muxnow: ON]" if is_capturing else "⏸ [muxnow: PAUSED]"
    try:
        run_tmux("set-option", "-p", "-t", target_pane, "pane-border-status", "top", check=False)
        run_tmux(
            "set-option",
            "-p",
            "-t",
            target_pane,
            "pane-border-format",
            f" #{target_pane} · {status_icon} ",
            check=False,
        )
    except Exception as e:
        logger.debug("Border update failed (tmux older or non-critical): %s", e)


def insert_command_to_pane(target_pane: str, command: str) -> None:
    """Insert command string into target pane input line WITHOUT pressing Enter."""
    # Use -l flag for literal string insertion to prevent key interpretation
    run_tmux("send-keys", "-t", target_pane, "-l", "--", command)


def execute_command_in_pane(target_pane: str, command: str) -> None:
    """Insert command string into target pane and trigger Enter execution."""
    run_tmux("send-keys", "-t", target_pane, "-l", "--", command)
    run_tmux("send-keys", "-t", target_pane, "Enter")


def create_sidecar_layout(
    session_name: str,
    assistant_cmd: str,
    height_lines: int = 12,
) -> Tuple[str, str]:
    """Create a split-window layout: top pane for assistant, bottom for shell."""
    # Create top pane (size in lines, -b for above)
    top_pane = run_tmux(
        "split-window",
        "-b",
        "-v",
        "-l",
        str(height_lines),
        "-P",
        "-F",
        "#{pane_id}",
        assistant_cmd,
    )
    shell_pane = run_tmux("display-message", "-p", "#{pane_id}")
    return top_pane, shell_pane
