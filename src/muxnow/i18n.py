"""Internationalization (i18n) support for muxnow."""

from __future__ import annotations

from typing import Any

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "suggestion": "Suggestion",
        "why": "Why",
        "security": "Security",
        "model": "Model",
        "no_action": "(no action needed)",
        "waiting": "Waiting for terminal activity or type a question...",
        "recording": "Recording",
        "status_on": "⏺ ON",
        "status_paused": "⏸ PAUSED",
        "input_placeholder": "💬 Ask AI a question (Enter = Send, Esc = Return to shell)...",
        "btn_return": "Return to shell (Esc)",
        "btn_pause": "Pause/Resume",
        "btn_quit": "Quit",
        "fail_closed": "⚠️ Fail-Closed triggered: Unredactable secret detected. No request sent to model!",
        "secrets_redacted": "🛡️ {count} secret(s) redacted before sending",
        "confirm_exec": "⚠️ Really execute? Press ENTER to confirm or any other key to cancel.",
        "cmd_inserted": "Command '{cmd}' inserted into shell prompt.",
        "cmd_executed": "Command '{cmd}' executed.",
        "cmd_copied": "Command copied to clipboard.",
        "asking_model": "🤔 Asking {model}: '{query}'...",
        "toast_active": "muxnow: Recording ACTIVE ⏺",
        "toast_paused": "muxnow: Recording PAUSED ⏸",
        "endpoint_unreachable": "Model endpoint {url} unreachable (offline fallback).",
        "request_error": "Error in model request: {error}",
        "session_exists": "muxnow session '{session}' already exists. Connecting...",
        "session_stopping": "Stopping existing session '{session}'...",
        "session_started": "muxnow session '{session}' started. Connecting...",
        "session_stopped": "muxnow session '{session}' stopped.",
        "no_session": "No running session '{session}' found.",
        "llm_instruction": "Your explanation MUST be written in English (concise, 1-2 sentences).",
    },
    "de": {
        "suggestion": "Vorschlag",
        "why": "Warum",
        "security": "Sicherheit",
        "model": "Modell",
        "no_action": "(keine Aktion erforderlich)",
        "waiting": "Warte auf Terminal-Aktivität oder tippe eine Frage...",
        "recording": "Mitschnitt",
        "status_on": "⏺ AN",
        "status_paused": "⏸ PAUSIERT",
        "input_placeholder": "💬 Frage an KI eingeben (Enter = Senden, Esc = Zurück zur Shell)...",
        "btn_return": "Zurück zur Shell (Esc)",
        "btn_pause": "Pause/Start",
        "btn_quit": "Beenden",
        "fail_closed": "⚠️ Fail-Closed ausgelöst: Unredaktierbares Geheimnis erkannt. Kein Modell-Versand erfolgt!",
        "secrets_redacted": "🛡️ {count} Secrets vor Versand geschwärzt",
        "confirm_exec": "⚠️ Wirklich ausführen? Drücke ENTER zur Bestätigung oder eine beliebige andere Taste zum Abbrechen.",
        "cmd_inserted": "Befehl '{cmd}' in Eingabezeile eingefügt.",
        "cmd_executed": "Befehl '{cmd}' ausgeführt.",
        "cmd_copied": "Befehl in Zwischenablage kopiert.",
        "asking_model": "🤔 Frage an {model}: '{query}'...",
        "toast_active": "muxnow: Mitschnitt AKTIV ⏺",
        "toast_paused": "muxnow: Mitschnitt PAUSIERT ⏸",
        "endpoint_unreachable": "Modell-Endpunkt {url} nicht erreichbar (Offline/Rückfall).",
        "request_error": "Fehler bei Modellanfrage: {error}",
        "session_exists": "muxnow Session '{session}' existiert bereits. Verbinde...",
        "session_stopping": "Beende bestehende Session '{session}'...",
        "session_started": "muxnow Session '{session}' gestartet. Verbinde...",
        "session_stopped": "muxnow Session '{session}' beendet.",
        "no_session": "Keine laufende Session '{session}' gefunden.",
        "llm_instruction": "Deine Erklärung (explanation) MUSS auf Deutsch verfasst sein (prägnant, 1-2 Sätze).",
    },
}


def t(key: str, lang: str = "en", **kwargs: Any) -> str:
    """Translate a message key to the target language (defaults to English)."""
    lang_code = "de" if str(lang).lower().startswith("de") else "en"
    msg = MESSAGES.get(lang_code, MESSAGES["en"]).get(
        key, MESSAGES["en"].get(key, key)
    )
    if kwargs:
        try:
            return msg.format(**kwargs)
        except Exception:
            return msg
    return msg
