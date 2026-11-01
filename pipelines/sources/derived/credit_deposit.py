"""Credit and deposits of scheduled commercial banks, on each fortnightly reporting date
(site calculations from the WSS series):

  credit_deposit_ratio              bank credit / aggregate deposits, %
  credit_deposit_gap                change over a year in credit minus change over a year in
                                    deposits, Rs lakh crore (positive: credit grew by more
                                    rupees than deposits, so banks drew on other funding)
  incremental_credit_deposit_ratio  change in credit / change in deposits over a year, %
"""
from __future__ import annotations

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.store import load_series


def pair(a: str, b: str) -> pd.DataFrame:
    x = load_series(a).set_index("period")["value"].astype(float)
    y = load_series(b).set_index("period")["value"].astype(float)
    both = pd.concat([x, y], axis=1, keys=["a", "b"]).dropna()
    both.index.name = None
    return both


class CreditDeposit(Source):
    name = "derived_credit_deposit"
    derived = True
    series_ids = ("credit_deposit_ratio", "credit_deposit_gap", "incremental_credit_deposit_ratio")

    def fetch(self) -> list[Raw]:
        return []

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        lv = pair("scb_credit", "scb_deposits")
        ch = pair("scb_credit_yoy_change", "scb_deposits_yoy_change")
        return pd.concat([
            pd.DataFrame({"series_id": "credit_deposit_ratio", "period": lv.index,
                          "value": (100 * lv["a"] / lv["b"]).round(2),
                          "note": "site calculation: bank credit / aggregate deposits"}),
            pd.DataFrame({"series_id": "credit_deposit_gap", "period": ch.index,
                          "value": (ch["a"] - ch["b"]).round(3),
                          "note": "site calculation: y/y change in credit minus y/y change in deposits"}),
            pd.DataFrame({"series_id": "incremental_credit_deposit_ratio", "period": ch.index,
                          "value": (100 * ch["a"] / ch["b"]).round(2),
                          "note": "site calculation: y/y change in credit / y/y change in deposits"}),
        ], ignore_index=True)


SOURCE = CreditDeposit()
