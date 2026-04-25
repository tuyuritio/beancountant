import logging
from pydantic import BaseModel, Field
import json
import httpx
from langchain.tools import tool


class ExchangeRateArgs(BaseModel):
    base: str = Field(
        ..., description="The base 3-letter ISO currency code (e.g., 'USD')."
    )
    quotes: str | None = Field(
        None,
        description="Comma-separated target 3-letter ISO currency codes (e.g., 'EUR,GBP').",
    )
    date: str | None = Field(
        None,
        description="The date for the exchange rate in 'YYYY-MM-DD' format. If not provided, the latest rate will be used.",
    )


@tool(args_schema=ExchangeRateArgs)
def exchange_rate(**kwargs):
    """
    Fetches exchange rates based on the provided arguments.
    """

    args = ExchangeRateArgs(**kwargs)

    url = "https://api.frankfurter.dev/v2/rates"

    params = {"base": args.base}
    if args.quotes:
        params["quotes"] = args.quotes

    if args.date:
        params["date"] = args.date

    logging.info(
        f"[Tool:exchange_rate] Fetching exchange rates with parameters: {params}"
    )

    try:
        response = httpx.get(url, params=params)
        response.raise_for_status()

        result = json.dumps(response.json(), ensure_ascii=False)

        logging.info(
            f"[Tool:exchange_rate] Exchange rates fetched successfully. Response:\n{result}"
        )

        return result

    except httpx.HTTPError as e:
        logging.error(f"[Tool:exchange_rate] HTTP error occurred: {e}")
        return f"Error fetching exchange rate: {e}"
