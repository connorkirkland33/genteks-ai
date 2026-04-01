"""
Web API for GenTeks AI Platform
FastAPI backend providing REST endpoints for agent management and web interface
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import json
import uvicorn
from datetime import datetime
import os
import asyncio
import sys
import subprocess
import anthropic
from concurrent.futures import ThreadPoolExecutor

# Import our agent system and memory manager
from agent_system import agent_manager, initialize_default_agents
from memory_manager import memory_manager


# =========================
# REQUEST MODELS
# =========================

class TaskRequest(BaseModel):
    agent_id: str
    task_description: str
    priority: Optional[int] = 5


class AgentCreateRequest(BaseModel):
    agent_type: str
    name: str
    capabilities: Optional[List[str]] = None
    tools: Optional[List[str]] = None


class MessageRequest(BaseModel):
    sender_id: str
    message: str
    target_id: Optional[str] = None


class MemorySearchRequest(BaseModel):
    query: str
    agent_id: Optional[str] = None
    category: Optional[str] = None
    limit: Optional[int] = 10


class PromptRequest(BaseModel):
    prompt: str
    task_id: Optional[str] = None


# =========================
# APP INIT
# =========================

app = FastAPI(
    title="GenTeks AI Platform API",
    description="GenTeks AI Multi-Agent Platform with Persistent Memory",
    version="1.0.0"
)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_PATH = os.path.join(BASE_DIR, "dashboard.html")
OPENMANUS_DIR = os.path.dirname(BASE_DIR)
MAIN_PY = os.path.join(OPENMANUS_DIR, "main.py")
WORKSPACE_DIR = BASE_DIR
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Create static dir if it doesn't exist
os.makedirs(STATIC_DIR, exist_ok=True)

# Copy logo to static dir if it exists in workspace
logo_src = os.path.join(BASE_DIR, "logo.png")
logo_dst = os.path.join(STATIC_DIR, "logo.png")
if os.path.exists(logo_src) and not os.path.exists(logo_dst):
    import shutil
    shutil.copy2(logo_src, logo_dst)

# venv Python path
VENV_PYTHON = os.path.join(
    os.path.dirname(OPENMANUS_DIR),
    ".venv", "Scripts", "python.exe"
)

# Platform internal files - never shown to users
HIDDEN_FILES = {
    "memory.json", "memory_backup.json", "last_response.json",
    "web_api.py", "web_api.py.backup", "platform_config.json",
    "dashboard.html", "start_platform.bat", "fix_pptx.bat",
    "requirements.txt", "install_dependencies.py", "logo.png",
    "agent_system.py", "memory_manager.py", "openmanus_integration.py",
    "platform_launcher.py", "base_agent.py", "config_manager.py",
    "progress_tracker.py", "ai_testing_framework.py", "backup_system.py",
    "fix_pptx.py", "test_platform.py", "test_memory_improvements.py",
    "PLATFORM_STATUS_REPORT.md", "DEPLOYMENT_GUIDE.md",
    "PROJECT_DOCUMENTATION.md", "README.md", "project_goals.md",
    "Executive_Summary.md", "Implementation_Status_Report.md",
    "AI_Improvement_Assessment.md", "AI_Improvement_Log.txt",
    "AI_Self_Improvement_Access_Instructions.txt",
    "System_Access_Instructions.txt",
    "OpenManus_Analysis_and_Improvements.txt",
    "example.txt",
}

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".rtf", ".pdf", ".docx", ".doc", ".odt", ".epub",
    ".xlsx", ".xls", ".csv", ".tsv",
    ".pptx", ".ppt",
    ".py", ".js", ".ts", ".html", ".css", ".json", ".xml",
    ".yaml", ".yml", ".sql", ".sh", ".bat",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff",
    ".mp3", ".wav", ".m4a", ".ogg",
    ".mp4", ".mov", ".avi", ".mkv",
    ".zip", ".tar", ".gz",
    ".msg", ".eml", ".log",
}


# =========================
# WEBSOCKET TASK STREAMING
# =========================

import queue
import threading

# Active WebSocket connections mapped by task_id
active_connections: Dict[str, WebSocket] = {}
# Log queues mapped by task_id
log_queues: Dict[str, queue.Queue] = {}

@app.websocket("/ws/task/{task_id}")
async def task_websocket(websocket: WebSocket, task_id: str):
    await websocket.accept()
    active_connections[task_id] = websocket
    log_queues[task_id] = queue.Queue()
    try:
        while True:
            await asyncio.sleep(0.1)
            q = log_queues.get(task_id)
            if q:
                while not q.empty():
                    msg = q.get_nowait()
                    await websocket.send_text(json.dumps(msg))
                    if msg.get("type") == "complete":
                        return
    except WebSocketDisconnect:
        pass
    finally:
        active_connections.pop(task_id, None)
        log_queues.pop(task_id, None)

def stream_log(task_id: str, message: str, msg_type: str = "step"):
    """Send a log message to the WebSocket queue for a task."""
    q = log_queues.get(task_id)
    if q:
        q.put({"type": msg_type, "message": message, "timestamp": datetime.now().strftime("%H:%M:%S")})


# =========================
# STATIC FILES
# =========================

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# =========================
# STARTUP
# =========================

@app.on_event("startup")
async def startup_event():
    default_agents = initialize_default_agents()
    memory_manager.save_memory(
        content=f"Platform started with default agents: {default_agents}",
        agent_id="system",
        category="system_events",
        importance=9
    )
    print(f"GenTeks AI Platform started with agents: {default_agents}")


# =========================
# ROOT
# =========================

@app.get("/", response_class=HTMLResponse)
async def root():
    if os.path.exists(DASHBOARD_PATH):
        return FileResponse(DASHBOARD_PATH)
    return HTMLResponse("<h1>dashboard.html not found</h1>")


# =========================
# OPENMANUS PROMPT ENDPOINT
# =========================

@app.post("/api/prompt")
async def run_prompt(request: PromptRequest):
    """Send a prompt directly to OpenManus and return the response"""

    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    python_exe = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable

    import uuid
    task_id = request.task_id if request.task_id else str(uuid.uuid4())
    # Pre-create the queue so WebSocket can connect before task starts
    if task_id not in log_queues:
        log_queues[task_id] = queue.Queue()

    def run_openmanus():
        process = subprocess.Popen(
            [python_exe, MAIN_PY, "--prompt", request.prompt],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=OPENMANUS_DIR,
            bufsize=1
        )
        all_output = []
        for line in process.stdout:
            line = line.rstrip()
            if not line:
                continue
            all_output.append(line)
            # Parse log lines into meaningful steps
            step_msg = None
            if "Executing step" in line:
                import re
                m = re.search(r'Executing step (\d+)/(\d+)', line)
                if m:
                    step_msg = f"⚡ Step {m.group(1)} of {m.group(2)}"
            elif "thoughts:" in line.lower() and "✨" in line:
                thought = line.split("thoughts:")[-1].strip()
                if thought:
                    step_msg = f"💭 {thought[:120]}"
            elif "Tools being prepared" in line:
                tools = line.split(":")[-1].strip()
                step_msg = f"🔧 Using tool: {tools}"
            elif "web_search" in line.lower() and "Attempting" in line:
                step_msg = f"🔎 Searching the web..."
            elif "Browser action" in line and "failed" in line.lower():
                step_msg = f"⚠️ Retrying with different source..."
            elif "completed its mission" in line:
                tool = line.split("'")[1] if "'" in line else "tool"
                step_msg = f"✅ {tool} completed"
            elif "terminate" in line.lower() and "special tool" in line.lower():
                step_msg = f"🏁 Finalizing response..."

            if step_msg:
                stream_log(task_id, step_msg)

        process.wait()
        return "\n".join(all_output), ""

    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            stdout, errors = await loop.run_in_executor(pool, run_openmanus)

        # Read response from temp file written by main.py
        response_file = os.path.join(OPENMANUS_DIR, "workspace", "last_response.json")
        clean_output = ""

        try:
            if os.path.exists(response_file):
                with open(response_file, "r") as f:
                    data = json.load(f)
                    clean_output = data.get("answer", "")
                os.remove(response_file)
        except Exception:
            pass

        # Fall back to filtering noisy lines if file read failed
        if not clean_output:
            skip_prefixes = [
                "INFO", "WARNING", "ERROR", "DEBUG",
                "RequestsDependencyWarning", "UserWarning",
                "warn(", "warnings.warn", "BrowserUse",
                "Anonymized telemetry", "Daytona", "pydantic",
                "browser_use", "browser]", "root]",
                "filename=", "lineno=", "func_name=",
                "Z [info", "Z [error", "Z [warn",
                "sandbox.py", "telemetry"
            ]
            clean_lines = []
            for line in stdout.splitlines():
                stripped = line.strip()
                if stripped and not any(stripped.startswith(p) or p in stripped for p in skip_prefixes):
                    clean_lines.append(stripped)
            clean_output = "\n".join(clean_lines).strip()
        

        # Detect any image files mentioned in the response
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
        detected_images = []
        if clean_output:
            import re
            # Look for filenames with image extensions in the response
            words = re.findall(r'[\w\-]+\.(?:png|jpg|jpeg|gif|webp|bmp)', clean_output, re.IGNORECASE)
            for fname in words:
                fpath = os.path.join(WORKSPACE_DIR, fname)
                if os.path.exists(fpath):
                    detected_images.append(fname)

        memory_manager.save_memory(
            content=f"Web prompt: {request.prompt[:200]}",
            agent_id="web_user",
            category="user_interactions",
            importance=5
        )

        stream_log(task_id, "Task complete", "complete")
        return {
            "success": True,
            "prompt": request.prompt,
            "response": clean_output if clean_output else stdout,
            "images": detected_images,
            "task_id": task_id,
            "timestamp": datetime.now().isoformat()
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Request timed out after 10 minutes")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


# =========================
# FILE BROWSER ENDPOINTS
# =========================

@app.get("/api/files")
async def list_files():
    """List all user-facing output files in the workspace"""
    try:
        files = []
        for entry in os.scandir(WORKSPACE_DIR):
            if entry.is_file():
                name = entry.name
                ext = os.path.splitext(name)[1].lower()
                if name in HIDDEN_FILES:
                    continue
                if ext not in ALLOWED_EXTENSIONS:
                    continue
                stat = entry.stat()
                files.append({
                    "name": name,
                    "size": stat.st_size,
                    "size_display": _format_size(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "modified_display": datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %Y %I:%M %p"),
                    "extension": ext.lstrip(".").upper() if ext else "FILE"
                })
        files.sort(key=lambda x: x["modified"], reverse=True)
        return {"files": files, "count": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files/download/{filename}")
async def download_file(filename: str):
    safe_name = os.path.basename(filename)
    if safe_name in HIDDEN_FILES:
        raise HTTPException(status_code=403, detail="Access denied")
    file_path = os.path.join(WORKSPACE_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=403, detail="File type not allowed")
    return FileResponse(path=file_path, filename=safe_name, media_type="application/octet-stream")


@app.delete("/api/files/{filename}")
async def delete_file(filename: str):
    safe_name = os.path.basename(filename)
    if safe_name in HIDDEN_FILES:
        raise HTTPException(status_code=403, detail="Access denied")
    file_path = os.path.join(WORKSPACE_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=403, detail="File type not allowed")
    os.remove(file_path)
    return {"success": True, "deleted": safe_name}


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


# =========================
# DIRECT CHAT ENDPOINT
# =========================

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []
    image_base64: Optional[str] = None
    image_media_type: Optional[str] = None

@app.post("/api/chat")
async def direct_chat(request: ChatRequest):
    """Direct Claude chat without full agent pipeline - for quick questions"""
    try:
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        # Read API key from OpenManus config
        import tomllib
        config_path = os.path.join(OPENMANUS_DIR, "config", "config.toml")
        try:
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            api_key = config.get("llm", {}).get("api_key", "")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Config read error: {str(e)}")

        if not api_key:
            raise HTTPException(status_code=500, detail="API key not found in config")

        client = anthropic.Anthropic(api_key=api_key)

        # Build message history for context
        messages = []
        for msg in (request.history or [])[-10:]:
            if msg.get("role") in ["user", "assistant"]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        # Add current message - with optional image
        if request.image_base64 and request.image_media_type:
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": request.image_media_type,
                            "data": request.image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": request.message or "Describe this image."
                    }
                ]
            })
        else:
            messages.append({"role": "user", "content": request.message})

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system="""You are GenTeks AI, the internal AI assistant for GenTeks IT — a family-owned, full-service Managed Service Provider based in Las Vegas, NV with operations in Denver, CO, founded in 2018. You assist the GenTeks team with day-to-day IT operations, client communications, research, and business tasks.

