# GenTeks AI — Platform Documentation

**Version:** 1.0  
**Last Updated:** April 2026  
**Author:** Connor Kirkland  
**Status:** Production — Live at http://163.245.216.199:8000

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Tech Stack](#3-tech-stack)
4. [File Structure](#4-file-structure)
5. [Database Design](#5-database-design)
6. [API Reference](#6-api-reference)
7. [Platform Modes](#7-platform-modes)
8. [Real-Time Streaming](#8-real-time-streaming)
9. [Image Processing](#9-image-processing)
10. [Memory System](#10-memory-system)
11. [File Management](#11-file-management)
12. [Configuration](#12-configuration)
13. [Deployment](#13-deployment)
14. [Service Management](#14-service-management)
15. [Roadmap](#15-roadmap)
16. [Business Impact](#16-business-impact)

---

## 1. Project Overview

GenTeks AI is an internal AI platform built for GenTeks IT, a family-owned full-service Managed Service Provider based in Las Vegas, NV with operations in Denver, CO. The platform was built to replace a commercial AI subscription that was limiting the team's usage capacity at high cost.

The platform gives the GenTeks team access to an autonomous AI agent through a branded web interface. It operates in two modes — a direct Chat mode for instant answers and a Task mode that runs a full autonomous agent capable of web research, file creation, and multi-step task execution.

**Problem it solves:**
- Commercial AI platform cost ~$1,000/month with capped usage
- No customization for MSP-specific workflows
- No file generation capability
- No integration path for internal tools

**What was built:**
- Self-hosted AI platform on internal server
- Unlimited usage at API cost (~$140–550/month depending on usage)
- Custom system prompt tuned for MSP operations
- File generation for .docx, .xlsx, and .pptx
- Real-time task streaming showing agent steps as they happen
- Image analysis via Claude vision API
- Persistent memory system backed by MySQL

---

## 2. Architecture

```
Browser (dashboard.html)
        │
        ├── Chat Mode ──────────────► /api/chat ──► Claude API (direct, instant)
        │                                                    │
        │                                              Returns text response
        │
        └── Task Mode ──────────────► /api/prompt ──► OpenManus Agent
                │                                           │
                │                                    ┌──────┴──────┐
                │                                    │             │
                ▼                                WebSearch    PythonExecute
        WebSocket /ws/task/{id}                     │             │
                │                              Web Results    File Creation
                │                                    │             │
                └── Real-time step display ◄─── stream_log()
                                                     │
                                               Workspace Output Files
```

**Request flow for Task mode:**
1. Frontend generates a unique `task_id`
2. WebSocket connection opens to `/ws/task/{task_id}` before the HTTP request is sent
3. POST request sent to `/api/prompt` with the prompt and `task_id`
4. Backend creates a queue for the task ID
5. OpenManus agent runs in a thread pool executor, streaming log lines
6. Each meaningful log line is parsed and sent to the WebSocket queue
7. Frontend receives steps in real time and displays them
8. Agent completes, response is returned via HTTP
9. Frontend renders the final response with typewriter animation

---

## 3. Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| AI Backend | OpenManus | Autonomous agent framework |
| AI Model | Anthropic Claude Sonnet 4 | Language model for both modes |
| Web Framework | FastAPI | REST API and WebSocket server |
| ASGI Server | Uvicorn | Production-grade async server |
| Frontend | Vanilla HTML/CSS/JS | Single-file dashboard, no framework dependencies |
| Database | MySQL 8.0 | Persistent memory storage |
| Web Search | DuckDuckGo | Primary search engine for agent |
| File Generation | python-pptx, python-docx, openpyxl | Office document creation |
| Runtime | Python 3.12 | Application runtime |
| OS | Ubuntu 24.04 LTS | Production server OS |
| Process Manager | systemd | Service auto-start and crash recovery |

---

## 4. File Structure

```
genteks-ai/
├── README.md                          # Project overview and setup guide
├── DOCS.md                            # This file — full platform documentation
├── .gitignore                         # Excludes secrets and generated files
├── genteks-ai.service                 # systemd service definition
├── setup_server.sh                    # Automated server setup script
│
└── ManusProjects/
    ├── main.py                        # Agent entry point — called by web_api.py
    ├── requirements.txt               # Python dependencies
    │
    ├── config/
    │   ├── config.toml                # Active config (gitignored — contains secrets)
    │   └── config.example.toml       # Safe template for new deployments
    │
    ├── app/
    │   ├── agent/
    │   │   └── manus.py              # Agent definition and tool registration
    │   ├── prompt/
    │   │   └── manus.py              # GenTeks system prompt
    │   └── tool/
    │       ├── python_execute.py     # Code execution tool (60s timeout)
    │       └── web_search.py         # DuckDuckGo search tool
    │
    └── workspace/
        ├── web_api.py                 # FastAPI server — all endpoints and WebSocket
        ├── dashboard.html             # Complete web interface (single file)
        ├── memory_manager.py          # MySQL/JSON memory backend
        └── schema.sql                 # MySQL database schema
```

**Key design decision — single file dashboard:**
The entire frontend is a single `dashboard.html` file with no external dependencies beyond Google Fonts. This means zero build steps, zero npm, zero webpack. The file is served directly by FastAPI and can be edited and refreshed instantly.

---

## 5. Database Design

The database uses a relational model built on MySQL 8.0 with InnoDB storage engine. All tables use UTF-8 encoding (`utf8mb4`) to support full Unicode including emoji.

**Database name:** `genteks_ai`

### memories
The core table. Stores everything the agent learns or is told to remember across sessions.

```sql
id           VARCHAR(64)    PRIMARY KEY
content      TEXT           The memory content
agent_id     VARCHAR(128)   Which agent stored it (default: 'system')
category     VARCHAR(128)   Type of memory (default: 'general')
importance   INT            Priority score 1-10 (default: 5)
timestamp    DATETIME       When it was stored
metadata     JSON           Flexible extra data storage
```

Indexes: `agent_id`, `category`, `timestamp`, FULLTEXT on `content`

The FULLTEXT index enables fast keyword search across all memories even with thousands of entries — without it MySQL would perform a full table scan on every search.

### chat_sessions
One row per conversation. Phase 3 replacement for browser localStorage.

```sql
id           VARCHAR(64)    PRIMARY KEY
title        VARCHAR(255)   Chat title (default: 'New Chat')
created_at   DATETIME       
updated_at   DATETIME       AUTO-updates on any change
```

### chat_messages
One row per message. Linked to `chat_sessions` via foreign key.

```sql
id           BIGINT         AUTO INCREMENT PRIMARY KEY
session_id   VARCHAR(64)    Foreign key → chat_sessions.id
role         ENUM           user / assistant / error
content      TEXT           Message content
timestamp    DATETIME       
```

The `ON DELETE CASCADE` foreign key means deleting a session automatically deletes all its messages — no orphaned records.

### task_logs
One row per Task mode execution. Tracks agent performance over time.

```sql
id               VARCHAR(64)    PRIMARY KEY
prompt           TEXT           What was asked
response         TEXT           What the agent returned
status           ENUM           pending / running / complete / error
created_at       DATETIME       
completed_at     DATETIME       
duration_seconds INT            How long it took
```

### Memory Manager — Dual Backend

`memory_manager.py` detects whether MySQL is available at startup. If MySQL is reachable it uses it as the backend. If not (local development without MySQL) it falls back to a JSON file automatically. This means the codebase works identically in both environments with no code changes.

```
Startup check
    │
    ├── MySQL reachable? ──► YES ──► Use MySQL backend
    │                                     │
    │                              Create tables if not exist
    │
    └── MySQL not reachable? ──► Use JSON fallback (memory.json)
```

---

## 6. API Reference

All endpoints are served by FastAPI on port 8000.

### POST /api/chat
Direct Claude API call. No agent, no tools. Returns instantly.

**Request:**
```json
{
  "message": "string",
  "history": [{"role": "user|assistant", "content": "string"}],
  "image_base64": "string (optional)",
  "image_media_type": "string (optional)"
}
```

**Response:**
```json
{
  "success": true,
  "response": "string",
  "timestamp": "ISO datetime"
}
```

### POST /api/prompt
Full OpenManus agent execution. Supports real-time streaming via WebSocket.

**Request:**
```json
{
  "prompt": "string",
  "task_id": "string (optional — provide for WebSocket streaming)"
}
```

**Response:**
```json
{
  "success": true,
  "prompt": "string",
  "response": "string",
  "images": ["filename.png"],
  "task_id": "string",
  "timestamp": "ISO datetime"
}
```

### WebSocket /ws/task/{task_id}
Real-time task step streaming. Connect before sending the HTTP request.

**Messages received:**
```json
{"type": "step", "message": "string", "timestamp": "HH:MM:SS"}
{"type": "complete", "message": "Task complete", "timestamp": "HH:MM:SS"}
```

### GET /api/files
List all output files in the workspace.

### GET /api/files/download/{filename}
Download a specific file.

### DELETE /api/files/{filename}
Delete a specific file.

### GET /api/status
Platform health check. Returns agent and memory statistics.

### GET /api/memory/search?query={q}
Search stored memories by keyword.

### GET /api/memory/stats
Return memory statistics including total count, agents, and categories.

---

## 7. Platform Modes

### Chat Mode
- Routes to `/api/chat`
- Direct call to Claude Sonnet API
- No agent overhead — responds in 1-3 seconds
- Supports conversation history (last 10 messages)
- Supports image uploads for vision analysis
- System prompt tuned for GenTeks IT context
- Never creates files — all output appears inline in chat
- Use for: quick questions, email drafts, troubleshooting guidance, IT research

### Task Mode
- Routes to `/api/prompt`
- Runs full OpenManus autonomous agent
- Capable of web search, Python execution, and file creation
- Real-time step display via WebSocket
- Timeout warning at 2 minutes, hard timeout at 10 minutes
- Creates actual .docx, .xlsx, .pptx files in the workspace
- Use for: research reports, document generation, data analysis, complex multi-step tasks

---

## 8. Real-Time Streaming

The WebSocket streaming system was purpose-built to match the real-time step display seen in commercial AI platforms like Manus AI.

**How it works:**

```
Frontend                          Backend
   │                                 │
   │── Generate task_id ────────────►│
   │                                 │
   │── Connect WebSocket ───────────►│ (queue created for task_id)
   │◄─ Connection accepted ──────────│
   │                                 │
   │── POST /api/prompt ────────────►│ (agent starts running)
   │                                 │── Parse stdout line by line
   │◄─ step: "Searching web..." ─────│── stream_log() → queue
   │◄─ step: "Step 1 of 3" ──────────│
   │◄─ step: "Writing document..." ──│
   │◄─ complete ─────────────────────│
   │                                 │
   │◄─ HTTP response (final answer) ─│
```

The critical detail is that the WebSocket connects **before** the HTTP request is sent. This ensures no steps are missed — the queue exists before the agent starts writing to it.

**Log parsing** — the backend parses raw OpenManus stdout into meaningful user-facing messages:
- `Executing step N/N` → `⚡ Step N of N`
- `thoughts:` lines → `💭 [thought preview]`
- `Tools being prepared` → `🔧 Using tool: [name]`
- `web_search` + `Attempting` → `🔎 Searching the web...`
- `terminate` + `special tool` → `🏁 Finalizing response...`

---

## 9. Image Processing

Chat mode supports image uploads for vision analysis using Claude's native multimodal API.

**Flow:**
1. User selects an image file (max 5MB)
2. Frontend reads the file as base64 using FileReader API
3. Base64 data and media type are stored in `pendingImage`
4. On send, the image is included in the API request body
5. Backend builds a multimodal message with both image and text content blocks
6. Claude receives the image and text together and responds with analysis

**Supported formats:** PNG, JPEG, GIF, WebP

**Limitations:**
- Only available in Chat mode (not Task mode)
- Images are not stored — they are sent directly to the API and not saved to the workspace
- Max file size: 5MB

---

## 10. Memory System

The memory system provides persistent context storage across sessions. It uses a dual-backend design that automatically selects MySQL or JSON depending on environment.

**Saving a memory:**
```python
memory_manager.save_memory(
    content="Client ABC uses Datto SIRIS for backup",
    agent_id="manus",
    category="client_info",
    importance=7
)
```

**Searching memories:**
```python
results = memory_manager.search_memories("Datto backup", limit=10)
```

**Current use:** The agent automatically saves interaction summaries to memory after each task. The Memory panel in the dashboard allows manual search.

**Phase 3 expansion:** Once the chat history tables are wired up, the memory system will also store full conversation history server-side, replacing the current localStorage approach. This will enable cross-device chat history and team-shared context.

---

## 11. File Management

All files generated by Task mode are saved to the workspace directory. The platform enforces strict rules about which files are visible to users vs hidden platform internals.

**Allowed file types:** .txt, .md, .pdf, .docx, .xlsx, .pptx, .csv, .json, .py, .html, .png, .jpg, and more (50+ extensions total)

**Hidden from users:** web_api.py, dashboard.html, memory.json, config files, and all other platform internals

**File operations available:**
- Browse all output files with name, type, size, and modified date
- Download any file
- Delete individual files
- Clear all files at once

**File creation by agent:**
- `.docx` — via python-docx
- `.xlsx` — via openpyxl
- `.pptx` — via python-pptx
- `.txt`, `.md`, `.csv` — via Python file operations

---

## 12. Configuration

All configuration lives in `ManusProjects/config/config.toml`. This file is gitignored and never committed.

```toml
[llm]
model = "claude-sonnet-4-20250514"
base_url = "https://api.anthropic.com/v1"
api_key = "your-anthropic-api-key"
max_tokens = 4096
temperature = 0.0

[llm.vision]
model = "claude-sonnet-4-20250514"
base_url = "https://api.anthropic.com/v1"
api_key = "your-anthropic-api-key"
max_tokens = 4096
temperature = 0.0

[search]
engine = "duckduckgo"
fallback_engines = ["bing"]
lang = "en"
country = "us"
retry_delay = 60
max_retries = 3

[database]
host = "localhost"
port = 3306
user = "genteks"
password = "your-db-password"
database = "genteks_ai"
```

Use `config.example.toml` as a template. Never commit `config.toml`.

---

## 13. Deployment

### Prerequisites
- Ubuntu 24.04 LTS
- Python 3.12
- MySQL 8.0
- Git
- Port 8000 open in firewall

### Automated Setup
The `setup_server.sh` script handles the entire server setup automatically:

```bash
# SSH into the server
ssh root@163.245.216.199

# Upload the setup script (or clone the repo first)
git clone https://github.com/connorkirkland33/genteks-ai.git
cd genteks-ai

# Run the setup script
bash setup_server.sh
```

The script will:
1. Update system packages
2. Install Python 3.12, Git, and tools
3. Install and start MySQL 8.0
4. Create the `genteks` app user
5. Clone the repository
6. Create Python virtual environment and install dependencies
7. Create MySQL database, user, and all tables
8. Prompt you to create `config.toml`
9. Install and start the systemd service
10. Configure the firewall

**Note:** After running the setup script, install these additional missing dependencies:
```bash
/home/genteks/openmanus/.venv/bin/pip install structlog daytona-sdk==0.10.0
```

Then patch the BrowserAgent import which pulls in the Daytona sandbox (not used):
```bash
sed -i 's/from app.agent.browser import BrowserContextHelper/# from app.agent.browser import BrowserContextHelper/' /home/genteks/openmanus/ManusProjects/app/agent/manus.py
sed -i 's/    browser_context_helper: Optional\[BrowserContextHelper\] = None/    # browser_context_helper: Optional[BrowserContextHelper] = None/' /home/genteks/openmanus/ManusProjects/app/agent/manus.py
sed -i 's/        self.browser_context_helper = BrowserContextHelper(self)/        # self.browser_context_helper = BrowserContextHelper(self)/' /home/genteks/openmanus/ManusProjects/app/agent/manus.py
sed -i 's/        if self.browser_context_helper:/        if False:  # browser_context_helper disabled/' /home/genteks/openmanus/ManusProjects/app/agent/manus.py
cat > /home/genteks/openmanus/ManusProjects/app/agent/__init__.py << 'EOF'
from app.agent.base import BaseAgent
from app.agent.react import ReActAgent
from app.agent.swe import SWEAgent
from app.agent.toolcall import ToolCallAgent
from app.agent.mcp import MCPAgent
__all__ = ["BaseAgent","ReActAgent","SWEAgent","ToolCallAgent","MCPAgent"]
EOF
sudo systemctl restart genteks-ai
```

### Manual Config Step
After the script runs you must create the config file:

```bash
cp /home/genteks/openmanus/ManusProjects/config/config.example.toml \
   /home/genteks/openmanus/ManusProjects/config/config.toml

nano /home/genteks/openmanus/ManusProjects/config/config.toml
```

Fill in your Anthropic API key and MySQL password. Also add the `[database]` block:

```toml
[database]
host = "localhost"
port = 3306
user = "genteks"
password = "YOUR_DB_PASSWORD"
database = "genteks_ai"
```

### Verify Deployment
```bash
sudo systemctl status genteks-ai
curl http://localhost:8000/api/status
```

Access the platform at `http://163.245.216.199:8000`

---

## 14. Service Management

The platform runs as a systemd service called `genteks-ai`.

```bash
# Check status
sudo systemctl status genteks-ai

# Start the service
sudo systemctl start genteks-ai

# Stop the service
sudo systemctl stop genteks-ai

# Restart the service
sudo systemctl restart genteks-ai

# View live logs
sudo journalctl -u genteks-ai -f

# View last 100 log lines
sudo journalctl -u genteks-ai -n 100
```

The service is configured to:
- Start automatically on server boot
- Restart automatically if it crashes (5 second delay)
- Start only after MySQL is running (`After=mysql.service`)

### Updating the Platform
```bash
# SSH into the server
ssh root@163.245.216.199

# Pull latest changes from GitHub
cd /home/genteks/openmanus
git pull

# Restart the service to apply changes
sudo systemctl restart genteks-ai
```

---

## 15. Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Core platform, web UI, dual-mode chat, file browser, real-time streaming, MySQL memory — live at 163.245.216.199:8000 |
| Phase 2 | ⏭ Skipped | Authentication (deferred to post-deployment) |
| Phase 3 | 🔜 Next | MySQL chat history — migrate localStorage to database, cross-device persistence |
| Phase 4 | 🔜 Planned | Server hardening — HTTPS, domain name, nginx reverse proxy |
| Phase 5 | 🔜 Future | VPS worker agents — multi-agent orchestration, AutoTask integration, Datto RMM integration |

### Phase 3 Detail
Phase 3 will wire up the `chat_sessions` and `chat_messages` tables that are already in the schema. The `web_api.py` will gain new endpoints for saving and retrieving chat history, and `dashboard.html` will switch from localStorage to API calls for all chat history operations. This enables:
- Chat history shared across all team members
- History persists even if browser cache is cleared
- Admin ability to view and manage all conversations

### Phase 5 Detail
Phase 5 requires a separate VPS with worker agent instances. Each worker will be a separate OpenManus instance with dedicated tool access. The Agents panel in the dashboard (currently showing "Coming Soon") will display all active workers, their current tasks, and performance metrics. Tool integrations planned:
- AutoTask — read and update tickets automatically
- IT Glue — query and update documentation
- Datto RMM — run scripts and check device status
- Slack — send notifications and receive commands

---

## 16. Business Impact

**Problem:** Commercial AI platform with capped usage at ~$1,000/month

**Solution:** Self-hosted OpenManus + Claude Sonnet platform

**Results:**
- Replaced $1,000/month commercial subscription
- Estimated monthly cost: $140–550 depending on API usage
- Approximately 10x usage capacity compared to commercial plan
- Custom system prompt tuned specifically for MSP operations
- Full file generation capability (Word, Excel, PowerPoint)
- Real-time autonomous agent with web research capability
- Foundation for future ticket automation via AutoTask and Datto RMM integration

**Built by:** Connor Kirkland (IT Support Technician / contractor, GenTeks IT)    
**Timeline:** ~2 weeks from concept to production deployment  
**Lines of code:** ~2,500 (Python backend) + ~1,500 (JavaScript frontend)
