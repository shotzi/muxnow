"""Fail-closed secret redactor for aimux terminal capture streams."""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern, Tuple

logger = logging.getLogger("aimux.redactor")

# Pre-compiled high-confidence secret patterns
SECRET_PATTERNS: List[Tuple[str, Pattern[str]]] = [
    (
        "OPENSSH_PRIVATE_KEY",
        re.compile(
            r"-----BEGIN OPENSSH PRIVATE KEY-----[\s\S]*?-----END OPENSSH PRIVATE KEY-----",
            re.MULTILINE,
        ),
    ),
    (
        "PRIVATE_KEY",
        re.compile(
            r"-----BEGIN (?:[A-Z0-9_\-]+ )*PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9_\-]+ )*PRIVATE KEY-----",
            re.MULTILINE,
        ),
    ),
    (
        "BEARER_TOKEN",
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_\-\.\=\+]{12,}", re.IGNORECASE),
    ),
    (
        "JWT_TOKEN",
        re.compile(
            r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"
        ),
    ),
    (
        "AWS_ACCESS_KEY",
        re.compile(r"\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b"),
    ),
    (
        "GITHUB_TOKEN",
        re.compile(
            r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}\b|"
            r"\bgithub_pat_[A-Za-z0-9_]{82}\b"
        ),
    ),
    (
        "GITLAB_TOKEN",
        re.compile(r"\bglpat-[0-9a-zA-Z_\.\-]{20,}\b"),
    ),
    (
        "SLACK_TOKEN",
        re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,48}\b"),
    ),
    (
        "TELEGRAM_TOKEN",
        re.compile(r"(?:bot)?([0-9]{9,10}:[a-zA-Z0-9_-]{35})"),
    ),
    (
        "PASSWORD_ASSIGNMENT",
        re.compile(
            r"(?i)(?:password|passwd|pwd|passphrase|secret|api_key|apikey|auth_token)\s*[:=]\s*['\"]?([^\s'\"&;]+)['\"]?",
            re.IGNORECASE,
        ),
    ),
    (
        "CLI_PASSWORD_FLAG",
        re.compile(
            r"(?i)(?:-p|--password|--passwd|--token|--api-key)[=\s]+(['\"][^'\"]+['\"]|\S+)",
            re.IGNORECASE,
        ),
    ),
    (
        "CURL_USER_FLAG",
        re.compile(r"-u\s+([A-Za-z0-9_\-\.]+):([^\s@]+)"),
    ),
    (
        "BASIC_AUTH_URL",
        re.compile(r"(https?://)([A-Za-z0-9_\-\.]+):([^@\s/\[\]]+)@"),
    ),
]


def shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy for a string to identify high-entropy secrets."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    frequencies = {}
    for char in data:
        frequencies[char] = frequencies.get(char, 0) + 1
    for count in frequencies.values():
        p_x = count / length
        entropy += -p_x * math.log2(p_x)
    return entropy


@dataclass
class RedactionResult:
    text: str
    redaction_count: int
    is_safe: bool
    categories: List[str] = field(default_factory=list)
    error: Optional[str] = None


