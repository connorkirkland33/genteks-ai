"""
GenTeks AI - Memory Manager
Supports MySQL backend with automatic fallback to JSON for local development.
"""

import json
import os
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

# ========================
# MYSQL CONNECTION
# ========================

def _get_mysql_config():
    """Read MySQL config from config.toml if available."""
    try:
        import tomllib
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.toml")
        if not os.path.exists(config_path):
            return None
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        db = config.get("database", {})
        if not db.get("host"):
            return None
        return db
    except Exception:
        return None


def _get_connection():
    """Get a MySQL connection. Returns None if MySQL is not configured."""
    try:
        import mysql.connector
        cfg = _get_mysql_config()
        if not cfg:
            return None
        conn = mysql.connector.connect(
            host=cfg.get("host", "localhost"),
            port=cfg.get("port", 3306),
            user=cfg.get("user", "genteks"),
            password=cfg.get("password", ""),
            database=cfg.get("database", "genteks_ai"),
            connection_timeout=5
        )
        return conn
    except Exception:
        return None


def _mysql_available():
    """Check if MySQL is reachable."""
    conn = _get_connection()
    if conn:
        conn.close()
        return True
    return False


# ========================
# SCHEMA INIT
# ========================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id VARCHAR(64) PRIMARY KEY,
    content TEXT NOT NULL,
    agent_id VARCHAR(128) DEFAULT 'system',
    category VARCHAR(128) DEFAULT 'general',
    importance INT DEFAULT 5,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata JSON
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

def init_schema():
    """Create the memories table if it doesn't exist."""
    conn = _get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(SCHEMA_SQL)
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[MemoryManager] Schema init error: {e}")
        return False


# ========================
# MEMORY MANAGER CLASS
# ========================

