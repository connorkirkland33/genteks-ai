# GenTeks AI

An internal AI platform built for GenTeks, a full-service IT Managed Service Provider based in Las Vegas, NV. Built on OpenManus + Claude Sonnet, GenTeks AI replaces a commercial AI subscription (~$1,000/month) with a self-hosted autonomous agent platform delivering equivalent capability at a fraction of the cost.

---

## Overview

GenTeks AI is a production-ready internal tool that gives the GenTeks team access to an autonomous AI agent through a branded web interface. Employees can use it to automate research, generate professional documents, draft client communications, and handle business tasks — all without leaving the browser.

The platform operates in two modes:

- **Chat Mode** — Direct Claude API for instant answers, Q&A, and quick content generation. No agent overhead, responds in seconds.
- **Task Mode** — Full OpenManus autonomous agent with real-time step display. Capable of web research, file creation, and multi-step task execution.

---

## Features

- **Dual-mode AI interface** — Chat and Task modes with a single toggle, each optimized for different use cases
- **Real-time task streaming** — WebSocket-based step display shows exactly what the agent is doing as it works, similar to Manus AI's "Computer" interface
- **Persistent chat history** — All conversations saved across browser sessions via localStorage, with clickable history in the sidebar
- **File generation** — Creates real `.pptx`, `.docx`, and `.xlsx` files using python-pptx, python-docx, and openpyxl
- **File browser** — Browse, download, and delete workspace output files directly from the UI
- **Web research** — DuckDuckGo-powered search with automatic fallback engines
- **Persistent memory** — JSON-based memory system for storing and retrieving context across sessions
- **GenTeks branding** — Custom SVG logo, Zima Blue color scheme, Sora + JetBrains Mono typography

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Backend | OpenManus + Anthropic Claude Sonnet |
| Web Framework | FastAPI (Python) |
| Real-time | WebSockets |
| Frontend | Vanilla HTML/CSS/JS |
| File Generation | python-pptx, python-docx, openpyxl |
| Web Search | DuckDuckGo Search |
| Package Management | uv |
| Runtime | Python 3.12 on Windows |

---

## Architecture

```
Browser (dashboard.html)
        │
        ├── Chat Mode → /api/chat → Claude API (direct, instant)
        │
        └── Task Mode → /api/prompt + WebSocket /ws/task/{id}
                              │
                        OpenManus Agent
                              │
                    ┌─────────┼─────────┐
                    │         │         │
               WebSearch  BrowserUse  PythonExecute
                    │         │         │
                  Files    Research   Documents
                              │
                        Workspace (output files)
```

---

## Project Structure

```
OpenManus/
├── .venv/                          # Python virtual environment
├── ManusProjects/
│   ├── main.py                     # Agent entry point + CLI
│   ├── config/
│   │   └── config.toml             # API keys and search config (gitignored)
│   ├── app/
│   │   ├── agent/
│   │   │   └── manus.py            # Agent definition and tool registration
│   │   ├── prompt/
│   │   │   └── manus.py            # GenTeks system prompt
│   │   └── tool/
│   │       ├── memory.py           # Custom persistent memory tool
│   │       ├── self_improve.py     # Safe file editing tool
│   │       └── web_search.py       # Multi-engine web search
│   └── workspace/
│       ├── web_api.py              # FastAPI server + WebSocket streaming
│       ├── dashboard.html          # Full web interface
│       └── [output files]          # Generated documents and research
```

---

## Setup

### Prerequisites

- Python 3.12+
- uv package manager
- Anthropic API key

### Installation

```powershell
# Clone the repository
git clone https://github.com/YOUR_USERNAME/genteks-ai.git
cd genteks-ai

# Install uv if not already installed
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Create virtual environment and install dependencies
uv venv .venv
.venv\Scripts\Activate.ps1
cd ManusProjects
uv pip install -r requirements.txt --prerelease=allow

# Install document generation libraries
uv pip install python-pptx python-docx openpyxl anthropic
```

### Configuration

Copy the example config and add your API key:

```powershell
copy ManusProjects\config\config.example.toml ManusProjects\config\config.toml
```

Edit `config.toml`:

```toml
[llm]
model = "claude-sonnet-4-20250514"
base_url = "https://api.anthropic.com/v1"
api_key = "your-anthropic-api-key-here"
max_tokens = 4096
temperature = 0.0

[search]
engine = "duckduckgo"
fallback_engines = ["bing"]
lang = "en"
country = "us"
```

### Running

```powershell
cd ManusProjects\workspace
python web_api.py
```

Or use the included `StartWebPlatform.bat` for one-click startup.

Access the platform at `http://localhost:8000`

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Core platform, web UI, dual-mode chat, file browser |
| Phase 2 | ⏭ Skipped | Authentication (post-deployment) |
| Phase 3 | 🔜 Pending | PostgreSQL database layer |
| Phase 4 | 🔜 Pending | Dedicated server migration |
| Phase 5 | 🔜 Pending | VPS worker agents + multi-agent orchestration |

---

## Business Impact

- **Replaced** a commercial AI platform (~$1,000/month) with a self-hosted solution
- **Estimated cost** after migration: $140–550/month depending on API usage
- **10x usage capacity** compared to the commercial subscription
- Tailored specifically to MSP workflows — ticket automation, client documentation, cybersecurity research, and business task generation

---

## Company Context

[GenTeks](https://genteks.net) is a family-owned full-service IT MSP serving Las Vegas, NV and Denver, CO since 2018. Core services include managed IT, cybersecurity, backup, antivirus, VoIP, and commercial/residential IT support.

Internal tech stack: AutoTask, IT Glue, Datto RMM, BullPhish ID, RapidFire Tools, Slack.

---

## License

Private — internal use only. Not licensed for public distribution.
