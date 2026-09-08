"""A focused US equity universe ranked by live market capitalization."""
from __future__ import annotations

NYSE_NASDAQ_EXCHANGES = {"NMS", "NGM", "NCM", "NYQ"}


def largest_us_equities(limit: int) -> list[str]:
    """Fetch the largest US common equities from Yahoo's screener in 250-row pages,
    restricted to NYSE and Nasdaq listings."""
    import yfinance as yf

    query = yf.EquityQuery("and", [
        yf.EquityQuery("eq", ["region", "us"]),
        yf.EquityQuery("gt", ["intradaymarketcap", 0]),
    ])

    symbols: list[str] = []
    for offset in range(0, limit + 250, 250):
        response = yf.screen(query, offset=offset, size=250, sortField="intradaymarketcap", sortAsc=False)
        quotes = response.get("quotes", [])
        if not quotes:
            break

        for quote in quotes:
            if (
                quote.get("quoteType") == "EQUITY"
                and quote.get("symbol")
                and quote.get("exchange") in NYSE_NASDAQ_EXCHANGES
            ):
                symbols.append(str(quote["symbol"]))
                if len(symbols) == limit:
                    return symbols

        if len(quotes) < 250:
            break

    if len(symbols) < limit:
        raise RuntimeError(f"Yahoo screener returned only {len(symbols)} NYSE/Nasdaq common equities; needed {limit}.")
    return symbols