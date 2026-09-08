# Market Rank CLI

A small Python CLI that refreshes a US-listed equity ranking shortly after the US market opens, stores the result locally, and displays the top 100 companies with sector-relative valuation, financial-health, and growth metrics.

## Demo

![market-rank update demo](docs/media/demo.gif)
![market-rank top demo](docs/media/demo-top.gif)

*Recorded with [VHS](https://github.com/charmbracelet/vhs) by Charm.*

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Optional: install the `market-rank` command as well.
pip install -e .
```

## Use

```bash
# Download the listed US equity universe and calculate a current snapshot.
market-rank update
market-rank update --watchlist # Rank only your watchlist symbols instead of the full universe.
                                # WARNING: this overwrites your current snapshot.

# Faster focused universes: the largest US companies by live market cap.
market-rank update --market-cap 100
market-rank update --market-cap 1000

# Print the current top 100 (or a shorter list).
market-rank top --limit 25
market-rank top --limit all # Displays everything.

# Inspect one company and its sector-relative scores.
market-rank show MSFT

# Show a correlation matrix of daily returns between stocks.
market-rank correlate --symbols AAPL,MSFT,NVDA,GOOGL,AMZN
market-rank correlate --watchlist --period 1y
market-rank correlate --limit 15 # Top 15 from the current snapshot (default when no --symbols/--watchlist given).

# Keep the process alive; refreshes once on each NYSE trading day at 09:40 ET.
market-rank run

# CRUD watchlist
market-rank watchlist --add symbol
market-rank watchlist --delete symbol
market-rank watchlist --list

# Show your watchlist's scores from the current snapshot.
# Symbols not present in the snapshot (e.g. outside the top 100, or you haven't
# run `update` since adding them) are listed separately instead of causing an error.
market-rank watchlist --top
```

`update` is intentionally explicit: the entire US-listed universe is large and the upstream quote/fundamental endpoints can be slow or rate-limited. The CLI caches company fundamentals for 7 days and uses the most recent daily history for price-based data. On a typical connection, the first full run may take a while.

For an unattended process, run `market-rank run` under your usual service manager (launchd/systemd) or invoke `market-rank update` from a scheduler at 09:40 America/New_York on trading days.

## How scores work

For every metric, the raw comparison is against the **median valid value in the company’s sector**. A score of `1.00` means the sector median. Values above one are better:

- Growth, ROE, asset turnover, cash flow and analyst upside use `company / sector median`.
- PE, forward PE, EV/EBITDA, debt-to-equity and historic PE use `sector median / company` because lower is better.

Negative or zero values are shown as unavailable for ratio-based comparisons where they would be misleading. The composite rank is a winsorized average of available relative scores, plus DCF and analyst-upside contributions; it is a screening signal, not investment advice.

### Low-coverage handling

Some companies have incomplete fundamental data. When a stock has fewer than 7 valid observations for a metric within its sector, ScreenX falls back to the corresponding industry-level average where available. Missing metrics are therefore handled without allowing sparse data to disproportionately affect the composite score.

For example, a low-coverage stock might produce a snapshot like:

| Metric           |   Raw Value | Relative Score |
| ---------------- | ----------: | -------------: |
| P/E              |        1.86 |           7.38 |
| Historic P/E     |        1.86 |           7.38 |
| Revenue growth   |       30.4% |           1.81 |
| Earnings growth  |       46.9% |           1.38 |
| Return on equity |       17.8% |           1.59 |
| Forward P/E      | Unavailable |              — |
| Debt-to-equity   | Unavailable |              — |
| Free cash flow   | Unavailable |              — |
| DCF upside       | Unavailable |              — |
| Analyst upside   | Unavailable |              — |

The `coverage` field records how many valid sector observations were available for the stock. Low coverage does not automatically exclude a company, but the resulting score should be interpreted with greater caution.


## Correlation matrix

`market-rank correlate` computes the Pearson correlation between daily returns for a set of stocks and prints it as a matrix, to help spot when a watchlist or top-ranked set is more concentrated (highly correlated) than it looks from scores alone.

```bash
market-rank correlate --symbols AAPL,MSFT,NVDA,GOOGL,AMZN
market-rank correlate --watchlist --period 1y
market-rank correlate --limit 15
```

- Symbols are resolved in this order: explicit `--symbols`, then `--watchlist`, then the top N symbols (`--limit`, default 10) from the current snapshot.
- `--period` sets the daily-price lookback window passed to yfinance (default `3y`; also accepts values like `6mo`, `1y`, `5y`).
- Daily price history is pulled in a single batched request per run — this isn't cached the way fundamentals are, since correlation is sensitive to the lookback window and changes day to day.
- Symbols with no usable price data for the requested period (e.g. recent IPOs shorter than `--period`) are dropped from the matrix and reported separately rather than causing an error.
- Values range from 1.00 (identical daily movement — always the diagonal) to -1.00 (inverse movement); values near 0 indicate largely unrelated movement.

## Data notes

- The stock universe comes from Nasdaq Trader's public `nasdaqlisted.txt` and `otherlisted.txt` directories, filtered to common equity-like listings. ETFs, funds, test issues and non-US symbol formats are excluded.
- Fundamentals, analyst targets, earnings/revenue growth and daily prices are fetched through `yfinance`/Yahoo Finance. Coverage varies by company; missing metrics do not count against a company's composite.
- DCF scenarios use a deliberately transparent five-year FCFE-style projection based on reported free cash flow, revenue/EPS growth forecasts, beta-derived discounting and a Monte Carlo terminal-growth/discount-rate simulation. They are estimates, not analyst models.
- A snapshot always reflects whichever universe was last requested — the full listed universe, a market-cap-limited set, or (with `update --watchlist`) just your watchlist symbols. `market-rank top` and `market-rank watchlist --top` both read from this same snapshot, so scores are only ever comparable within the universe that generated the current snapshot, not across runs made with different `update` options.