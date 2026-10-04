"""OSC 133 block parser and ANSI sequence sanitizer for muxnow."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

# ANSI escape sequence patterns
ANSI_CSI_REGEX = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
ANSI_OSC_REGEX = re.compile(r"\x1b\][^\x07\x1b]*(\x07|\x1b\\)")
ANSI_GENERAL_REGEX = re.compile(r"\x1b[@-_][0-?]*[ -/]*[@-~]")

# OSC 133 specific markers
# ESC ] 133 ; <char> [; <payload>] (BEL | ESC \)
OSC_133_REGEX = re.compile(
    r"\x1b\]133;([A-D])(?:;([^\x07\x1b]*))?(?:\x07|\x1b\\)"
)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences and normalize line endings."""
    if not text:
        return ""
    # Strip OSC sequences first
    clean = ANSI_OSC_REGEX.sub("", text)
    # Strip CSI and other general escapes
    clean = ANSI_CSI_REGEX.sub("", clean)
    clean = ANSI_GENERAL_REGEX.sub("", clean)
    # Normalize carriage returns and newlines
    clean = clean.replace("\r\n", "\n").replace("\r", "")
    return clean


@dataclass
class TerminalBlock:
    """Represents a coherent terminal execution block: command + output + exit_code."""
    command: str
    output: str
    exit_code: Optional[int] = None
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    raw: str = ""

    @property
    def is_completed(self) -> bool:
        return self.exit_code is not None

    @property
    def is_failed(self) -> bool:
        return self.exit_code is not None and self.exit_code != 0


class BlockParser:
    """Incremental byte-stream parser for OSC 133 terminal blocks.
    Falls back to prompt-boundary detection when OSC 133 markers are absent.
    """

    def __init__(self) -> None:
        self.buffer: str = ""
        self.current_command: Optional[str] = None
        self.current_output: List[str] = []
        self.current_started_at: float = time.time()
        self.completed_blocks: List[TerminalBlock] = []

    def feed(self, chunk: str) -> List[TerminalBlock]:
        """Feed incoming terminal stream chunk and return newly completed blocks."""
        new_blocks: List[TerminalBlock] = []
        self.buffer += chunk

        # Search for OSC 133 sequences
        while True:
            match = OSC_133_REGEX.search(self.buffer)
            if not match:
                break

            start, end = match.span()
            pre_content = self.buffer[:start]
            tag = match.group(1)
            payload = match.group(2) or ""

            if tag == "A":
                # Prompt start
                pass

            elif tag == "C":
                # Command executed (start of output)
                # The text between prompt and C is typically the typed command
                cmd_raw = pre_content.strip()
                if cmd_raw:
                    self.current_command = strip_ansi(cmd_raw)
                self.current_output = []
                self.current_started_at = time.time()

            elif tag == "D":
                # Command finished
                exit_code = 0
                if payload:
                    try:
                        exit_code = int(payload.split(";")[0])
                    except ValueError:
                        exit_code = 0

                # Whatever pre_content was buffered belongs to current output
                if pre_content:
                    self.current_output.append(pre_content)

                cmd = self.current_command or ""
                output_str = strip_ansi("".join(self.current_output)).strip()

                if cmd or output_str:
                    block = TerminalBlock(
                        command=cmd,
                        output=output_str,
                        exit_code=exit_code,
                        started_at=self.current_started_at,
                        completed_at=time.time(),
                        raw="".join(self.current_output),
                    )
                    self.completed_blocks.append(block)
                    new_blocks.append(block)

                # Reset state
                self.current_command = None
                self.current_output = []

            # Advance buffer past marker
            self.buffer = self.buffer[end:]

        return new_blocks

    def parse_plain_stream(self, stream_text: str) -> List[TerminalBlock]:
        """Fallback parser for raw non-OSC 133 terminal captures based on standard prompts."""
        blocks: List[TerminalBlock] = []
        # Match standard bash/zsh prompt lines: user@host:...$ command
        prompt_re = re.compile(
            r"^(?:[\w\.\-]+@[\w\.\-]+:[^\n\$#%]*[\$#%]|[\w\.\-]+[\$#%])\s+(.*)$",
            re.MULTILINE,
        )

        clean = strip_ansi(stream_text)
        matches = list(prompt_re.finditer(clean))

        if not matches:
            return blocks

        for i, match in enumerate(matches):
            cmd = match.group(1).strip()
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(clean)
            output = clean[start_pos:end_pos].strip()

            blocks.append(
                TerminalBlock(
                    command=cmd,
                    output=output,
                    exit_code=0,
                    completed_at=time.time(),
                )
            )

        return blocks