class SecretRedactor:
    """Scans and scrubs sensitive data before external or LLM processing.
    Operates on a strict fail-closed model: any unexpected error marks the
    result as unsafe, withholding text from delivery.
    """

    def __init__(
        self,
        custom_patterns: Optional[List[str]] = None,
        fail_closed: bool = True,
        entropy_threshold: float = 4.5,
    ) -> None:
        self.fail_closed = fail_closed
        self.entropy_threshold = entropy_threshold
        self.patterns = list(SECRET_PATTERNS)

        if custom_patterns:
            for idx, pat_str in enumerate(custom_patterns):
                try:
                    compiled = re.compile(pat_str)
                    self.patterns.append((f"CUSTOM_{idx}", compiled))
                except re.error as e:
                    logger.warning("Failed to compile custom pattern '%s': %s", pat_str, e)

    def redact(self, text: str) -> RedactionResult:
        """Apply all redactions with fail-closed guarantee."""
        if not text:
            return RedactionResult(text="", redaction_count=0, is_safe=True)

        try:
            current_text = text
            total_redactions = 0
            categories_seen: List[str] = []

            # 1. Apply configured regex patterns
            for name, pattern in self.patterns:
                if name == "PASSWORD_ASSIGNMENT":
                    # Keep variable name, redact value
                    def _replace_assignment(m: re.Match[str]) -> str:
                        nonlocal total_redactions
                        total_redactions += 1
                        matched_str = m.group(0)
                        val = m.group(1)
                        return matched_str.replace(val, f"[REDACTED:{name}]")

                    new_text, count = pattern.subn(_replace_assignment, current_text)
                    if count > 0:
                        categories_seen.append(name)
                        current_text = new_text

                elif name == "CLI_PASSWORD_FLAG":
                    def _replace_cli_flag(m: re.Match[str]) -> str:
                        nonlocal total_redactions
                        total_redactions += 1
                        val = m.group(1)
                        return m.group(0).replace(val, f"[REDACTED:{name}]")

                    new_text, count = pattern.subn(_replace_cli_flag, current_text)
                    if count > 0:
                        categories_seen.append(name)
                        current_text = new_text

                elif name == "CURL_USER_FLAG":
                    def _replace_curl_user(m: re.Match[str]) -> str:
                        nonlocal total_redactions
                        total_redactions += 1
                        user = m.group(1)
                        return f"-u {user}:[REDACTED:PASSWORD]"

                    new_text, count = pattern.subn(_replace_curl_user, current_text)
                    if count > 0:
                        categories_seen.append(name)
                        current_text = new_text

                elif name == "TELEGRAM_TOKEN":
                    def _replace_telegram(m: re.Match[str]) -> str:
                        nonlocal total_redactions
                        total_redactions += 1
                        tok = m.group(1)
                        return m.group(0).replace(tok, "[REDACTED:TELEGRAM_TOKEN]")

                    new_text, count = pattern.subn(_replace_telegram, current_text)
                    if count > 0:
                        categories_seen.append(name)
                        current_text = new_text

                elif name == "BASIC_AUTH_URL":
                    def _replace_url_auth(m: re.Match[str]) -> str:
                        nonlocal total_redactions
                        total_redactions += 1
                        scheme = m.group(1)
                        user = m.group(2)
                        return f"{scheme}{user}:[REDACTED:PASSWORD]@"

                    new_text, count = pattern.subn(_replace_url_auth, current_text)
                    if count > 0:
                        categories_seen.append(name)
                        current_text = new_text

                else:
                    new_text, count = pattern.subn(f"[REDACTED:{name}]", current_text)
                    if count > 0:
                        total_redactions += count
                        categories_seen.append(name)
                        current_text = new_text

            # 2. Entropy check for standalone candidate tokens (len >= 32)
            words = current_text.split()
            for word in words:
                clean_word = word.strip("=,\"';()[]{}")
                if len(clean_word) >= 32 and not clean_word.startswith("[REDACTED"):
                    # Check if token is alphanumeric/base64-ish
                    if re.match(r"^[A-Za-z0-9+/=_-]{32,}$", clean_word):
                        if shannon_entropy(clean_word) >= self.entropy_threshold:
                            current_text = current_text.replace(
                                clean_word, "[REDACTED:HIGH_ENTROPY_SECRET]"
                            )
                            total_redactions += 1
                            if "HIGH_ENTROPY_SECRET" not in categories_seen:
                                categories_seen.append("HIGH_ENTROPY_SECRET")

            # 3. Post-verification: ensure private key headers did not survive
            if "PRIVATE KEY" in current_text and "-----BEGIN" in current_text:
                if self.fail_closed:
                    return RedactionResult(
                        text="",
                        redaction_count=total_redactions,
                        is_safe=False,
                        categories=categories_seen,
                        error="Fail-closed trip: Unredacted private key marker detected after scrubbing.",
                    )

            return RedactionResult(
                text=current_text,
                redaction_count=total_redactions,
                is_safe=True,
                categories=categories_seen,
            )

        except Exception as e:
            logger.error("Redactor encounter error: %s", e)
            if self.fail_closed:
                return RedactionResult(
                    text="",
                    redaction_count=0,
                    is_safe=False,
                    error=f"Fail-closed: Redaction exception occurred ({e})",
                )
            raise
