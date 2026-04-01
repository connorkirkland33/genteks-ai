"""
Multi-Agent System for OpenManus Web Platform
Core agent management and coordination system with persistent memory
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class AgentState:
    """Represents the current state of an agent"""
    agent_id: str
    name: str
    status: str  # 'active', 'idle', 'busy', 'error'
    current_task: Optional[str]
    created_at: str
    last_activity: str
    memory_entries: List[str]
    capabilities: List[str]


class BaseAgent:
    """
    Base class for all agents in the multi-agent platform
    Provides core functionality including memory management, communication, and task execution
    """
    
    def __init__(self, name: str, capabilities: List[str] = None):
        self.agent_id = str(uuid.uuid4())
        self.name = name
        self.capabilities = capabilities or []
        self.status = "idle"
        self.current_task = None
        self.created_at = datetime.now().isoformat()
        self.last_activity = self.created_at
        self.memory_entries = []
        
        # Initialize agent in persistent memory
        self._save_to_memory(f"Agent {self.name} initialized with ID: {self.agent_id}")
    
    def get_state(self) -> AgentState:
        """Get current agent state"""
        return AgentState(
            agent_id=self.agent_id,
            name=self.name,
            status=self.status,
            current_task=self.current_task,
            created_at=self.created_at,
            last_activity=self.last_activity,
            memory_entries=self.memory_entries,
            capabilities=self.capabilities
        )
    
    def _save_to_memory(self, content: str) -> None:
        """Save information to persistent memory"""
        memory_entry = f"[{self.name}:{self.agent_id}] {content}"
        self.memory_entries.append(memory_entry)
        self.last_activity = datetime.now().isoformat()
        
        # Note: In actual implementation, this would call the memory tool
        # memory.save(content=memory_entry)
    
    def _update_status(self, new_status: str, task: str = None) -> None:
        """Update agent status and current task"""
        old_status = self.status
        self.status = new_status
        self.current_task = task
        self.last_activity = datetime.now().isoformat()
        
        status_msg = f"Status changed from {old_status} to {new_status}"
        if task:
            status_msg += f" - Task: {task}"
        
        self._save_to_memory(status_msg)
    
    def execute_task(self, task_description: str) -> Dict[str, Any]:
        """Execute a task - to be overridden by specific agent implementations"""
        self._update_status("busy", task_description)
        
        try:
            result = self._process_task(task_description)
            self._update_status("idle")
            
            self._save_to_memory(f"Task completed: {task_description}")
            return {
                "success": True,
                "result": result,
                "agent_id": self.agent_id,
                "task": task_description
            }
            
        except Exception as e:
            self._update_status("error")
            self._save_to_memory(f"Task failed: {task_description} - Error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "agent_id": self.agent_id,
                "task": task_description
            }
    
    def _process_task(self, task_description: str) -> str:
        """Process the actual task - to be overridden by specific agent types"""
        return f"Base agent processed task: {task_description}"


class OpenManusAgent(BaseAgent):
    """Agent that integrates with OpenManus tools"""
    
    def __init__(self, name: str, tools: List[str] = None):
        self.available_tools = tools or ["memory", "str_replace_editor", "python_execute", "browser_use"]
        super().__init__(name, capabilities=self.available_tools)
    
    def use_memory_tool(self, action: str, content: str = None, query: str = None) -> Dict[str, Any]:
        """Interface to OpenManus memory tool"""
        # This would call the actual memory tool
        result = f"Memory {action} operation"
        if content:
            result += f" with content: {content[:50]}..."
        if query:
            result += f" with query: {query}"
        
        self._save_to_memory(f"Used memory tool: {result}")
        return {"tool": "memory", "action": action, "result": result}
    
    def use_file_editor(self, command: str, path: str, content: str = None) -> Dict[str, Any]:
        """Interface to OpenManus file editor tool"""
        result = f"File editor {command} on {path}"
        self._save_to_memory(f"Used file editor: {result}")
        return {"tool": "str_replace_editor", "command": command, "result": result}
    
    def use_browser(self, action: str, url: str = None, query: str = None) -> Dict[str, Any]:
        """Interface to OpenManus browser tool"""
        result = f"Browser {action}"
        if url:
            result += f" on {url}"
        if query:
            result += f" searching for {query}"
        
        self._save_to_memory(f"Used browser: {result}")
        return {"tool": "browser_use", "action": action, "result": result}


class AgentManager:
    """Manages multiple agents and coordinates their activities"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.task_queue: List[Dict[str, Any]] = []
        self.created_at = datetime.now().isoformat()
    
    def create_agent(self, agent_type: str, name: str, **kwargs) -> str:
        """Create a new agent and add it to the system"""
        if agent_type == "base":
            agent = BaseAgent(name, **kwargs)
        elif agent_type == "openmanus":
            agent = OpenManusAgent(name, **kwargs)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        self.agents[agent.agent_id] = agent
        return agent.agent_id
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent by ID"""
        return self.agents.get(agent_id)
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents and their current states"""
        return [agent.to_dict() for agent in self.agents.values()]
    
    def assign_task(self, agent_id: str, task_description: str) -> Dict[str, Any]:
        """Assign a task to a specific agent"""
        agent = self.get_agent(agent_id)
        if not agent:
            return {"success": False, "error": f"Agent {agent_id} not found"}
        
        return agent.execute_task(task_description)
    
    def broadcast_message(self, sender_id: str, message: str) -> List[Dict[str, Any]]:
        """Send a message from one agent to all other agents"""
        sender = self.get_agent(sender_id)
        if not sender:
            return [{"success": False, "error": f"Sender agent {sender_id} not found"}]
        
        responses = []
        for agent_id, agent in self.agents.items():
            if agent_id != sender_id:
                response = agent.receive_message(sender_id, message)
                responses.append({
                    "agent_id": agent_id,
                    "response": response
                })
        
        return responses
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        agent_statuses = {}
        for agent_id, agent in self.agents.items():
            agent_statuses[agent_id] = {
                "name": agent.name,
                "status": agent.status,
                "current_task": agent.current_task,
                "last_activity": agent.last_activity
            }
        
        return {
            "total_agents": len(self.agents),
            "system_created": self.created_at,
            "agents": agent_statuses,
            "task_queue_size": len(self.task_queue)
        }


# Global agent manager instance
agent_manager = AgentManager()


def initialize_default_agents():
    """Initialize a set of default agents for the platform"""
    # Create a coordinator agent
    coordinator_id = agent_manager.create_agent("openmanus", "MainCoordinator", 
                                               tools=["memory", "str_replace_editor"])
    
    # Create specialized agents
    web_agent_id = agent_manager.create_agent("openmanus", "WebAgent", 
                                            tools=["browser_use", "memory"])
    
    code_agent_id = agent_manager.create_agent("openmanus", "CodeAgent", 
                                             tools=["str_replace_editor", "python_execute", "memory"])
    
    return {
        "coordinator": coordinator_id,
        "web_agent": web_agent_id,
        "code_agent": code_agent_id
    }


if __name__ == "__main__":
    print("Multi-Agent Platform - Agent System Initialized")
    
    # Initialize default agents
    agent_ids = initialize_default_agents()
    print(f"Created default agents: {agent_ids}")
    
    # Show system status
    status = agent_manager.get_system_status()
    print(f"System Status: {json.dumps(status, indent=2)}")