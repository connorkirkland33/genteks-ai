import json
import os
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.tool.base import BaseTool
from pydantic import Field
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
import time
from difflib import SequenceMatcher

# Configuration
MEMORY_FILE = "workspace/memory.json"
BACKUP_FILE = "workspace/memory_backup.json"
MAX_MEMORY_SIZE = 10000  # Maximum number of memories
MAX_CONTENT_LENGTH = 10000  # Maximum characters per memory
SEARCH_RESULT_LIMIT = 50  # Maximum search results to return

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _create_backup():
    """Create a backup of the current memory file."""
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'r') as src, open(BACKUP_FILE, 'w') as dst:
                dst.write(src.read())
            logger.info("Memory backup created successfully")
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")

def _load_memory() -> List[Dict[str, Any]]:
    """Load memories from file with error handling and validation."""
    if not os.path.exists(MEMORY_FILE):
        logger.info("Memory file doesn't exist, starting with empty memory")
        return []
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with open(MEMORY_FILE, "r", encoding='utf-8') as f:
                # Try to acquire a shared lock for reading
                if HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                
                data = json.load(f)
                
                # Validate data structure
                if not isinstance(data, list):
                    logger.error("Memory file contains invalid data structure")
                    return _restore_from_backup()
                
                # Validate each memory entry
                validated_memories = []
                for memory in data:
                    if _validate_memory_entry(memory):
                        validated_memories.append(memory)
                    else:
                        logger.warning(f"Invalid memory entry found and skipped: {memory}")
                
                logger.info(f"Loaded {len(validated_memories)} valid memories")
                return validated_memories
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                return _restore_from_backup()
            time.sleep(0.1)  # Brief delay before retry
            
        except Exception as e:
            logger.error(f"Error loading memory (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                return _restore_from_backup()
            time.sleep(0.1)
    
    return []

def _restore_from_backup() -> List[Dict[str, Any]]:
    """Restore memories from backup file."""
    logger.info("Attempting to restore from backup")
    try:
        if os.path.exists(BACKUP_FILE):
            with open(BACKUP_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    logger.info("Successfully restored from backup")
                    return data
    except Exception as e:
        logger.error(f"Failed to restore from backup: {e}")
    
    logger.warning("Starting with empty memory due to corruption")
    return []

def _validate_memory_entry(memory: Dict[str, Any]) -> bool:
    """Validate a memory entry structure."""
    required_fields = ['id', 'timestamp', 'content']
    if not isinstance(memory, dict):
        return False
    
    for field in required_fields:
        if field not in memory:
            return False
    
    # Validate data types
    if not isinstance(memory['id'], int) or not isinstance(memory['content'], str):
        return False
    
    # Validate timestamp format
    try:
        datetime.fromisoformat(memory['timestamp'].replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return False
    
    return True

def _save_memory(memories: List[Dict[str, Any]]) -> bool:
    """Save memories to file with error handling and atomic writes."""
    try:
        # Create backup before saving
        _create_backup()
        
        # Ensure workspace directory exists
        os.makedirs("workspace", exist_ok=True)
        
        # Write to temporary file first (atomic write)
        temp_file = MEMORY_FILE + ".tmp"
        with open(temp_file, "w", encoding='utf-8') as f:
            # Try to acquire exclusive lock for writing
            if HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            json.dump(memories, f, indent=2, ensure_ascii=False)
        
        # Atomically replace the original file
        if os.name == 'nt':  # Windows
            if os.path.exists(MEMORY_FILE):
                os.remove(MEMORY_FILE)
        os.rename(temp_file, MEMORY_FILE)
        
        logger.info(f"Successfully saved {len(memories)} memories")
        return True
        
    except Exception as e:
        logger.error(f"Error saving memory: {e}")
        # Clean up temp file if it exists
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
        return False

def _sanitize_input(text: str, max_length: int = MAX_CONTENT_LENGTH) -> str:
    """Sanitize and validate input text."""
    if not isinstance(text, str):
        text = str(text)
    
    # Remove potentially dangerous characters
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Limit length
    if len(text) > max_length:
        text = text[:max_length] + "... [truncated]"
    
    return text.strip()

def _fuzzy_search(query: str, memories: List[Dict[str, Any]], threshold: float = 0.3) -> List[Dict[str, Any]]:
    """Perform fuzzy search on memories with similarity scoring."""
    query_lower = query.lower()
    results = []
    
    for memory in memories:
        content_lower = memory['content'].lower()
        
        # Exact substring match gets highest score
        if query_lower in content_lower:
            similarity = 1.0
        else:
            # Use sequence matcher for fuzzy matching
            similarity = SequenceMatcher(None, query_lower, content_lower).ratio()
        
        if similarity >= threshold:
            memory_with_score = memory.copy()
            memory_with_score['similarity'] = similarity
            results.append(memory_with_score)
    
    # Sort by similarity score (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    return results[:SEARCH_RESULT_LIMIT]

def _cleanup_old_memories(memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove old memories if we exceed the maximum size."""
    if len(memories) <= MAX_MEMORY_SIZE:
        return memories
    
    # Sort by timestamp and keep the most recent ones
    memories.sort(key=lambda x: x['timestamp'], reverse=True)
    removed_count = len(memories) - MAX_MEMORY_SIZE
    logger.info(f"Cleaned up {removed_count} old memories")
    
    return memories[:MAX_MEMORY_SIZE]

class MemoryTool(BaseTool):
    name: str = "memory"
    description: str = (
        "Save and retrieve persistent memory across sessions. "
        "Use action='save' with a 'content' field to store information. "
        "Use action='retrieve' with a 'query' field to search past memories. "
        "Use action='list' to see all stored memories. "
        "Use action='delete' with an 'id' field to remove a specific memory. "
        "Use action='stats' to get memory statistics."
    )

    async def execute(self, action: str = "", content: str = "", query: str = "", id: str = "", tags: str = "") -> dict:
        """Execute memory operations with comprehensive error handling."""
        try:
            # Validate action parameter
            valid_actions = ["save", "retrieve", "list", "delete", "stats"]
            if action not in valid_actions:
                return {"output": f"Error: Unknown action '{action}'. Valid actions: {', '.join(valid_actions)}"}
            
            memories = _load_memory()
            
            if action == "save":
                if not content:
                    return {"output": "Error: No content provided to save."}
                
                # Sanitize content
                sanitized_content = _sanitize_input(content)
                if not sanitized_content:
                    return {"output": "Error: Content is empty after sanitization."}
                
                # Check for duplicates
                content_lower = sanitized_content.lower()
                for existing in memories:
                    if existing['content'].lower() == content_lower:
                        return {"output": f"Warning: Similar content already exists (ID: {existing['id']}). Not saving duplicate."}
                
                # Create new memory entry
                entry = {
                    "id": max([m['id'] for m in memories], default=0) + 1,
                    "timestamp": datetime.now().isoformat(),
                    "content": sanitized_content,
                    "tags": [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
                }
                
                memories.append(entry)
                memories = _cleanup_old_memories(memories)
                
                if _save_memory(memories):
                    return {"output": f"Memory saved successfully with ID {entry['id']}."}
                else:
                    return {"output": "Error: Failed to save memory to file."}

            elif action == "retrieve":
                if not query:
                    return {"output": "Error: No query provided for search."}
                
                sanitized_query = _sanitize_input(query, 1000)  # Shorter limit for queries
                results = _fuzzy_search(sanitized_query, memories)
                
                if not results:
                    return {"output": f"No memories found matching '{sanitized_query}'."}
                
                # Format results with similarity scores
                output_lines = []
                for result in results:
                    similarity_pct = int(result['similarity'] * 100)
                    tags_str = f" [Tags: {', '.join(result.get('tags', []))}]" if result.get('tags') else ""
                    output_lines.append(
                        f"[ID: {result['id']}] [{result['timestamp']}] (Match: {similarity_pct}%){tags_str}\n{result['content']}"
                    )
                
                return {"output": f"Found {len(results)} matching memories:\n\n" + "\n\n".join(output_lines)}

            elif action == "list":
                if not memories:
                    return {"output": "No memories stored yet."}
                
                # Sort by timestamp (most recent first)
                memories.sort(key=lambda x: x['timestamp'], reverse=True)
                
                output_lines = []
                for memory in memories:
                    tags_str = f" [Tags: {', '.join(memory.get('tags', []))}]" if memory.get('tags') else ""
                    output_lines.append(
                        f"ID {memory['id']} [{memory['timestamp']}]{tags_str}:\n{memory['content']}"
                    )
                
                return {"output": f"Total memories: {len(memories)}\n\n" + "\n\n".join(output_lines)}

            elif action == "delete":
                if not id:
                    return {"output": "Error: No ID provided for deletion."}
                
                try:
                    memory_id = int(id)
                except ValueError:
                    return {"output": f"Error: Invalid ID '{id}'. ID must be a number."}
                
                # Find and remove the memory
                original_count = len(memories)
                memories = [m for m in memories if m['id'] != memory_id]
                
                if len(memories) == original_count:
                    return {"output": f"Error: No memory found with ID {memory_id}."}
                
                if _save_memory(memories):
                    return {"output": f"Memory with ID {memory_id} deleted successfully."}
                else:
                    return {"output": "Error: Failed to save changes after deletion."}

            elif action == "stats":
                if not memories:
                    return {"output": "No memories stored yet."}
                
                # Calculate statistics
                total_memories = len(memories)
                total_chars = sum(len(m['content']) for m in memories)
                avg_chars = total_chars // total_memories if total_memories > 0 else 0
                
                # Find oldest and newest
                timestamps = [datetime.fromisoformat(m['timestamp'].replace('Z', '+00:00')) for m in memories]
                oldest = min(timestamps)
                newest = max(timestamps)
                
                # Count memories by tags
                all_tags = []
                for m in memories:
                    all_tags.extend(m.get('tags', []))
                tag_counts = {}
                for tag in all_tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
                
                stats_output = [
                    f"Memory Statistics:",
                    f"Total memories: {total_memories}",
                    f"Total characters: {total_chars:,}",
                    f"Average characters per memory: {avg_chars}",
                    f"Oldest memory: {oldest.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Newest memory: {newest.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Memory file size: {os.path.getsize(MEMORY_FILE) if os.path.exists(MEMORY_FILE) else 0} bytes"
                ]
                
                if tag_counts:
                    stats_output.append(f"\nTop tags:")
                    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
                    for tag, count in sorted_tags:
                        stats_output.append(f"  {tag}: {count}")
                
                return {"output": "\n".join(stats_output)}

        except Exception as e:
            logger.error(f"Unexpected error in memory tool: {e}")
            return {"output": f"Error: An unexpected error occurred: {str(e)}"}