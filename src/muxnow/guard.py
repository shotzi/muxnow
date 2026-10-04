"""Risk classification and command execution guard for muxnow."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

DESTRUCTIVE_PATTERNS = [
    (r"(?i)\brm\s+-[rRfF]+\s+(?:/|\*|\~|\$HOME)", "Recursive root or wildcard deletion"),
    (r"(?i)\brm\s+-[rRfF]+\b", "Recursive file deletion"),
    (r"(?i)\bmkfs(?:\.\w+)?\b", "Filesystem creation / disk format"),
    (r"(?i)\bdd\s+(?:if|of)=", "Direct low-level disk block write"),
    (r"(?i)\biptables\s+-(?:F|X)\b", "Firewall flush / rule deletion"),
    (r">\s*/dev/(?:sd[a-z]|nvme[0-9]|hd[a-z]|vd[a-z])", "Direct raw device overwrite"),
    (r"(?i)\b(?:shutdown|reboot|poweroff|init\s+0)\b", "System shutdown/reboot"),
    (r"(?i)\bDROP\s+(?:DATABASE|SCHEMA|TABLE)\b", "Database destruction"),
    (r"(?i)\bTRUNCATE\s+TABLE\b", "Database table truncation"),
    (r"(?i):(){ :\|:& };:", "Fork bomb attempt"),
]

READ_ONLY_PREFIXES = [
    "ls", "cat", "less", "more", "head", "tail", "grep", "rg", "find",
    "status", "echo", "pwd", "which", "whereis", "whoami", "id", "uname",
    "uptime", "top", "htop", "free", "df", "du", "ps", "netstat", "ss",
    "ip addr", "ip route", "ifconfig", "ping", "traceroute", "curl -I",
    "git status", "git log", "git diff", "git show", "git branch",
    "systemctl status", "systemctl is-active", "journalctl",
    "docker ps", "docker images", "docker logs",
]


@dataclass
class RiskAssessment:
    level: str  # "read-only", "write", "destructive"
    reason: str
    is_denied: bool = False
    requires_double_confirm: bool = False


class CommandGuard:
    """Evaluates risk and enforces safe execution gates."""

    def __init__(self, deny_patterns: Optional[List[str]] = None) -> None:
        self.deny_patterns = [re.compile(p) for p in (deny_patterns or [])]
        self.destructive_rules = [(re.compile(p), msg) for p, msg in DESTRUCTIVE_PATTERNS]

    def assess(self, command: str) -> RiskAssessment:
        clean_cmd = command.strip()
        if not clean_cmd:
            return RiskAssessment(level="read-only", reason="Empty command")

        # 1. Deny patterns
        for pat in self.deny_patterns:
            if pat.search(clean_cmd):
                return RiskAssessment(
                    level="destructive",
                    reason="Command matches security deny-pattern rule",
                    is_denied=True,
                    requires_double_confirm=True,
                )

        # 2. Destructive patterns
        for pat, reason in self.destructive_rules:
            if pat.search(clean_cmd):
                return RiskAssessment(
                    level="destructive",
                    reason=reason,
                    is_denied=False,
                    requires_double_confirm=True,
                )

        # 3. Read-only checks
        for prefix in READ_ONLY_PREFIXES:
            if clean_cmd.startswith(prefix):
                # Ensure it's not piped into destructive commands or file redirects
                if not re.search(r"[>|]", clean_cmd):
                    return RiskAssessment(
                        level="read-only",
                        reason=f"Standard inspection command ({prefix})",
                    )

        # 4. Default fallback: write
        return RiskAssessment(
            level="write",
            reason="Standard state-modifying shell command",
            requires_double_confirm=False,
        )
