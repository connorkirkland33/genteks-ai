import os
import shutil
from datetime import datetime
from app.tool.base import BaseTool

# Absolute boundary - tool cannot touch anything outside this path
PROJECT_ROOT = os.path.abspath(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
)
BACKUP_DIR = os.path.join(PROJECT_ROOT, "workspace", "backups")


def _is_safe_path(path: str) -> bool:
    """Ensure the path stays within the project folder."""
    abs_path = os.path.abspath(path)
    return abs_path.startswith(PROJECT_ROOT)


def _backup_file(path: str) -> str:
    """Create a backup before any file is modified."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.basename(path)
    backup_path = os.path.join(BACKUP_DIR, f"{filename}.{timestamp}.bak")
    shutil.copy2(path, backup_path)
    return backup_path


class SelfImproveTool(BaseTool):
    name: str = "self_improve"
    description: str = (
        "Allows OpenManus to read and modify its own source files for self-improvement. "
        "Actions: 'read' a file, 'write' changes to a file (auto-backs up first), "
        "'list' files in a directory, 'restore' a file from backup. "
        "All paths must be within the OpenManus project folder only."
    )

    async def execute(
        self,
        action: str = "",
        path: str = "",
        content: str = "",
        backup_timestamp: str = ""
    ) -> dict:

        # Always resolve relative to project root
        if path:
            full_path = os.path.abspath(
                os.path.join(PROJECT_ROOT, path)
            )
        else:
            full_path = ""

        # Safety check on every operation
        if full_path and not _is_safe_path(full_path):
            return {"output": f"Access denied. Path is outside the OpenManus project folder."}

        # READ a file
        if action == "read":
            if not os.path.exists(full_path):
                return {"output": f"File not found: {path}"}
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"output": f"Contents of {path}:\n\n{content}"}

        # LIST files in a directory
        elif action == "list":
            target = full_path if full_path else PROJECT_ROOT
            if not os.path.isdir(target):
                return {"output": f"Not a directory: {path}"}
            items = os.listdir(target)
            formatted = "\n".join(items)
            return {"output": f"Files in {path or 'project root'}:\n{formatted}"}

        # WRITE changes to a file (backs up first)
        elif action == "write":
            if not full_path:
                return {"output": "Error: No path provided."}
            if not content:
                return {"output": "Error: No content provided."}
            if os.path.exists(full_path):
                backup_path = _backup_file(full_path)
                backup_msg = f"Backup created at: {backup_path}\n"
            else:
                backup_msg = "New file - no backup needed.\n"
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"output": f"{backup_msg}File written successfully: {path}"}

        # RESTORE a file from backup
        elif action == "restore":
            if not full_path:
                return {"output": "Error: No path provided."}
            filename = os.path.basename(full_path)
            backups = [
                f for f in os.listdir(BACKUP_DIR)
                if f.startswith(filename)
            ]
            if not backups:
                return {"output": f"No backups found for {filename}"}
            backups.sort(reverse=True)
            latest = os.path.join(BACKUP_DIR, backups[0])
            shutil.copy2(latest, full_path)
            return {"output": f"Restored {path} from backup: {backups[0]}"}

        # LIST available backups
        elif action == "list_backups":
            if not os.path.exists(BACKUP_DIR):
                return {"output": "No backups exist yet."}
            backups = os.listdir(BACKUP_DIR)
            if not backups:
                return {"output": "No backups exist yet."}
            return {"output": "Available backups:\n" + "\n".join(sorted(backups, reverse=True))}

        else:
            return {"output": f"Unknown action '{action}'. Use: read, write, list, restore, list_backups."}