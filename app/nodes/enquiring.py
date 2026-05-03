import logging
from langgraph.types import interrupt
from langchain.messages import AIMessage, ToolMessage

from app.context import State


def enquiring(state: State):
    message = state["messages"][-1]
    if isinstance(message, AIMessage):
        tool = message.tool_calls[0]

        logging.info(f"[Enquiring] Interrupt: {tool['args']}")
        response = interrupt(tool["args"])
        logging.info(f"[Enquiring] Response: {response}")

        return {
            "messages": [
                ToolMessage(
                    content=response,
                    tool_call_id=tool["id"],
                )
            ]
        }
