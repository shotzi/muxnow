# aimux — AI-Sidecar für tmux

> **Intelligente Terminal-Assistenz ohne Kontrollverlust.**
> Unten die gewohnte Shell/SSH-Session, darüber ein schlankes Sidecar-Fenster, das Eingaben und Ausgaben mitliest, Fehler analysiert, Befehlssyntax vorschlägt und auf Knopfdruck einfügt oder ausführt.
>
> **Mit verlässlichem Hardware-artigen Mitschnitt-Stopp (`pipe-pane`) und Fail-Closed Secret-Redaktion.**

---

## 🎯 Kernprinzipien

1. **Der Assistent ist Vorschlagender, nicht Ausführender:** Befehle werden erst nach expliziter Bestätigung ausgeführt (`prefix + I`) oder gefahrlos in die Eingabezeile eingefügt (`prefix + i`).
2. **Echter Mitschnitt-Stopp:** Ein Keybind (`prefix + A`) schaltet den Mitschnitt via `tmux pipe-pane` hardware-nah ab. Während der Pause verlässt kein einziges Byte die lokale Maschine.
3. **Fail-Closed Secret Redactor:** Vor jeder Modell-Anfrage werden Passwörter, Private Keys, Bearer Tokens, JWTs und Cloud-Keys geschwärzt. Schlägt der Redaktor fehl oder ist unsicher, wird **nichts** versendet.
4. **Local First:** Standardmäßig angebunden an das lokale LiteLLM-Gateway (`http://127.0.0.1:4000/v1`) oder Ollama.
5. **Audit-Trail:** Jede Aktion wird unveränderbar in einem append-only JSONL-Audit-Log protokolliert (inkl. SHA256-Hashes, Risikoklassen, Aktionsarten).

---

## ⌨️ Tastatur-Bedienung

| Taste | Aktion | Beschreibung |
|---|---|---|
| `prefix + a` | **Sidecar umschalten** | Assistenten-Pane ein- oder ausblenden |
| `prefix + A` | **Mitschnitt Pause/Start** | Mitschnitt (`pipe-pane`) sofort anhalten bzw. fortsetzen |
| `prefix + i` | **Vorschlag einfügen** | Schreibt den Befehl in die Shell — **ohne** Enter |
| `prefix + I` | **Vorschlag ausführen** | Ausführung nach Bestätigungsdialog (mit Risiko-Warnung) |
| `prefix + ?` | **Output erklären** | Letzten Block gezielt analysieren lassen |
| `prefix + e` | **Replay exportieren** | Mitschnitt als sauberes Markdown exportieren |

---

## 🏗️ Architektur

```
┌── tmux-Session "aimux" ──────────────────────────────────────────────┐
│  Pane 2 (oben)   aimux-assistant (Textual TUI)                       │
│                  liest Blöcke, befragt Modell, zeigt Risikostufen    │
│  Pane 1 (unten)  Shell / SSH ── pipe-pane ──► aimux capture queue     │
└──────────────────────────────────────────────────────────────────────┘
         ▲                                                  │
         │ Send-Queue (Blöcke)                              │ Vorschlag
         │                                                  ▼
    aimux-daemon  ── Block-Parser (OSC 133) ── Redactor ── LiteLLM / Ollama
                  └─ Audit-Log (JSONL)
```

---

## 🚀 Installation & Schnellstart

```bash
# Mit uv installieren
uv pip install -e .

# Session starten
aimux start

# Oder in bestehende tmux-Session einklinken
aimux attach
```

---

## 🛡️ Lizenz

MIT License – siehe [LICENSE](LICENSE).
