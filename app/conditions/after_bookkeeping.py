from langchain.messages import AIMessage

from app.context import State


def after_bookkeeping(state: State):
    message = state["messages"][-1]

    if isinstance(message, AIMessage):
        if message.tool_calls:
            first_tool = message.tool_calls[0]["name"]

            if first_tool == "enquiring_message":
                # Telegram Options response
                return "enquire"

            elif first_tool == "retrieve":
                # Retrieve relevant information for bookkeeping
                return "retrieve"

            else:
                # Record the transaction
                return "record"

        else:
            # If there are no tool calls, it means the AI has provided a final response without needing further information or actions, so we can consider the process complete.
            return "cancel"
