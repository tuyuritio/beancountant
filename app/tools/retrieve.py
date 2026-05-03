import logging
from pydantic import BaseModel, Field
from itertools import batched
import time
import sqlite3
import sqlite_vss
from beancount import loader
from beancount.core import data
from langchain.tools import tool
from langchain.embeddings import init_embeddings
from langchain_community.vectorstores import SQLiteVSS

import app.context as env

if not env.EMBEDDING_API_KEY or not env.EMBEDDING_MODEL:
    raise ValueError("[Launch] Lack of necessary environment variables for embedding model.")

VECTOR_DB = "./db/vector.db"

connection = sqlite3.connect(VECTOR_DB, check_same_thread=False)
connection.row_factory = sqlite3.Row
connection.enable_load_extension(True)
sqlite_vss.load(connection)

embeddings = init_embeddings(
    provider=env.EMBEDDING_PROVIDER,
    base_url=env.EMBEDDING_URL,
    model=env.EMBEDDING_MODEL,
    api_key=env.EMBEDDING_API_KEY,
    encoding_format="float",
    check_embedding_ctx_length=False,
)

vector_store = SQLiteVSS(
    embedding=embeddings,
    connection=connection,
    db_file=VECTOR_DB,
    table="beancountant_vectors",
)

DESCRIPTION_TEMPLATE = "{payee} | {narration}"


def initialize_embeddings():
    data_set = []
    entries, errors, options = loader.load_file(env.MAIN_LEDGER)

    for entry in entries:
        if isinstance(entry, data.Transaction):
            payee = entry.payee if entry.payee else ""
            narration = entry.narration if entry.narration else ""
            semantic_description = DESCRIPTION_TEMPLATE.format(payee=payee, narration=narration)

            data_set.append(
                {
                    "text": semantic_description,
                    "metadata": {
                        "flag": entry.flag,
                        "payee": payee if payee else None,
                        "narration": narration if narration else None,
                        "tags": list(entry.tags) if entry.tags else None,
                        "links": list(entry.links) if entry.links else None,
                        "postings": [
                            {
                                "account": posting.account,
                                "units": str(posting.units) if posting.units else None,
                                "cost": str(posting.cost) if posting.cost else None,
                                "price": str(posting.price) if posting.price else None,
                                "flag": posting.flag if posting.flag else None,
                            }
                            for posting in entry.postings
                        ],
                    },
                }
            )

    CHUNK_SIZE = 200
    chunks = list(batched(data_set, CHUNK_SIZE))

    logging.info("[Embedding] Start.")

    SLEEP_INTERVAL = 5  # seconds
    for chunk in chunks:
        texts = [item["text"] for item in chunk]
        metadatas = [item["metadata"] for item in chunk]

        vector_store.add_texts(texts=texts, metadatas=metadatas)

        # Sleep to respect rate limits
        time.sleep(SLEEP_INTERVAL)

    logging.info("[Embedding] Completed.")


class RAGArgs(BaseModel):
    """
    Args for the `retrieve` tool.
    You MUST provide extracting information for EITHER `payee` OR `narration` (or both) to form a valid similarity search query. Do NOT output empty values for both.
    """

    payee: str | None = Field(
        None,
        description="The exact name of the payee in the transaction. Extract verbatim. If absolutely no payee is identifiable in the context, output exactly null.",
    )
    narration: str | None = Field(
        None,
        description="The transaction description, purpose, or note. If present, extract it. If absent, output exactly null.",
    )


@tool(args_schema=RAGArgs)
def retrieve(**kwargs):
    """
    Retrieves historical Beancount entries to align the pending transaction with established Account, Payee, Narration, Tag/Link patterns, and to ensure consistency with the user's financial history and habits.
    This tool provides the Ground Truth for personal accounting logic that cannot be inferred through general knowledge.
    """

    args = RAGArgs(**kwargs)

    similarities = vector_store.similarity_search(
        query=DESCRIPTION_TEMPLATE.format(payee=args.payee or "", narration=args.narration or ""),
        k=5,
    )

    results = []
    for similarity in similarities:
        metadata = similarity.metadata
        results.append(
            {
                "flag": metadata.get("flag"),
                "payee": metadata.get("payee"),
                "narration": metadata.get("narration"),
                "tags": metadata.get("tags"),
                "links": metadata.get("links"),
                "postings": metadata.get("postings"),
            }
        )

    logging.info(f"[Retrieve] Retrieved {len(results)} similar entries: {results}")
    return results
