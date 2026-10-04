"""Textual TUI for the muxnow sidecar assistant pane."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Static

from muxnow.audit import AuditLogger
from muxnow.config import MuxnowConfig
from muxnow.guard import CommandGuard
from muxnow.llm import LLMClient
from muxnow.parser import BlockParser, TerminalBlock
from muxnow.redactor import SecretRedactor
from muxnow.tmux import (
    execute_command_in_pane,
    insert_command_to_pane,
    is_capture_active,
    start_capture_pipe,
    stop_capture_pipe,
)


class SidecarApp(App):
    """Textual TUI application for the muxnow sidecar assistant."""

    CSS = """
    Screen {
        background: #111827;
        color: #f3f4f6;
    }
    #assistant_panel {
        height: 100%;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("i", "insert_suggestion", "Einfügen (⇥)", priority=True),
        Binding("enter", "execute_suggestion", "Ausführen (⏎)", priority=True),
        Binding("p", "toggle_pause", "Pause/Start (⏸)", priority=True),
        Binding("c", "copy_suggestion", "Kopieren", priority=True),
        Binding("q", "quit_app", "Beenden", priority=True),
    ]

    def __init__(
        self,
        target_pane: str,
        capture_log: str,
        config: Optional[MuxnowConfig] = None,
    ) -> None:
        super().__init__()
        self.target_pane = target_pane
        self.capture_log = Path(capture_log)
        self.config = config or MuxnowConfig.load()

        self.redactor = SecretRedactor(
            custom_patterns=self.config.capture.redact_patterns,
            fail_closed=self.config.capture.fail_closed,
        )
        self.parser = BlockParser()
        self.guard = CommandGuard(deny_patterns=self.config.guard.deny_patterns)
        self.llm = LLMClient(self.config.model)
        self.audit = AuditLogger(self.config.audit.path)

        self.current_suggestion: str = ""
        self.current_explanation: str = "Warte auf Terminal-Aktivität..."
        self.current_risk: str = "read-only"
        self.is_capturing: bool = True
        self.redaction_count: int = 0
        self.is_confirming_execution: bool = False

    def compose(self) -> ComposeResult:
        yield Static(id="assistant_panel")
        yield Footer()

    async def on_mount(self) -> None:
        self.is_capturing = is_capture_active(self.target_pane)
        self.update_display()
        # Start background tailer
        self.tail_task = asyncio.create_task(self.tail_capture_log())

    def update_display(self) -> None:
        panel_widget = self.query_one("#assistant_panel", Static)

        # Build Status Line
        status_icon = "⏺ AN" if self.is_capturing else "⏸ PAUSIERT"
        status_style = "bold green" if self.is_capturing else "bold yellow"

        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan", width=14)
        table.add_column()

        # Suggestion Row
        risk_color = (
            "bold red"
            if self.current_risk == "destructive"
            else "yellow"
            if self.current_risk == "write"
            else "bold green"
        )

        sugg_text = Text()
        if self.current_suggestion:
            sugg_text.append(self.current_suggestion, style=risk_color)
            sugg_text.append(f"  [{self.current_risk.upper()}]", style="dim " + risk_color)
        else:
            sugg_text.append("(keine Aktion erforderlich)", style="dim")

        table.add_row("Vorschlag", sugg_text)
        table.add_row("Warum", Text(self.current_explanation, style="white"))

        # Redaction info
        if self.redaction_count > 0:
            table.add_row(
                "Sicherheit",
                Text(f"🛡️ {self.redaction_count} Secrets vor Versand geschwärzt", style="bold green"),
            )

        if self.is_confirming_execution:
            table.add_row(
                "BESTÄTIGUNG",
                Text(
                    f"⚠️ Wirklich ausführen? Drücke ENTER zur Bestätigung oder eine beliebige andere Taste zum Abbrechen.",
                    style="bold red blink",
                ),
            )

        title = f"muxnow · Pane {self.target_pane} · Modell: {self.config.model.model} · Mitschnitt: [{status_icon}]"
        panel = Panel(
            table,
            title=title,
            title_align="left",
            border_style="green" if self.is_capturing else "yellow",
        )
        panel_widget.update(panel)

    async def tail_capture_log(self) -> None:
        """Monitor capture log file for new terminal output chunks."""
        last_pos = 0
        while True:
            try:
                if self.capture_log.exists():
                    with open(self.capture_log, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_pos)
                        new_data = f.read()
                        last_pos = f.tell()

                        if new_data:
                            await self.process_terminal_data(new_data)
            except Exception as e:
                pass
            await asyncio.sleep(0.3)

    async def process_terminal_data(self, data: str) -> None:
        """Parse incoming data into blocks and trigger LLM analysis."""
        blocks = self.parser.feed(data)
        if not blocks:
            # Fallback if no OSC 133 sequences present
            blocks = self.parser.parse_plain_stream(data)

        for block in blocks:
            if not self.is_capturing:
                continue

            # Fail-closed secret redaction
            redacted_output = self.redactor.redact(block.output)
            redacted_cmd = self.redactor.redact(block.command)

            if not (redacted_output.is_safe and redacted_cmd.is_safe):
                self.current_explanation = (
                    "⚠️ Fail-Closed ausgelöst: Unredaktierbares Geheimnis erkannt. "
                    "Kein Modell-Versand erfolgt!"
                )
                self.current_suggestion = ""
                self.update_display()
                continue

            self.redaction_count += redacted_output.redaction_count + redacted_cmd.redaction_count

            # Safe block to process
            safe_block = TerminalBlock(
                command=redacted_cmd.text,
                output=redacted_output.text,
                exit_code=block.exit_code,
            )

            # Query LLM
            resp = await self.llm.get_suggestion(
                latest_block=safe_block,
                history=self.parser.completed_blocks[:-1],
            )

            self.current_suggestion = resp.suggestion
            self.current_explanation = resp.explanation
            # Run local guard evaluation
            assessment = self.guard.assess(resp.suggestion)
            self.current_risk = assessment.level

            self.update_display()

    def action_insert_suggestion(self) -> None:
        """Keybind: prefix + i / 'i' -> insert into shell without execution."""
        if not self.current_suggestion:
            return
        insert_command_to_pane(self.target_pane, self.current_suggestion)
        self.audit.log(
            action="inserted",
            risk_level=self.current_risk,
            command_suggested=self.current_suggestion,
            pane_id=self.target_pane,
        )
        self.current_explanation = f"Befehl '{self.current_suggestion}' in Eingabezeile eingefügt."
        self.update_display()

    def action_execute_suggestion(self) -> None:
        """Keybind: Enter -> execute command with safety check."""
        if not self.current_suggestion:
            return

        if not self.is_confirming_execution:
            self.is_confirming_execution = True
            self.update_display()
            return

        # Double confirmed
        self.is_confirming_execution = False
        execute_command_in_pane(self.target_pane, self.current_suggestion)
        self.audit.log(
            action="executed",
            risk_level=self.current_risk,
            command_suggested=self.current_suggestion,
            pane_id=self.target_pane,
        )
        self.current_explanation = f"Befehl '{self.current_suggestion}' ausgeführt."
        self.current_suggestion = ""
        self.update_display()

    def action_toggle_pause(self) -> None:
        """Keybind: prefix + A / 'p' -> toggle capture pipe."""
        if self.is_capturing:
            stop_capture_pipe(self.target_pane)
            self.is_capturing = False
            self.audit.log(action="paused", pane_id=self.target_pane)
        else:
            start_capture_pipe(self.target_pane, str(self.capture_log))
            self.is_capturing = True
            self.audit.log(action="resumed", pane_id=self.target_pane)
        self.update_display()

    def action_copy_suggestion(self) -> None:
        """Copy suggestion to system clipboard."""
        if self.current_suggestion:
            try:
                import subprocess
                p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                p.communicate(self.current_suggestion.encode("utf-8"))
                self.current_explanation = "Befehl in Zwischenablage kopiert."
                self.update_display()
            except Exception:
                pass

    def action_quit_app(self) -> None:
        self.exit()
