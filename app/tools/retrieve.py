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


def initialize_embeddings():
    data_set = []
    entries, errors, options = loader.load_file(env.MAIN_LEDGER)

    for entry in entries:
        if isinstance(entry, data.Transaction):
            payee = entry.payee if entry.payee else ""
            narration = entry.narration if entry.narration else ""
            accounts = [p.account.replace(":", " ") for p in entry.postings]
            semantic_description = f"{payee} | {narration} | {', '.join(accounts)}"

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
    text: str = Field(
        ...,
        description="The input text to retrieve relevant transactions for.",
    )
    k: int = Field(
        5,
        description="The number of relevant transactions to retrieve.",
    )


@tool(args_schema=RAGArgs)
def retrieve(**kwargs):
    """
    Retrieves relevant transactions from the Beancount ledger based on the input text.
    """

    args = RAGArgs(**kwargs)

    similarities = vector_store.similarity_search(args.text, k=5)

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

    return results
