import argparse
import asyncio
import sys
import os
import json
from app.agent.manus import Manus
from app.logger import logger
from app.schema import AgentState

async def main():
    parser = argparse.ArgumentParser(description="Run Manus agent with a prompt")
    parser.add_argument(
        "--prompt", type=str, required=False, help="Input prompt for the agent"
    )
    args = parser.parse_args()

    # Set working directory to workspace so all files save there
    workspace_dir = os.path.join(os.path.dirname(__file__), "workspace")
    os.makedirs(workspace_dir, exist_ok=True)
    os.chdir(workspace_dir)

    agent = await Manus.create()
    try:
        if args.prompt:
            if not args.prompt.strip():
                logger.warning("Empty prompt provided.")
                return
            logger.warning("Processing your request...")
            await agent.run(args.prompt)
            logger.info("Request processing completed.")

            # Write the last agent response to a temp file for web API to read
            response_file = os.path.join(os.path.dirname(__file__), "workspace", "last_response.json")
            try:
                if agent.memory and agent.memory.messages:
                    for msg in reversed(agent.memory.messages):
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            for tc in msg.tool_calls:
                                if hasattr(tc, 'function') and tc.function.name == 'terminate':
                                    args_dict = json.loads(tc.function.arguments)
                                    answer = args_dict.get("answer", "").strip()
                                    # If answer is empty or generic, check for assistant messages
                                    if not answer or answer.lower().strip(".").strip() in ["task completed", "done", "complete", "task complete"]:
                                        for m in reversed(agent.memory.messages):
                                            if hasattr(m, 'content') and m.content and hasattr(m, 'role') and m.role == 'assistant':
                                                if isinstance(m.content, str) and len(m.content) > 20:
                                                    answer = m.content
                                                    break
                                    if not answer:
                                        answer = "The request could not be completed. Please try rephrasing or switch to Chat mode for questions."
                                    with open(response_file, 'w') as f:
                                        json.dump({"answer": answer}, f)
                                    break
            except Exception as e:
                with open(response_file, 'w') as f:
                    json.dump({"answer": f"An error occurred: {str(e)}"}, f)
            return

        # Otherwise loop continuously
        print("\nOpenManus is ready. Type 'exit' to quit.\n")
        while True:
            prompt = input("Enter your prompt: ")
            if prompt.strip().lower() == "exit":
                print("Shutting down OpenManus.")
                break
            if not prompt.strip():
                logger.warning("Empty prompt. Please enter a task.")
                continue
            logger.warning("Processing your request...")
            # Reset agent state so it can accept new tasks
            agent.state = AgentState.IDLE
            agent.current_step = 0
            await agent.run(prompt)
            logger.info("Task completed. Ready for next task.\n")

    except KeyboardInterrupt:
        logger.warning("Operation interrupted.")
    finally:
        await agent.cleanup()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