ABOUT GENTEKS:
- Services: Managed IT, cybersecurity, backup & disaster recovery, antivirus, VoIP, and commercial/residential IT support
- Tools in use: AutoTask (ticketing), IT Glue (documentation), Datto RMM (remote monitoring), BullPhish ID (security awareness), RapidFire Tools (assessments), Slack (communication)
- Team size: ~10 employees
- Clients: Small and mid-sized businesses in Las Vegas and Denver

YOUR ROLE:
- Answer IT questions with practical, experience-based knowledge
- Help draft professional client-facing communications
- Assist with internal documentation and SOPs
- Research vendors, products, and industry topics
- Support ticket triage and troubleshooting guidance
- Help with business operations, proposals, and reporting

CRITICAL RULES:
- You are in CHAT MODE. Never create files, never save to workspace, never use tools.
- Always write content directly in your response so the user can read and copy it immediately.
- If asked to draft an email, write the full email in your response.
- If asked to write a document, write the full content in your response.
- If asked to create a report or spreadsheet, write the content in your response as formatted text.
- For tasks requiring actual file creation (Word docs, Excel, PowerPoint), tell the user to switch to Task mode.
- Be concise, direct, and professional. Avoid unnecessary filler.
- Use IT industry terminology appropriately — this team is technically proficient.""",
            messages=messages
        )

        return {
            "success": True,
            "response": response.content[0].text,
            "timestamp": datetime.now().isoformat()
        }

    except anthropic.APIError as e:
        raise HTTPException(status_code=500, detail=f"API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


# =========================
# API ROUTES
# =========================

@app.get("/api/status")
async def get_system_status():
    system_status = agent_manager.get_system_status()
    memory_stats = memory_manager.get_system_memory_stats()
    return {
        "platform": "GenTeks AI Platform",
        "timestamp": datetime.now().isoformat(),
        "agents": system_status,
        "memory": memory_stats
    }


@app.get("/api/agents")
async def list_agents():
    return agent_manager.list_agents()


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.to_dict()


@app.post("/api/agents")
async def create_agent(request: AgentCreateRequest):
    try:
        kwargs = {}
        if request.capabilities:
            kwargs['capabilities'] = request.capabilities
        if request.tools:
            kwargs['tools'] = request.tools
        agent_id = agent_manager.create_agent(
            agent_type=request.agent_type,
            name=request.name,
            **kwargs
        )
        memory_manager.save_memory(
            content=f"New agent created: {request.name} ({agent_id})",
            agent_id="system",
            category="agent_creation",
            importance=7
        )
        return {"success": True, "agent_id": agent_id, "name": request.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/tasks")
async def assign_task(request: TaskRequest):
    result = agent_manager.assign_task(request.agent_id, request.task_description)
    memory_manager.save_memory(
        content=f"Task assigned to {request.agent_id}: {request.task_description}",
        agent_id="system",
        category="task_execution",
        importance=6
    )
    return result


@app.post("/api/messages")
async def send_message(request: MessageRequest):
    if request.target_id:
        target_agent = agent_manager.get_agent(request.target_id)
        if not target_agent:
            raise HTTPException(status_code=404, detail="Target agent not found")
        response = target_agent.receive_message(request.sender_id, request.message)
        return {"success": True, "response": response}
    else:
        responses = agent_manager.broadcast_message(request.sender_id, request.message)
        return {"success": True, "responses": responses}


@app.get("/api/memory/search")
async def search_memory(query: str, agent_id: str = None, category: str = None, limit: int = 10):
    results = memory_manager.search_memories(query, limit)
    return {"query": query, "results": results}


@app.get("/api/memory/stats")
async def get_memory_stats():
    return memory_manager.get_system_memory_stats()


@app.get("/api/memory/agent/{agent_id}")
async def get_agent_memory(agent_id: str):
    return memory_manager.get_agent_memory_summary(agent_id)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "agents_count": len(agent_manager.agents),
        "memory_entries": len(memory_manager.local_cache)
    }


# =========================
# RUN SERVER
# =========================

if __name__ == "__main__":
    print("Starting GenTeks AI Platform...")
    print("Access the platform at: http://localhost:8000")
    print("API documentation at: http://localhost:8000/docs")

    uvicorn.run(
        "web_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
