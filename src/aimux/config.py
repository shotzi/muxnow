"""Configuration handling for aimux."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "aimux" / "config.toml"


@dataclass
class ModelConfig:
    base_url: str = "http://127.0.0.1:4000/v1"
    model: str = "local-default"
    timeout_s: float = 60.0
    context_blocks: int = 5


@dataclass
class CaptureConfig:
    redact_patterns: List[str] = field(
        default_factory=lambda: [
            r"(?i)password\s*[:=]\s*['\"]?[^\s'\"]+",
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
            r"(?i)bearer\s+[A-Za-z0-9_\-\.]+",
            r"AKIA[0-9A-Z]{16}",
            r"ghp_[0-9a-zA-Z]{36}",
            r"glpat-[0-9a-zA-Z_\.\-]{20,}",
            r"ey[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]+",
        ]
    )
    skip_prompt_lines: bool = True
    fail_closed: bool = True


@dataclass
class GuardConfig:
    deny_patterns: List[str] = field(
        default_factory=lambda: [
            r"(?i)\brm\s+-rf\s+/\b",
            r"\bmkfs\b",
            r"\bdd\s+if=",
            r"iptables\s+-F",
            r">\s*/dev/sd",
            r"(?i)\b(shutdown|reboot|poweroff|init\s+0)\b",
        ]
    )
    require_confirm: List[str] = field(
        default_factory=lambda: ["destructive", "write"]
    )


@dataclass
class AuditConfig:
    path: str = "~/.local/state/aimux/audit.jsonl"

    @property
    def resolved_path(self) -> Path:
        return Path(os.path.expanduser(self.path))


@dataclass
class AimuxConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    guard: GuardConfig = field(default_factory=GuardConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)

    @classmethod
    def load(cls, path: Path | str | None = None) -> AimuxConfig:
        config_file = Path(path) if path else DEFAULT_CONFIG_PATH
        if not config_file.exists():
            return cls()

        try:
            with open(config_file, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            # Fall back to defaults on parsing error
            return cls()

        m_data = data.get("model", {})
        c_data = data.get("capture", {})
        g_data = data.get("guard", {})
        a_data = data.get("audit", {})

        return cls(
            model=ModelConfig(
                base_url=m_data.get("base_url", "http://127.0.0.1:4000/v1"),
                model=m_data.get("model", "local-default"),
                timeout_s=float(m_data.get("timeout_s", 60.0)),
                context_blocks=int(m_data.get("context_blocks", 5)),
            ),
            capture=CaptureConfig(
                redact_patterns=c_data.get("redact_patterns", CaptureConfig().redact_patterns),
                skip_prompt_lines=c_data.get("skip_prompt_lines", True),
                fail_closed=c_data.get("fail_closed", True),
            ),
            guard=GuardConfig(
                deny_patterns=g_data.get("deny_patterns", GuardConfig().deny_patterns),
                require_confirm=g_data.get("require_confirm", ["destructive", "write"]),
            ),
            audit=AuditConfig(
                path=a_data.get("path", "~/.local/state/aimux/audit.jsonl")
            ),
        )
