"""Append-only JSONL audit logger for muxnow actions."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("muxnow.audit")


@dataclass
class AuditRecord:
    timestamp: str
    action: str  # "inserted", "executed", "discarded", "explained", "paused", "resumed"
    block_hash: str
    risk_level: str  # "read-only", "write", "destructive"
    command_suggested: Optional[str] = None
    redaction_count: int = 0
    categories: Optional[List[str]] = None
    pane_id: Optional[str] = None
    session_name: Optional[str] = None
    notes: Optional[str] = None


class AuditLogger:
    """Manages append-only JSONL audit trails with hashed contents for confidentiality."""

    def __init__(self, log_path: Path | str) -> None:
        self.log_path = Path(os.path.expanduser(str(log_path)))
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def hash_payload(data: str) -> str:
        """Create SHA-256 fingerprint of input block so audit never leaks secret values."""
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def log(
        self,
        action: str,
        risk_level: str = "read-only",
        raw_block_content: str = "",
        command_suggested: Optional[str] = None,
        redaction_count: int = 0,
        categories: Optional[List[str]] = None,
        pane_id: Optional[str] = None,
        session_name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> AuditRecord:
        """Append an audit record to the persistent JSONL file."""
        now_iso = datetime.now(timezone.utc).isoformat()
        block_hash = self.hash_payload(raw_block_content) if raw_block_content else "none"

        record = AuditRecord(
            timestamp=now_iso,
            action=action,
            block_hash=block_hash,
            risk_level=risk_level,
            command_suggested=command_suggested,
            redaction_count=redaction_count,
            categories=categories or [],
            pane_id=pane_id,
            session_name=session_name,
            notes=notes,
        )

        try:
            line = json.dumps(asdict(record)) + "\n"
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            logger.error("Failed to write to audit log (%s): %s", self.log_path, e)

        return record
