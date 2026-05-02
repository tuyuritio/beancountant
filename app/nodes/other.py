from langchain.messages import AIMessage

from app.context import State

def other(state: State):
    state["messages"].append(AIMessage("Fine."))
