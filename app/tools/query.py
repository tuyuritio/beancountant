import logging
import subprocess
from pydantic import BaseModel, Field
from langchain.tools import tool

import app.context as env


class QueryArgs(BaseModel):
    bql: str = Field(
        ...,
        description="""
A BQL (Beancount Query Language) statement to execute against the ledger.

BEANCOUNT QUERY LANGUAGE (BQL) SYNTAX GUIDE

1. BASIC QUERY STRUCTURE
SELECT [DISTINCT] target1 [AS alias1], target2 ...
FROM entry_filter_expression [STATEMENT_OPERATORS]
WHERE posting_filter_expression
GROUP BY column1, column2... (or positional index e.g., 1, 2)
ORDER BY column1 [DESC], column2...
LIMIT number

2. FILTERING LEVELS
BQL uses a two-level filtering system to respect double-entry accounting.

FROM CLAUSE: Filters at the full TRANSACTION level.
Available columns: id (unique hash), date, payee, narration, tags, links, flag, type.

WHERE CLAUSE: Filters at the POSTING level.
Available columns: account, position, balance (cumulative balance of previous rows).

3. OPERATORS
Comparison: =, !=, <, <=, >, >=
Logical: AND, OR, NOT
Set Membership: IN (e.g., 'trip-new-york' IN tags)
Regular Expression Match: ~ (e.g., account ~ 'Expenses:Food:.*')
Note: BQL does not implement three-valued logic for NULL. NULL = NULL yields TRUE.

4. DATA EXTRACTION AND FUNCTIONS
Positions and inventories can be rendered in various formats using extraction functions:
raw(position): Full detail including cost and lot date.
units(position): Number and currency only.
cost(position): Total cost (units x per-unit cost).
weight(position): Balancing amount (useful for price conversions).
value(position): Market value based on last entry.

Simple Functions (apply to single column):
year(date), month(date), day(date)
length(list/set)
parent(account_string)

Aggregate Functions (require GROUP BY if mixed with simple columns):
sum(target): Sums amounts, positions, or numbers.
count(target): Number of postings.
first(target), last(target): First or last seen value.
min(target), max(target): Minimum or maximum value.

5. STATEMENT OPERATORS (Used in FROM clause)
OPEN ON YYYY-MM-DD: Replaces entries before the date with summarization entries (opening balances).
CLOSE [ON YYYY-MM-DD]: Truncates entries after the date. Defaults to one day after the last entry.
CLEAR: Transfers final balances of Income and Expenses to an Equity account (used for balance sheets).

6. METADATA
To query metadata associated with postings, transactions, accounts, or commodities:
meta('key'): Metadata of the current posting.
entry_meta('key'): Metadata of the parent transaction.
any_meta('key'): Metadata of the posting, falling back to the parent transaction if absent.
open_meta(account, 'key'): Metadata of the OPEN directive for the given account.
commodity_meta(currency, 'key'): Metadata of the COMMODITY directive for the given currency.
Note: Metadata functions return a generic object. Use type casting if necessary: str(), int(), decimal(), or date(). Example: SELECT date, str(any_meta('location'))

7. HIGH-LEVEL SHORTCUT COMMANDS
JOURNAL account_regexp [AT function] [FROM entry_filter]
Generates a linear register of entries. Example: JOURNAL "Invest" AT COST.

BALANCES [AT function] [FROM entry_filter]
Generates a table of account balances. Example: BALANCES FROM year = 2014.

PRINT [FROM entry_filter]
Outputs filtered transactions in valid Beancount input text format.

8. DEBUGGING
EXPLAIN query_statement
Prefix any statement with EXPLAIN to print the intermediate AST, compiled representation, and selected columns without executing it.
""",
    )


@tool(args_schema=QueryArgs)
def query(**kwargs) -> str:
    """
    Executes a BQL query against the Beancount ledger and returns the results as a csv.
    """

    args = QueryArgs(**kwargs)

    command = ["bean-query", "-f", "csv", env.MAIN_LEDGER, args.bql]

    logging.info(f"[Tool:query] Executing BQL query: {args.bql}")

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logging.info(
            f"[Tool:query] BQL query executed successfully. Output:\n{result.stdout}"
        )
        return result.stdout

    except subprocess.CalledProcessError as e:
        logging.error(
            f"[Tool:query] BQL query execution failed with error:\n{e.stderr}"
        )
        return e.stderr
