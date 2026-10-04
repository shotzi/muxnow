# muxnow — AI-Sidecar für tmux 🚀

> **Intelligente Terminal-Assistenz ohne Kontrollverlust.**  
> Unten deine gewohnte Shell- oder SSH-Session, darüber ein schlankes TUI-Sidecar (Textual), das Ein- und Ausgaben mitliest, Fehler analysiert, Befehlssyntax vorschlägt und interaktive Fragen im Terminalkontext beantwortet.
>
> **Mit verlässlichem Hardware-artigen Mitschnitt-Stopp (`pipe-pane`), interaktivem Prompt und Fail-Closed Secret-Redaktion.**

---

## 🎯 Highlights

- 💬 **Interaktiver Kontext-Chat:** Stelle oben direkt Fragen in natürlicher Sprache (z. B. *„Wieviel Platz wird in Summe belegt?“* oder *„Zeig mir die 5 größten Ordner“*). `muxnow` liest den Terminal-Puffer und generiert den passenden Befehl samt Erklärung und Risikoeinstufung.
- ⚡ **Einfügen ohne Blindflug:** Mit `prefix + i` wird der vorgeschlagene Befehl direkt in deine Shell getippt — **ohne** Enter. Du behältst immer die volle Kontrolle.
- 🛑 **Echter Mitschnitt-Stopp:** Mit `prefix + p` pausierst du den Mitschnitt via `tmux pipe-pane`. Während der Pause verlässt kein einziges Byte deinen Rechner.
- 🔒 **Fail-Closed Secret Redactor:** Vor jeder Modell-Anfrage werden Passwörter, Private Keys, Bearer Tokens, JWTs und Cloud-Keys geschwärzt.
- 🌐 **Modell-Flexibilität:** Funktioniert nahtlos mit OpenAI-kompatiblen Endpunkten (z. B. DeepSeek, LiteLLM, Ollama, vLLM).
- 📜 **Audit-Trail:** Jede Aktion wird unveränderbar in einem append-only JSONL-Audit-Log protokolliert (inkl. SHA256-Hashes, Risikoklassen, Zeitstempel).

---

## ⌨️ Tastatur-Bedienung

| Taste | Aktion | Beschreibung |
|---|---|---|
| `prefix + Tab` | **Fokus wechseln** | Wechselt zwischen Eingabezeile des Assistenten und deiner Shell |
| `Esc` *(im Prompt)* | **Zurück zur Shell** | Springt aus dem Chat-Prompt sofort wieder in die Shell |
| `prefix + i` | **Vorschlag einfügen** | Schreibt den Befehl in die untere Shell — **ohne** Enter |
| `prefix + p` | **Mitschnitt Pause/Start** | Schaltet `pipe-pane` sofort an/aus (mit Live-Statusanzeige) |
| `prefix + a` | **Sidecar umschalten** | Assistenten-Pane oben temporär ein- oder ausblenden |
| `prefix + e` | **Replay exportieren** | Letzte Interaktionen als sauberes Markdown exportieren |

*(Hinweis: `prefix` ist standardmäßig `Ctrl + b`)*

---

## 🏗️ Architektur

```text
┌── tmux-Session "muxnow" ─────────────────────────────────────────────┐
│  Pane %1 (oben)   muxnow-assistant (Textual TUI)                     │
│                   Interaktiver Chat, Befehlsvorschläge, Risikostufe  │
│                   Eingabezeile mit Esc-Fokuswechsel                  │
├──────────────────────────────────────────────────────────────────────┤
│  Pane %0 (unten)  Shell / SSH ── pipe-pane ──► muxnow capture queue  │
└──────────────────────────────────────────────────────────────────────┘
         ▲                                                  │
         │ Send-Queue (Blöcke)                              │ Vorschlag
         │                                                  ▼
    muxnow-daemon  ── Block-Parser (OSC 133) ── Redactor ── LLM (DeepSeek / LiteLLM / Ollama)
                   └─ Audit-Log (JSONL)
```

---

## 🚀 Installation & Schnellstart

### 1. Installation

Mit [`uv`](https://github.com/astral-sh/uv) (empfohlen):
```bash
# Direkt als isoliertes CLI-Tool installieren
uv tool install --editable .
```

Oder klassisch via `pip`:
```bash
pip install -e .
```

### 2. Konfiguration

Erstelle die Datei `~/.config/muxnow/config.toml`:

```toml
# Beispiel: DeepSeek API direkt
model = "deepseek-flash"
base_url = "https://api.deepseek.com/v1"
api_key = "sk-..."

# Oder lokales LiteLLM / Ollama:
# model = "qwen2.5-coder:7b"
# base_url = "http://127.0.0.1:11434/v1"

# Sicherheitseinstellungen
risk_threshold = "medium"
mask_secrets = true
```

*Alternativ kann der Key auch über die Umgebungsvariable `MUXNOW_API_KEY` gesetzt werden.*

### 3. Starten

```bash
# Startet tmux mit geteiltem Fenster (Assistent oben, Shell unten):
muxnow start

# Wenn die Session bereits läuft, verbindet sich `muxnow start` automatisch.
# Beenden der Session:
muxnow stop
```

---

## 🛡️ Lizenz

MIT License – Copyright (c) 2026 Sascha Hotz. Siehe [LICENSE](LICENSE).

