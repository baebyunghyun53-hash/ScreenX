"""Download the complete Nasdaq Trader US-listed symbol directory."""
from __future__ import annotations

from io import StringIO
import pandas as pd
import requests

NASDAQ_LISTED = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


def _read_directory(url: str) -> pd.DataFrame:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    frame = pd.read_csv(StringIO(response.text), sep="|")
    return frame[~frame.iloc[:, 0].astype(str).str.contains("File Creation Time", na=False)]


def download_us_symbols() -> list[str]:
    """Return tradable US equity symbols understood by Yahoo Finance, limited
    to NYSE and Nasdaq listings.

    Dot class-share symbols are converted to Yahoo's dash convention (BRK.B -> BRK-B).
    """
    nasdaq = _read_directory(NASDAQ_LISTED)
    other = _read_directory(OTHER_LISTED)

    nasdaq_symbols = nasdaq.loc[
        (nasdaq["Test Issue"] == "N") & (nasdaq["ETF"] == "N"), "Symbol"
    ]
    other_symbols = other.loc[
        (other["Test Issue"] == "N") & (other["ETF"] == "N") & (other["Exchange"] == "N"), "ACT Symbol"
    ]

    symbols = pd.concat([nasdaq_symbols, other_symbols]).dropna().astype(str)
    # Keep standard common-equity ticker forms. Warrants/units/preferreds have
    # non-standard suffixes and make fundamentally comparable ranking unreliable.
    symbols = symbols[symbols.str.fullmatch(r"[A-Z]{1,5}(\.[A-Z])?")]
    return sorted({symbol.replace(".", "-") for symbol in symbols})
