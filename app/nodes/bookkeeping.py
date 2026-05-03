import logging
from pydantic import BaseModel, Field
from datetime import datetime
from zoneinfo import ZoneInfo
from langchain.messages import SystemMessage
from langchain.chat_models import init_chat_model

import app.context as context
from app.tools import query, retrieve, record


class enquiring_message(BaseModel):
    """
    Use this tool STRICTLY when the user's input lacks necessary details to record a complete bookkeeping transaction.
    If any required information is missing or ambiguous, you MUST invoke this tool to ask the user for clarification.
    Do NOT ask the user for missing information in your regular text response; you MUST use this tool.
    """

    text: str = Field(
        ...,
        description="The message text to send to the user, prompting them for information or confirmation.",
    )
    options: list[str] | None = Field(
        None,
        description="A list of predefined single-choice option buttons to present to the user. Populate this parameter ONLY when providing choices would make it easier, faster, or more intuitive for the user to answer.",
    )


model = init_chat_model(
    model_provider=context.LLM_PROVIDER,
    model=context.LLM_MODEL,
    temperature=0,
    api_key=context.LLM_API_KEY,
    base_url=context.LLM_URL,
).bind_tools([enquiring_message, retrieve, record])


SYSTEM_PROMPT = """
Role
You are an expert personal accountant assistant for bookkeeping.
Your job is to help the user manage the personal finances by accurately adding new transaction records.

Goal
When the user states they spent/earned money, you MUST:
- Determine the correct accounts based the user's input.
- If the expense category (account) itself fully describes the transaction, leave the `narration` empty (an empty string).
- If essential information is missing and cannot be deduced, you MUST ask the user for the missing information using the `enquire` tool. This is MANDATORY to ensure accurate bookkeeping.
- Once all necessary transaction details are completely gathered, you MUST invoke the `retrieve` tool to query historical transaction patterns based on the extracted details.
- Finally, you MUST use the retrieved historical transactions as Ground Truth to invoke the `record` tool to add the new transaction record with the highest accuracy and consistency with the user's financial history and habits.
- If the user attempts to cancel the recording process, you MUST respect that and not record anything, just return a cancellation message.

Constraints
- Be concise, professional, and precise.
- Use ONLY the following Telegram-compatible HTML tags in your text: <b>, <i>, <u>, <s>, <code>, <pre>, and <a>.
- NEVER use emoji, markdown or any other formatting.

Context
Current Time: {current_time}; You must dynamically resolve "today", "yesterday", etc.

Accounts:
{accounts}
"""


def bookkeeping(state: context.State):
    prompt = SYSTEM_PROMPT.format(
        current_time=datetime.now(ZoneInfo(context.TIMEZONE)),
        accounts=query.invoke(
            {
                "bql": "SELECT DISTINCT account, open_meta(account, 'alias') as alias FROM accounts WHERE account ~ 'Expenses|Income|Assets|Liabilities'"
            }
        ),
    )

    message = model.invoke([SystemMessage(prompt)] + state["messages"])

    logging.info(f"[Bookkeeping] {message}")
    return {"messages": [message]}
