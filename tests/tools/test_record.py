import logging

from app.tools.record import record


def test_record():
    result = record.invoke(
        {
            "transactions": [
                {
                    "date": "2026-04-30",
                    "flag": "*",
                    "links": [],
                    "narration": "Bought a coffee",
                    "payee": "Coffee Shop",
                    "postings": [
                        {"account": "Expenses:Food:Dining", "units": {"currency": "USD", "number": 5}},
                        {"account": "Assets:Bank:Checking", "units": {"currency": "USD", "number": -5}},
                    ],
                    "tags": [],
                }
            ]
        }
    )

    logging.info(f"Result: {result}")
