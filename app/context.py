import os
from typing import NotRequired
from dotenv import load_dotenv
from langgraph.graph import MessagesState

load_dotenv()

ENV = os.getenv("ENV", "prod").lower()

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "8443"))
BOT_TOKEN = os.getenv("BOT_TOKEN")
SECRET_TOKEN = os.getenv("SECRET_TOKEN")
ALLOWED_USERS = [int(uid.strip()) for uid in os.getenv("ALLOWED_USERS", "").split(",") if uid.strip()]

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_URL = os.getenv("LLM_URL")
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_API_KEY = os.getenv("LLM_API_KEY")

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")
EMBEDDING_URL = os.getenv("EMBEDDING_URL")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")

MAIN_LEDGER = os.getenv("MAIN_LEDGER", "./ledger/main.bean")
INDEX_LEDGER = os.getenv("INDEX_LEDGER", "./ledger/main.bean")


class State(MessagesState):
    intent: NotRequired[str | None]
