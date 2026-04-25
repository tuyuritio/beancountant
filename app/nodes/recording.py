from langchain.messages import HumanMessage, AIMessage

from app.context import State
from app.tools.record import record


def recording(state: State):
    message = state["messages"][-1]

    if isinstance(message, AIMessage):
        if message.tool_calls:
            for call in message.tool_calls:
                if call["name"] == "record":
                    record_args = call["args"]
                    result = record.invoke(record_args)

                    if result is True:
                        # Record accepted
                        return {"messages": [AIMessage("Recorded!")]}

                    elif result is False:
                        # Record cancelled
                        return {"messages": [AIMessage("Cancelled.")]}

                    else:
                        # User feedback
                        return {"messages": [HumanMessage(result)]}
