import os
import logging
from dotenv import load_dotenv
from langgraph.types import Command
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition, ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain.messages import HumanMessage, AIMessage, RemoveMessage
from langchain_core.runnables import RunnableConfig

from app.context import State
import app.nodes as nodes
import app.tools as tools
import app.conditions as conditions

load_dotenv()

# Build workflow & Add nodes
workflow = StateGraph(State)
workflow.add_node(nodes.intent_router)
workflow.add_node(nodes.bookkeeping)
workflow.add_node(nodes.accounting)
workflow.add_node(nodes.other)
workflow.add_node(nodes.cleanup)
workflow.add_node(ToolNode([tools.query, tools.exchange_rate], name="analyzing"))
workflow.add_node(nodes.recording)
workflow.add_node(ToolNode([tools.retrieve], name="retrieval"))
workflow.add_node(nodes.enquiring)


# Build edges
workflow.add_edge(START, "intent_router")
workflow.add_conditional_edges(
    "intent_router",
    lambda state: state["intent"],
    {
        "bookkeeping": "bookkeeping",
        "accounting": "accounting",
        "other": "other",
    },
)
workflow.add_conditional_edges(
    "bookkeeping",
    conditions.after_bookkeeping,
    {
        "retrieve": "retrieval",
        "record": "recording",
        "enquire": "enquiring",
        "cancel": "cleanup",
    },
)
workflow.add_edge("retrieval", "bookkeeping")
workflow.add_edge("enquiring", "bookkeeping")
workflow.add_conditional_edges(
    "recording",
    lambda state: isinstance(state["messages"][-1], AIMessage),
    {
        True: "cleanup",
        False: "bookkeeping",
    },
)
# workflow.add_edge("recording", "cleanup")
workflow.add_conditional_edges(
    "accounting",
    tools_condition,
    {"tools": "analyzing", END: "cleanup"},
)
workflow.add_edge("analyzing", "accounting")
workflow.add_edge("other", "cleanup")
workflow.add_edge("cleanup", END)

# Set up memory and checkpointer
memory = MemorySaver()

# Compile workflow
chain = workflow.compile(checkpointer=memory)

# Visualize workflow
MERMAID_PATH = "workflow.mmd"
if os.getenv("ENV") == "dev":
    with open(MERMAID_PATH, "w", encoding="utf-8") as f:
        flowchart = chain.get_graph().draw_mermaid()
        f.write(flowchart)


# Invoke
def invoke(user_input: str, user_id: int):
    config: RunnableConfig = {"configurable": {"thread_id": str(user_id)}}

    snapshot = chain.get_state(config)
    if snapshot.tasks and snapshot.tasks[0].interrupts:
        # Resume from interrupt with the new user input
        logging.info(f"[Workflow] Resuming: {user_input}")
        state = chain.invoke(Command(resume=user_input), config=config)

    else:
        logging.info(f"[Workflow] New: {user_input}")
        state = chain.invoke(
            {"messages": [HumanMessage(user_input)]},
            config=config,
        )

    logging.info(f"[Workflow] End: {state}")

    if "__interrupt__" in state:
        # Interrupt for enquiring futher information
        logging.info(f"[Workflow] Interrupt: {state['__interrupt__']}")
        response = state["__interrupt__"][0].value

    else:
        # Normal response after bookkeeping or accounting
        last = state["messages"][-1]
        logging.info(f"[Workflow] Response: {last}")
        response = {"text": last.content}

        if state["intent"] is None:
            logging.info("[Workflow] Cleaup response.")
            chain.update_state(
                values={"messages": [RemoveMessage(state["messages"][-1].id)]},
                config=config,
            )

    return response
