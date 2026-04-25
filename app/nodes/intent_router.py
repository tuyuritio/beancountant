import logging
from pydantic import BaseModel, Field
from typing import Literal
from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage

import app.context as env
from app.context import State


class IntentRouterOutput(BaseModel):
    """
    The output of the Intent Router node, indicating the determined intent of the user's input.
    """

    intent: Literal["bookkeeping", "accounting", "other"] = Field(
        description="The classified intent of the user's input, which determines the subsequent processing node in the workflow."
    )


model = init_chat_model(
    model_provider=env.LLM_PROVIDER,
    base_url=env.LLM_URL,
    model=env.LLM_MODEL,
    api_key=env.LLM_API_KEY,
    temperature=0,
).with_structured_output(IntentRouterOutput)

SYSTEM_PROMPT = """
Role
You are a highly efficient Intent Classification Engine for a personal finance application.
Your sole task is to analyze user input and route it to the correct functional module.

Intents
1. BOOKKEEPING
   - Triggered when the user wants to record a new transaction.
   - Keywords/Context: Spent, earned, bought, paid, income, expense, "just bought [item] for [price]".
2. ACCOUNTING
   - Triggered when the user wants to check history, query balances, or analyze spending habits.
   - Keywords/Context: How much, show me, report, total, "what did I spend on...", balance, summary.
3. OTHER
   - Triggered for general conversation, greetings, help requests, or any input that does not involve recording or analyzing financial data.
"""


def intent_router(state: State):
    message = model.invoke([SystemMessage(SYSTEM_PROMPT)] + state["messages"])
    intent = message.intent  # type: ignore

    logging.info(f"[Intent Router] {intent}")

    return {"intent": intent}  # type: ignore
