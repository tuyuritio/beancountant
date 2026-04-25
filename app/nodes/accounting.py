import logging
from datetime import datetime, timezone
from langgraph.graph import MessagesState
from langchain.messages import SystemMessage
from langchain.chat_models import init_chat_model

import app.context as env
from app.tools import query, exchange_rate


model = init_chat_model(
    model_provider=env.LLM_PROVIDER,
    base_url=env.LLM_URL,
    model=env.LLM_MODEL,
    api_key=env.LLM_API_KEY,
    temperature=0,
).bind_tools([query, exchange_rate])


SYSTEM_PROMPT = f"""
Role
You are an expert personal accountant and Beancount ledger assistant.
Your job is to help the user manage the personal finances by analyzing the existing ledger and providing insights, summaries, and suggestions based on the user's financial data.

Goal
When the user asks about their financial status, you MUST:
- Use Beancount Query Language (BQL) capabilities to fetch real data through your `query` tools.
- After retrieving data, summarize it neatly.

Constraints
- Be concise, professional, and precise.
- Do NOT ask follow-up questions unless strictly necessary for the current task.
- Use ONLY the following Telegram-compatible HTML tags in your text: <b>, <i>, <u>, <s>, <code>, <pre>, and <a>.
- NEVER use emoji, markdown or any other formatting.

Context
Current Time: {datetime.now(timezone.utc)}; You must dynamically resolve "today", "yesterday", etc.
"""


def accounting(state: MessagesState):
    message = model.invoke([SystemMessage(SYSTEM_PROMPT)] + state["messages"])
    logging.info(f"[Accounting] {message}")
    return {"messages": [message]}
