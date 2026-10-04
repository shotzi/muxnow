"""LiteLLM / OpenAI compatible LLM backend client for muxnow."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

import httpx

from muxnow.config import ModelConfig
from muxnow.parser import TerminalBlock

logger = logging.getLogger("muxnow.llm")

SYSTEM_PROMPT = """You are muxnow, a precise and cautious Linux/Unix terminal copilot.
You inspect executed terminal blocks (command, output, exit code).
Your goal:
1. If the previous command failed (exit code != 0 or error in output), determine the root cause and propose the exact command to fix or troubleshoot it.
2. If the command succeeded, propose the next logical command or leave suggestion empty if no action is needed.
3. Be strictly concise. Do NOT add markdown blocks or chatter.

You MUST respond strictly with a valid JSON object with these 3 keys:
{
  "suggestion": "command string or empty string",
  "explanation": "concise explanation of why this command is needed (1-2 sentences)",
  "risk_level": "read-only" | "write" | "destructive"
}
"""


@dataclass
class LLMResponse:
    suggestion: str
    explanation: str
    risk_level: str
    is_available: bool = True
    error_message: Optional[str] = None


class LLMClient:
    """Interacts with LiteLLM Gateway or Ollama."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/chat/completions"

    async def get_suggestion(
        self,
        latest_block: TerminalBlock,
        history: Optional[List[TerminalBlock]] = None,
    ) -> LLMResponse:
        """Call LLM API with terminal context and parse structured suggestion."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Append historical blocks if provided
        if history:
            for b in history[-self.config.context_blocks :]:
                messages.append({
                    "role": "user",
                    "content": f"Command: {b.command}\nExit Code: {b.exit_code}\nOutput:\n{b.output[:500]}",
                })

        # Latest block
        messages.append({
            "role": "user",
            "content": (
                f"Latest Block:\n"
                f"Command: {latest_block.command}\n"
                f"Exit Code: {latest_block.exit_code}\n"
                f"Output:\n{latest_block.output[:2000]}"
            ),
        })

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 300,
        }

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_s) as client:
                resp = await client.post(self.endpoint, json=payload)
                resp.raise_for_status()
                data = resp.json()

            raw_reply = data["choices"][0]["message"]["content"].strip()
            return self._parse_json_reply(raw_reply)

        except httpx.ConnectError:
            msg = f"Modell-Endpunkt {self.base_url} nicht erreichbar (Offline/Rückfall)."
            logger.warning(msg)
            return LLMResponse(
                suggestion="",
                explanation=msg,
                risk_level="read-only",
                is_available=False,
                error_message=msg,
            )
        except Exception as e:
            msg = f"Fehler bei Modellanfrage: {e}"
            logger.error(msg)
            return LLMResponse(
                suggestion="",
                explanation=msg,
                risk_level="read-only",
                is_available=False,
                error_message=msg,
            )

    def _parse_json_reply(self, raw: str) -> LLMResponse:
        # Strip potential markdown fences
        clean = re.sub(r"^```(?:json)?\s*", "", raw)
        clean = re.sub(r"\s*```$", "", clean)

        try:
            obj = json.loads(clean)
            return LLMResponse(
                suggestion=str(obj.get("suggestion", "")).strip(),
                explanation=str(obj.get("explanation", "")).strip(),
                risk_level=str(obj.get("risk_level", "read-only")).lower(),
                is_available=True,
            )
        except Exception:
            return LLMResponse(
                suggestion=raw.splitlines()[0] if raw else "",
                explanation=raw,
                risk_level="read-only",
                is_available=True,
            )
