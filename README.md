# muxnow — AI Sidecar for tmux 🚀

> **Intelligent terminal assistance without losing control.**  
> Keep your familiar shell or SSH session at the bottom, while a lightweight TUI sidecar (built with Textual) runs at the top—reading command input/output, diagnosing errors, suggesting precise commands, and answering interactive queries with full terminal context.
>
> **Featuring hardware-level capture pause (`pipe-pane`), interactive chat prompt, and fail-closed secret redaction.**

---

## 🎯 Highlights

- 💬 **Interactive Context-Aware Chat:** Ask questions directly in natural language (e.g., *"How much total disk space is used?"* or *"Show me the 5 largest directories"*). `muxnow` inspects the active terminal buffer and produces the exact shell command with an explanation and risk assessment.
- ⚡ **No Blind Execution:** Press `prefix + i` to insert the suggested command straight into your active shell prompt — **without** executing it. You review, edit if desired, and press Enter yourself.
- 🛑 **True Capture Pause:** Press `prefix + p` to instantly toggle capture via `tmux pipe-pane`. When paused, not a single byte leaves your local machine.
- 🔒 **Fail-Closed Secret Redactor:** Automatically strips passwords, private keys, bearer tokens, JWTs, cloud credentials, and high-entropy secrets before sending data to any model.
- 🌐 **Model Flexibility:** Seamlessly works with any OpenAI-compatible API endpoint (e.g. DeepSeek, LiteLLM, Ollama, vLLM, LocalAI).
- 📜 **Immutable Audit Trail:** Logs every prompt, suggestion, hash, and risk level into an append-only JSONL audit file.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action | Description |
|---|---|---|
| `prefix + Tab` | **Toggle Focus** | Switches focus between the sidecar prompt and your shell |
| `Esc` *(in prompt)* | **Back to Shell** | Immediately exits the chat prompt and focuses the shell below |
| `prefix + i` | **Insert Suggestion** | Types the proposed command into the active shell without executing |
| `prefix + p` | **Pause / Resume Capture** | Toggles `pipe-pane` capture with instant visual on-screen feedback |
| `prefix + a` | **Toggle Sidecar** | Temporarily collapses or expands the top assistant pane |
| `prefix + e` | **Export Replay** | Exports recent terminal interactions to clean Markdown |

*(Note: `prefix` is `Ctrl + b` by default in tmux)*

---

## 🏗️ Architecture

```text
┌── tmux session "muxnow" ─────────────────────────────────────────────┐
│  Pane %1 (top)     muxnow-assistant (Textual TUI)                    │
│                    Interactive chat, command suggestions, risk badge │
│                    Prompt input with Esc quick-return                │
├──────────────────────────────────────────────────────────────────────┤
│  Pane %0 (bottom)  Shell / SSH ── pipe-pane ──► muxnow capture queue  │
└──────────────────────────────────────────────────────────────────────┘
         ▲                                                  │
         │ Block feed (commands & outputs)                  │ Suggestion
         │                                                  ▼
    muxnow-daemon  ── Block Parser (OSC 133) ── Redactor ── LLM (DeepSeek / LiteLLM / Ollama)
                   └─ Audit Log (JSONL)
```

---

## 🚀 Installation & Quickstart

### 1. Prerequisites
- Python 3.11+
- [tmux](https://github.com/tmux/tmux) 3.2+
- Recommended: [`uv`](https://github.com/astral-sh/uv)

### 2. Installation

Using [`uv`](https://github.com/astral-sh/uv) (recommended):
```bash
# Clone the repository
git clone https://github.com/shotzi/muxnow.git
cd muxnow

# Install as a global, isolated tool
uv tool install --editable .
```

Or via standard `pip`:
```bash
git clone https://github.com/shotzi/muxnow.git
cd muxnow
pip install -e .
```

### 3. Configuration

Create your configuration file at `~/.config/muxnow/config.toml`:

```toml
# Example: Direct DeepSeek API
model = "deepseek-flash"
base_url = "https://api.deepseek.com/v1"
api_key = "sk-..."

# Example: Local Ollama / LiteLLM
# model = "qwen2.5-coder:7b"
# base_url = "http://127.0.0.1:11434/v1"

# Safety settings
risk_threshold = "medium"
mask_secrets = true
```

*Tip: You can also provide your API key via the `MUXNOW_API_KEY` environment variable.*

### 4. Running muxnow

```bash
# Launch tmux with the split window (assistant on top, shell below):
muxnow start

# If the session is already active, muxnow start re-attaches automatically.
# To shut down the session:
muxnow stop
```

---

## 🛡️ License

MIT License – Copyright (c) 2026 Sascha Hotz. See [LICENSE](LICENSE) for details.


