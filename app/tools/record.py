from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, Field
import datetime
from beancount.core.data import Transaction as BeanTransaction, Posting as BeanPosting
from beancount.core.amount import Amount as BeanAmount
from beancount.core.position import Cost as BeanCost, CostSpec as BeanCostSpec
from beancount.parser import printer
from langgraph.types import interrupt
from langchain.tools import tool

import app.context as env
from app.tools.retrieve import vector_store, DESCRIPTION_TEMPLATE


class Flag(StrEnum):
    CLEARED = "*"
    PENDING = "!"


Meta = dict[str, object]


class Amount(BaseModel):
    """An 'Amount' represents a number of a particular unit of something."""

    number: Decimal = Field(..., description="The numeric value of the amount.")
    currency: str = Field(..., description="The currency symbol of the amount.")

    def beanize(self) -> BeanAmount:
        return BeanAmount(self.number, self.currency)


class Cost(BaseModel):
    """A variant of Amount that also includes a date and a label."""

    number: Decimal = Field(..., description="The per-unit cost.")
    currency: str = Field(..., description="The cost currency.")
    date: datetime.date = Field(..., description="The date that the lot was created at")
    label: str | None = Field(None, description="The label of this lot.")

    def beanize(self) -> BeanCost:
        return BeanCost(self.number, self.currency, self.date, self.label)


class CostSpec(BaseModel):
    """
    A stand-in for an "incomplete" Cost, that is, a container all the data that
    was provided by the user in the input in order to resolve this lot to a
    particular lot and produce an instance of Cost. Any of the fields of this
    object may be left unspecified, in which case they take the special value
    "NA" (see below), if the field was absent from the input.
    """

    number_per: Decimal | None = Field(
        None,
        description="The cost/price per unit",
    )
    number_total: Decimal | None = Field(
        None,
        description="The total cost/price",
    )
    currency: str | None = Field(
        None,
        description="The commodity of the amount",
    )
    date: datetime.date | None = Field(
        None,
        description="The date that the lot was created at.",
    )
    label: str | None = Field(
        None,
        description="The label of this lot.",
    )
    merge: bool = Field(
        False,
        description="True if this specification calls for averaging the units of this lot's currency.",
    )

    def beanize(self) -> BeanCostSpec:
        return BeanCostSpec(
            self.number_per,
            self.number_total,
            self.currency,
            self.date,
            self.label,
            self.merge,
        )


class Posting(BaseModel):
    account: str = Field(..., description="The account that is modified by this posting.")
    units: Amount | None = Field(
        None,
        description="The amount and currency of the posting, formatted as '<amount> <currency>'. For example: '10 USD' or '-5 EUR'.",
    )
    cost: Cost | CostSpec | None = Field(
        None,
        description="The cost of the posting, if applicable, formatted as '<amount> <currency>'. For example: '10 USD' or '-5 EUR'. This field is optional and can be left out if there is no cost associated with the posting.",
    )
    price: Amount | None = Field(
        None,
        description="The price of the posting, if applicable, formatted as '<amount> <currency>'. For example: '10 USD' or '-5 EUR'. This field is optional and can be left out if there is no price associated with the posting.",
    )
    flag: Flag | None = Field(
        None,
        description="The flag for the posting, either '*' for cleared or '!' for pending.",
    )
    meta: Meta | None = Field(
        None,
        description="A dict of strings to values, the metadata that was attached specifically to that posting.",
    )


class Transaction(BaseModel):
    date: datetime.date = Field(..., description="The date of the transaction in 'YYYY-MM-DD' format.")
    flag: Flag = Field(
        Flag.PENDING,
        description="The transaction flag, either '*' for cleared or '!' for pending.",
    )
    payee: str | None = Field(None, description="The payee of the transaction.")
    narration: str | None = Field(None, description="The narration/description of the transaction.")
    tags: list[str] = Field(
        ...,
        description="A set of tags to associate with the transaction. Tags should be provided as a comma-separated string (e.g., 'tag1,tag2,tag3').",
    )
    links: list[str] = Field(
        ...,
        description="A set of links to associate with the transaction. Links should be provided as a comma-separated string (e.g., 'link1,link2,link3').",
    )
    postings: list[Posting] = Field(
        ...,
        description="A list of postings for the transaction.",
    )
    meta: Meta | None = Field(
        None,
        description="A dict of strings to values, the metadata that was attached to the transaction as a whole.",
    )


class RecordArgs(BaseModel):
    transactions: list[Transaction] = Field(..., description="A list of transactions to be recorded.")


@tool(args_schema=RecordArgs)
def record(**kwargs):
    """
    Adds a transaction to the Beancount ledger based on the provided arguments.
    """

    args = RecordArgs(**kwargs)

    transactions = [
        BeanTransaction(
            meta=transaction.meta or {},
            date=transaction.date,
            flag=transaction.flag.value,
            payee=transaction.payee or "",
            narration=transaction.narration or "",
            tags=frozenset(transaction.tags),
            links=frozenset(transaction.links),
            postings=[
                BeanPosting(
                    account=posting.account,
                    units=posting.units.beanize() if posting.units else None,
                    cost=posting.cost.beanize() if posting.cost else None,
                    price=posting.price.beanize() if posting.price else None,
                    flag=posting.flag.value if posting.flag else None,
                    meta=posting.meta or {},
                )
                for posting in transaction.postings
            ],
        )
        for transaction in args.transactions
    ]

    entries = "\n".join(printer.format_entry(transaction) for transaction in transactions)

    response = interrupt({"text": entries, "options": [["❌", "✔️"]]})

    match response[0].get("text"):
        case "✔️":
            with open(env.INBOX_LEDGER, "a", encoding="utf-8") as file:
                file.write(entries)
                file.write("\n")

            data_set = []
            for entry in args.transactions:
                data_set.append(
                    {
                        "text": DESCRIPTION_TEMPLATE.format(payee=entry.payee or "", narration=entry.narration or ""),
                        "metadata": {
                            "flag": entry.flag.value,
                            "payee": entry.payee,
                            "narration": entry.narration,
                            "tags": entry.tags if entry.tags else None,
                            "links": entry.links if entry.links else None,
                            "postings": [
                                {
                                    "account": posting.account,
                                    "units": str(posting.units.beanize()) if posting.units else None,
                                    "cost": str(posting.cost.beanize()) if posting.cost else None,
                                    "price": str(posting.price.beanize()) if posting.price else None,
                                    "flag": posting.flag.value if posting.flag else None,
                                }
                                for posting in entry.postings
                            ],
                        },
                    }
                )

            texts = [item["text"] for item in data_set]
            metadatas = [item["metadata"] for item in data_set]
            vector_store.add_texts(texts=texts, metadatas=metadatas)

            return True

        case "❌":
            return False

        case _:
            return response
