"""Configuration handling for muxnow."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "muxnow" / "config.toml"


@dataclass
class ModelConfig:
    base_url: str = "http://127.0.0.1:4000/v1"
    model: str = "deepseek-flash"
    api_key: Optional[str] = None
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
    path: str = "~/.local/state/muxnow/audit.jsonl"

    @property
    def resolved_path(self) -> Path:
        return Path(os.path.expanduser(self.path))


@dataclass
class MuxnowConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    guard: GuardConfig = field(default_factory=GuardConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    language: str = "en"

    @classmethod
    def load(cls, path: Path | str | None = None) -> MuxnowConfig:
        config_file = Path(path) if path else DEFAULT_CONFIG_PATH
        data: Dict[str, Any] = {}
        if config_file.exists():
            try:
                with open(config_file, "rb") as f:
                    data = tomllib.load(f)
            except Exception:
                data = {}

        m_data = data.get("model", {})
        if not isinstance(m_data, dict):
            # If specified as flat string (e.g. model = "deepseek-flash")
            m_data = {"model": m_data}

        c_data = data.get("capture", {})
        if not isinstance(c_data, dict):
            c_data = {}

        g_data = data.get("guard", {})
        if not isinstance(g_data, dict):
            g_data = {}

        a_data = data.get("audit", {})
        if not isinstance(a_data, dict):
            a_data = {}

        api_key = (
            m_data.get("api_key")
            or data.get("api_key")
            or m_data.get("token")
            or data.get("token")
            or os.environ.get("MUXNOW_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )

        base_url = (
            m_data.get("base_url")
            or data.get("base_url")
            or "http://127.0.0.1:4000/v1"
        )

        model_name = (
            m_data.get("model")
            or data.get("model")
            or "deepseek-flash"
        )

        lang = (
            data.get("language")
            or data.get("lang")
            or data.get("ui", {}).get("language")
            or os.environ.get("MUXNOW_LANG")
            or "en"
        ).strip().lower()
        if lang not in ("en", "de"):
            lang = "en"

        return cls(
            model=ModelConfig(
                base_url=base_url,
                model=model_name,
                api_key=api_key,
                timeout_s=float(m_data.get("timeout_s", data.get("timeout_s", 60.0))),
                context_blocks=int(m_data.get("context_blocks", data.get("context_blocks", 5))),
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
                path=a_data.get("path", data.get("audit_path", "~/.local/state/muxnow/audit.jsonl"))
            ),
            language=lang,
        )


# Backward-compatibility alias
AimuxConfig = MuxnowConfig
