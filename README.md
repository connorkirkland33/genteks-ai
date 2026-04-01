# GenTeks AI Platform

An internal AI platform built for GenTeks IT — a family-owned Managed Service Provider based in Las Vegas, NV with operations in Denver, CO. Built to replace a commercial AI subscription with a self-hosted solution delivering approximately 10x usage capacity at a fraction of the cost.

**Live Platform:** http://163.245.216.199:8000

---

## Overview

GenTeks AI combines the OpenManus autonomous agent framework with Anthropic's Claude Sonnet model, served through a custom-built FastAPI web interface. The platform operates in two modes:

- **Chat Mode** — Direct Claude API calls for instant answers, email drafts, IT research, and client communications
- **Task Mode** — Full autonomous agent capable of web search, file creation, and multi-step task execution with real-time step display

---

## Features

- Dual-mode chat system (Chat and Task)
- Real-time WebSocket streaming of agent steps
- Image upload and vision analysis via Claude API
- File generation — .docx, .xlsx, .pptx, .txt, .md, .csv
- File browser with download and delete
- Persistent memory system backed by MySQL 8.0
- Chat history stored in browser localStorage
- Responsive web interface — works on desktop and mobile
- systemd service with auto-start and crash recovery

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Backend | OpenManus |
| AI Model | Claude Sonnet 4 (Anthropic) |
| Web Framework | FastAPI |
| ASGI Server | Uvicorn |
| Frontend | Vanilla HTML/CSS/JS (single file) |
| Database | MySQL 8.0 |
| Web Search | DuckDuckGo |
| File Generation | python-pptx, python-docx, openpyxl |
| Runtime | Python 3.12 |
| OS | Ubuntu 24.04 LTS |
| Process Manager | systemd |

---

## Server Details

| Item | Value |
|------|-------|
| Server IP | 163.245.216.199 |
| Port | 8000 |
| OS | Ubuntu 24.04 LTS |
| App User | genteks |
| App Directory | /home/genteks/openmanus/ |
| Database | genteks_ai (MySQL 8.0) |
| Service | genteks-ai.service |

---

## Accessing the Platform

Open a browser and navigate to:

```
http://163.245.216.199:8000
```

No login required. The platform is accessible from any device on the network.

---

## File Structure

```
genteks-ai/
├── README.md
├── DOCS.md                            # Full platform documentation
├── .gitignore
├── genteks-ai.service                 # systemd service definition
├── setup_server.sh                    # Automated server setup script
│
└── ManusProjects/
    ├── main.py                        # Agent entry point
    ├── requirements.txt               # Python dependencies
    ├── config/
    │   ├── config.toml                # Active config (gitignored)
    │   └── config.example.toml       # Safe template
    ├── app/
    │   ├── agent/                     # Agent definitions
    │   ├── prompt/                    # System prompts
    │   └── tool/                      # Agent tools
    └── workspace/
        ├── web_api.py                 # FastAPI server
        ├── dashboard.html             # Web interface
        ├── memory_manager.py          # MySQL/JSON memory backend
        ├── agent_system.py            # Agent management
        └── schema.sql                 # MySQL schema
```

---

## Service Management

```bash
# Check status
sudo systemctl status genteks-ai

# Restart the service
sudo systemctl restart genteks-ai

# Stop the service
sudo systemctl stop genteks-ai

# View live logs
sudo journalctl -u genteks-ai -f

# View last 50 log lines
sudo journalctl -u genteks-ai -n 50 --no-pager
```

---

## Updating the Platform

```bash
# SSH into the server
ssh root@163.245.216.199

# Pull latest changes from GitHub
cd /home/genteks/openmanus
git pull

# Restart the service
sudo systemctl restart genteks-ai
```

---

## Configuration

The active config lives at:
```
/home/genteks/openmanus/ManusProjects/config/config.toml
```

This file is gitignored and never committed. It contains the Anthropic API key and MySQL credentials. Use `config.example.toml` as a template if you need to recreate it.

To update the API key:
```bash
nano /home/genteks/openmanus/ManusProjects/config/config.toml
# Update api_key under [llm] and [llm.vision]
sudo systemctl restart genteks-ai
```

---

## Database

```bash
# Connect to MySQL
mysql -u genteks -p genteks_ai

# View memory entries
SELECT id, content, category, timestamp FROM memories ORDER BY timestamp DESC LIMIT 10;

# View database tables
SHOW TABLES;
```

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Core platform, web UI, dual-mode chat, file browser, real-time streaming, MySQL memory |
| Phase 2 | ⏭ Skipped | Authentication |
| Phase 3 | ✅ Complete | MySQL database deployed — memories active, chat tables ready |
| Phase 4 | 🔜 Next | Wire MySQL chat history — migrate localStorage to database |
| Phase 5 | 🔜 Planned | HTTPS, nginx reverse proxy, domain name |
| Phase 6 | 🔜 Future | VPS worker agents, AutoTask integration, Datto RMM integration |

---

## Business Impact

- Replaced ~$1,000/month commercial AI subscription
- Estimated monthly cost: $140–550 depending on API usage
- Approximately 10x usage capacity vs commercial plan
- Custom system prompt tuned for MSP operations
- Full file generation capability
- Foundation for future automation via AutoTask and Datto RMM

---

## Built By

Connor Kirkland — IT Support Technician / Contractor, GenTeks IT
GitHub: [github.com/connorkirkland33/genteks-ai](https://github.com/connorkirkland33/genteks-ai)
