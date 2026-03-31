from app.tool.base import BaseTool


_TERMINATE_DESCRIPTION = """Terminate the interaction when the request is met OR if the assistant cannot proceed further with the task.
When you have finished all the tasks, call this tool to end the work."""


class Terminate(BaseTool):
    name: str = "terminate"
    description: str = _TERMINATE_DESCRIPTION

    parameters: dict = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["success", "failure"],
            },
            "answer": {
                "type": "string",
                "description": "Final answer to return to the user"
            }
        },
        "required": ["status", "answer"],
    }

    async def execute(self, status: str, answer: str) -> dict:
        return {
            "terminated": True,
            "status": status,
            "answer": answer
        }
