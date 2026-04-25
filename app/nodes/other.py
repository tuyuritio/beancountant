from langgraph.graph import MessagesState
from langchain.messages import AIMessage


def other(state: MessagesState):
    state["messages"].append(AIMessage("Fine."))
