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
    account: str = Field(
        ..., description="The account that is modified by this posting."
    )
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
    date: datetime.date = Field(
        ..., description="The date of the transaction in 'YYYY-MM-DD' format."
    )
    flag: Flag = Field(
        Flag.PENDING,
        description="The transaction flag, either '*' for cleared or '!' for pending.",
    )
    payee: str | None = Field(None, description="The payee of the transaction.")
    narration: str | None = Field(
        None, description="The narration/description of the transaction."
    )
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
    transactions: list[Transaction] = Field(
        ..., description="A list of transactions to be recorded."
    )


def to_bean_cost(value: Cost | CostSpec | None) -> BeanCost | BeanCostSpec | None:
    if value is None:
        return None
    if isinstance(value, Cost):
        return BeanCost(value.number, value.currency, value.date, value.label)
    return BeanCostSpec(
        value.number_per,
        value.number_total,
        value.currency,
        value.date,
        value.label,
        value.merge,
    )


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

    entries = "\n".join(
        printer.format_entry(transaction) for transaction in transactions
    )

    response = interrupt({"text": entries, "options": [["❌", "✔️"]]})

    match response:
        case "✔️":
            with open(env.INDEX_LEDGER, "a", encoding="utf-8") as file:
                file.write(entries)
                file.write("\n")

            return True

        case "❌":
            return False

        case _:
            return response
