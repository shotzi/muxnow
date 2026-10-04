"""Tests for append-only audit logger."""

import json
from aimux.audit import AuditLogger


def test_audit_logging(tmp_path):
    log_file = tmp_path / "audit.jsonl"
    logger = AuditLogger(log_file)

    rec = logger.log(
        action="inserted",
        risk_level="read-only",
        raw_block_content="secret_text_to_be_hashed_never_stored_in_plaintext",
        command_suggested="systemctl status nginx",
        pane_id="%1",
    )

    assert log_file.exists()
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["action"] == "inserted"
    assert data["risk_level"] == "read-only"
    assert data["command_suggested"] == "systemctl status nginx"
    # Content must be hashed, never plaintext!
    assert "secret_text_to_be_hashed" not in lines[0]
    assert data["block_hash"] == rec.block_hash
