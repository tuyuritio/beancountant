from langchain.messages import RemoveMessage

from app.context import State


def cleanup(state: State):
    """
    Cleanup node to remove all messages except the last one and reset intent to None.
    """

    return {
        "messages": [
            RemoveMessage(id=message.id)
            for message in state["messages"][:-1]
            if message.id is not None
        ],
        "intent": None,
    }