class MemoryManager:
    """
    Unified memory manager.
    Uses MySQL when available, falls back to JSON for local development.
    """

    def __init__(self):
        self.use_mysql = False
        self.json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")
        self.local_cache: Dict[str, Any] = {}
        self._init()

    def _init(self):
        """Initialize backend — MySQL if available, JSON otherwise."""
        if _mysql_available():
            if init_schema():
                self.use_mysql = True
                print("[MemoryManager] Using MySQL backend")
                return
        # Fallback to JSON
        self.use_mysql = False
        print("[MemoryManager] MySQL not available — using JSON fallback")
        self._load_json()

    def _load_json(self):
        """Load memories from JSON file."""
        try:
            if os.path.exists(self.json_path):
                with open(self.json_path, "r") as f:
                    data = json.load(f)
                    self.local_cache = data.get("memories", {})
        except Exception:
            self.local_cache = {}

    def _save_json(self):
        """Persist memories to JSON file."""
        try:
            backup = self.json_path.replace(".json", "_backup.json")
            if os.path.exists(self.json_path):
                import shutil
                shutil.copy2(self.json_path, backup)
            with open(self.json_path, "w") as f:
                json.dump({"memories": self.local_cache, "updated_at": datetime.now().isoformat()}, f, indent=2)
        except Exception as e:
            print(f"[MemoryManager] JSON save error: {e}")

    # ========================
    # PUBLIC API
    # ========================

    def save_memory(self, content: str, agent_id: str = "system", category: str = "general",
                    importance: int = 5, metadata: Optional[Dict] = None) -> Optional[str]:
        """Save a memory entry. Returns memory ID on success."""
        memory_id = str(uuid.uuid4())
        timestamp = datetime.now()

        if self.use_mysql:
            return self._mysql_save(memory_id, content, agent_id, category, importance, timestamp, metadata)
        else:
            return self._json_save(memory_id, content, agent_id, category, importance, timestamp, metadata)

    def search_memories(self, query: str, limit: int = 10,
                        agent_id: Optional[str] = None,
                        category: Optional[str] = None) -> List[Dict]:
        """Search memories by content. Returns list of matching entries."""
        if self.use_mysql:
            return self._mysql_search(query, limit, agent_id, category)
        else:
            return self._json_search(query, limit, agent_id, category)

    def get_system_memory_stats(self) -> Dict:
        """Return stats about stored memories."""
        if self.use_mysql:
            return self._mysql_stats()
        else:
            return self._json_stats()

    def get_agent_memory_summary(self, agent_id: str) -> Dict:
        """Return memory summary for a specific agent."""
        if self.use_mysql:
            return self._mysql_agent_summary(agent_id)
        else:
            return self._json_agent_summary(agent_id)

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory entry by ID."""
        if self.use_mysql:
            return self._mysql_delete(memory_id)
        else:
            return self._json_delete(memory_id)

    # ========================
    # MYSQL BACKEND
    # ========================

    def _mysql_save(self, memory_id, content, agent_id, category, importance, timestamp, metadata):
        conn = _get_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO memories (id, content, agent_id, category, importance, timestamp, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (memory_id, content, agent_id, category, importance, timestamp,
                 json.dumps(metadata) if metadata else None)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return memory_id
        except Exception as e:
            print(f"[MemoryManager] MySQL save error: {e}")
            return None

    def _mysql_search(self, query, limit, agent_id, category):
        conn = _get_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor(dictionary=True)
            sql = "SELECT * FROM memories WHERE content LIKE %s"
            params = [f"%{query}%"]
            if agent_id:
                sql += " AND agent_id = %s"
                params.append(agent_id)
            if category:
                sql += " AND category = %s"
                params.append(category)
            sql += " ORDER BY importance DESC, timestamp DESC LIMIT %s"
            params.append(limit)
            cursor.execute(sql, params)
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            for r in results:
                if r.get("timestamp"):
                    r["timestamp"] = r["timestamp"].isoformat()
                if r.get("metadata") and isinstance(r["metadata"], str):
                    r["metadata"] = json.loads(r["metadata"])
            return results
        except Exception as e:
            print(f"[MemoryManager] MySQL search error: {e}")
            return []

    def _mysql_stats(self):
        conn = _get_connection()
        if not conn:
            return {"total_memories": 0, "backend": "mysql_unavailable"}
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as total FROM memories")
            total = cursor.fetchone()["total"]
            cursor.execute("SELECT agent_id, COUNT(*) as count FROM memories GROUP BY agent_id")
            agents = {r["agent_id"]: r["count"] for r in cursor.fetchall()}
            cursor.execute("SELECT DISTINCT category FROM memories")
            categories = [r["category"] for r in cursor.fetchall()]
            cursor.execute("SELECT AVG(importance) as avg_imp FROM memories")
            avg = cursor.fetchone()["avg_imp"] or 0
            cursor.close()
            conn.close()
            return {
                "total_memories": total,
                "agents": agents,
                "available_categories": categories,
                "average_importance": round(float(avg), 2),
                "backend": "mysql"
            }
        except Exception as e:
            print(f"[MemoryManager] MySQL stats error: {e}")
            return {"total_memories": 0, "backend": "mysql_error", "error": str(e)}

    def _mysql_agent_summary(self, agent_id):
        conn = _get_connection()
        if not conn:
            return {}
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as total FROM memories WHERE agent_id = %s", (agent_id,))
            total = cursor.fetchone()["total"]
            cursor.execute(
                "SELECT * FROM memories WHERE agent_id = %s ORDER BY timestamp DESC LIMIT 5",
                (agent_id,)
            )
            recent = cursor.fetchall()
            cursor.close()
            conn.close()
            for r in recent:
                if r.get("timestamp"):
                    r["timestamp"] = r["timestamp"].isoformat()
            return {"agent_id": agent_id, "total_memories": total, "recent": recent}
        except Exception as e:
            return {"agent_id": agent_id, "error": str(e)}

    def _mysql_delete(self, memory_id):
        conn = _get_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = %s", (memory_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            cursor.close()
            conn.close()
            return deleted
        except Exception as e:
            print(f"[MemoryManager] MySQL delete error: {e}")
            return False

    # ========================
    # JSON FALLBACK BACKEND
    # ========================

    def _json_save(self, memory_id, content, agent_id, category, importance, timestamp, metadata):
        entry = {
            "id": memory_id,
            "content": content,
            "agent_id": agent_id,
            "category": category,
            "importance": importance,
            "timestamp": timestamp.isoformat(),
            "metadata": metadata or {}
        }
        self.local_cache[memory_id] = entry
        self._save_json()
        return memory_id

    def _json_search(self, query, limit, agent_id, category):
        results = []
        q = query.lower()
        for entry in self.local_cache.values():
            if q not in entry.get("content", "").lower():
                continue
            if agent_id and entry.get("agent_id") != agent_id:
                continue
            if category and entry.get("category") != category:
                continue
            results.append(entry)
        results.sort(key=lambda x: (x.get("importance", 0), x.get("timestamp", "")), reverse=True)
        return results[:limit]

    def _json_stats(self):
        memories = list(self.local_cache.values())
        agents = {}
        categories = set()
        importances = []
        for m in memories:
            aid = m.get("agent_id", "unknown")
            agents[aid] = agents.get(aid, 0) + 1
            categories.add(m.get("category", "general"))
            importances.append(m.get("importance", 5))
        avg = sum(importances) / len(importances) if importances else 0
        return {
            "total_memories": len(memories),
            "agents": agents,
            "available_categories": list(categories),
            "average_importance": round(avg, 2),
            "backend": "json_fallback"
        }

    def _json_agent_summary(self, agent_id):
        memories = [m for m in self.local_cache.values() if m.get("agent_id") == agent_id]
        memories.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return {
            "agent_id": agent_id,
            "total_memories": len(memories),
            "recent": memories[:5]
        }

    def _json_delete(self, memory_id):
        if memory_id in self.local_cache:
            del self.local_cache[memory_id]
            self._save_json()
            return True
        return False


# ========================
# SINGLETON
# ========================
memory_manager = MemoryManager()
