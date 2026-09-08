from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import time
from typing import Any
import math

from .config import APP_DIR, DEFAULT_OPEN_REFRESH_TIME, FUNDAMENTALS_FILE, FUNDAMENTALS_TTL_DAYS, SNAPSHOT_FILE, UNIVERSE_FILE
from .metrics import METRICS, backfill_low_coverage, display_metrics, normalize_record, score_records
from .market_cap import largest_us_equities
from .storage import load, now_iso, save
from .universe import download_us_symbols
import pandas as pd
import yfinance as yf
import pandas as pd
import pandas_market_calendars as mcal
from pathlib import Path



def _fresh(entry: dict[str, Any]) -> bool:
    try:
        return datetime.fromisoformat(entry["fetched_at"]) > datetime.now(timezone.utc) - timedelta(days=FUNDAMENTALS_TTL_DAYS)
    except (KeyError, TypeError, ValueError):
        return False


def update(args: argparse.Namespace) -> None:

    if getattr(args, "watchlist", False):
        from .watchlist import list_watchlist
        rows = list_watchlist()
        symbols = [title for _id, title, added, watched in rows]
        if not symbols:
            raise SystemExit("Watchlist is empty. Add symbols with: market-rank watchlist --add SYMBOL")
    elif args.symbols:
        symbols = [s.upper() for s in args.symbols.split(",")]
    elif args.market_cap:
        print(f"Getting the {args.market_cap:,} largest US common equities by market capitalization...")
        symbols = largest_us_equities(args.market_cap)
    else:
        stored_universe = load(UNIVERSE_FILE, {})
        if stored_universe.get("symbols") and not args.refresh_universe:
            symbols = stored_universe["symbols"]
        else:
            print("Downloading US-listed symbol directory...")
            symbols = download_us_symbols()
            save(UNIVERSE_FILE, {"fetched_at": now_iso(), "symbols": symbols})

    if args.max_symbols:
        symbols = symbols[:args.max_symbols]

    cache: dict[str, dict[str, Any]] = load(FUNDAMENTALS_FILE, {})
    records: list[dict[str, Any]] = []


    for index, symbol in enumerate(symbols, start=1):
        cached = cache.get(symbol)
        if cached and _fresh(cached):
            records.append(cached["record"])
            continue
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if not info or not info.get("quoteType", "EQUITY") == "EQUITY":
                continue
            info["symbol"] = symbol
            history = ticker.history(period="5d", auto_adjust=False, raise_errors=False)
            record = normalize_record(info, history)
            cache[symbol] = {"fetched_at": now_iso(), "record": record}
            records.append(record)
        except Exception as exc:  # Individual bad tickers must not stop a market run.
            print(f"[{index}/{len(symbols)}] {symbol}: {exc}")
        if index % 25 == 0:
            save(FUNDAMENTALS_FILE, cache)
            print(f"Processed {index}/{len(symbols)} symbols")

    backfill_low_coverage(records)
    ranked = score_records(records)

    if getattr(args, "watchlist", False):
        universe_label = "your watchlist"
    elif args.market_cap:
        universe_label = f"largest {args.market_cap:,} US equities"
    else:
        universe_label = "all US listed equities"

    snapshot = {"generated_at": now_iso(), "universe_size": len(symbols), "ranked_count": len(ranked), "universe": universe_label, "records": ranked[:100]}

    save(FUNDAMENTALS_FILE, cache)
    save(SNAPSHOT_FILE, snapshot)

    display_path = str(SNAPSHOT_FILE).replace(str(Path.home()), "~")
    print(f"Saved {len(snapshot['records'])} ranked companies to {display_path}")

def _fmt(value: Any, percent: bool = False) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "—"
    return f"{value:.1%}" if percent else f"{value:.2f}"


def top(args: argparse.Namespace) -> None:
    snapshot = load(SNAPSHOT_FILE, {})
    records = snapshot.get("records", [])

    if not records:
        raise SystemExit("No snapshot yet. Run: python -m market_rank update")

    limit = None if args.limit.lower() == "all" else int(args.limit)

    print(f"Snapshot: {snapshot.get('generated_at')} | {snapshot.get('universe', 'US equities')} | ranked {snapshot.get('ranked_count')} of {snapshot.get('universe_size')} symbols")
    print("-" * 115)
    print(f"| {'#':>3} | {'Ticker':<7} | {'Company':<28} | {'Sector':<20} | {'Industry':<20} | {'Score':>7} | {'Coverage':>8} |")
    print("-" * 115)


    for rank, row in enumerate(records[:limit], start=1):
        print(f"| {rank:>3} | {row['symbol']:<7} | {row['name'][:28]:<28} | {row['sector'][:20]:<20} | {row['industry'][:20]:<20} | {_fmt(row.get('composite_score')):>7} | {row.get('coverage', 0):>8} |")
    print("-" * 115)


def show(args: argparse.Namespace) -> None:
    records = load(SNAPSHOT_FILE, {}).get("records", [])
    row = next((r for r in records if r["symbol"] == args.symbol.upper()), None)


    if not row:
        raise SystemExit(f"{args.symbol.upper()} is not in the current top 100. Run update or use a ranked symbol.")

    
    print(f"{row['name']} ({row['symbol']}) — {row['sector']} / {row['industry']}")
    print(f"Composite score: {_fmt(row.get('composite_score'))}  |  price: {_fmt(row.get('price'))}  |  analyst target: {_fmt(row.get('analyst_target'))}")
    print("\nMetric                         Raw value       Relative score")


    for label, raw, score in display_metrics(row):
        pct = label in {"Revenue growth", "EPS growth", "Forward ROE"}
        print(f"{label:<29} {_fmt(raw, pct):>11}       {_fmt(score):>8}")


    print("DCF scenarios (per share): bear {}, base {}, bull {}; base/current = {}".format(_fmt(row.get("dcf_bear")), _fmt(row.get("dcf_base")), _fmt(row.get("dcf_bull")), _fmt(row.get("dcf_upside"))))
    print(f"Analyst target/current: {_fmt(row.get('analyst_upside'))}")
    print("Scores > 1 are better than the sector median. For valuation/debt metrics, lower raw values score higher.")


def run(args: argparse.Namespace) -> None:


    nyse = mcal.get_calendar("NYSE")
    last_date = None

    
    print(f"Watching for NYSE market days; refresh time is {args.at} America/New_York. Ctrl-C to stop.")


    while True:
        now = pd.Timestamp.now(tz="America/New_York")
        day = now.strftime("%Y-%m-%d")
        schedule = nyse.schedule(start_date=day, end_date=day)
        if not schedule.empty and now.strftime("%H:%M") >= args.at and last_date != day:
            update(args)
            last_date = day
        time.sleep(30)


def watchlist(args: argparse.Namespace) -> None:
    from .watchlist import add_to_watchlist, delete_from_watchlist, list_watchlist

    if args.add:
        symbol = args.add.upper()
        add_to_watchlist(symbol)
        print(f"Added {symbol} to watchlist.")
    elif args.delete:
        symbol = args.delete.upper()
        delete_from_watchlist(symbol)
        print(f"Removed {symbol} from watchlist.")
    elif args.list:
        rows = list_watchlist()
        if not rows:
            print("Watchlist is empty.")
        else:
            print(f"{'Ticker':<10} {'Added':<20} {'Watched'}")
            for _id, title, added, watched in rows:
                print(f"{title:<10} {added:<20} {'yes' if watched else 'no'}")
    elif args.top:
        rows = list_watchlist()
        if not rows:
            print("Watchlist is empty.")
            return

        snapshot = load(SNAPSHOT_FILE, {})
        records = {r["symbol"]: r for r in snapshot.get("records", [])}

        if not records:
            raise SystemExit("No snapshot yet. Run: python -m market_rank update")
        
        print("-" * 115)
        print(f"| {'#':>3} | {'Ticker':<7} | {'Company':<28} | {'Sector':<20} | {'Industry':<20} | {'Score':>7} | {'Coverage':>8} |")
        print("-" * 115)


        missing = []
        rank = 0
        for _id, title, added, watched in rows:
            row = records.get(title)
            if row is None:
                missing.append(title)
                continue
            rank += 1
            print(f"| {rank:>3} | {row['symbol']:<7} | {row['name'][:28]:<28} | {row['sector'][:20]:<20} | {row['industry'][:20]:<20} | {_fmt(row.get('composite_score')):>7} | {row.get('coverage', 0):>8} |")
        print("-" * 115)


        if missing:
            print(f"\nNot in current snapshot (outside top 100 or not yet ranked): {', '.join(missing)}")
    else:
        print("No action specified. Use --add TICKER, --delete TICKER, --list, or --top.")

def correlate(args: argparse.Namespace) -> None:

    if args.symbols:
        symbols = [s.upper() for s in args.symbols.split(",")]
    elif args.watchlist:
        from .watchlist import list_watchlist
        rows = list_watchlist()
        symbols = [title for _id, title, added, watched in rows]
        if not symbols:
            raise SystemExit("Watchlist is empty. Add symbols with: market-rank watchlist --add SYMBOL")
    else:
        snapshot = load(SNAPSHOT_FILE, {})
        records = snapshot.get("records", [])
        if not records:
            raise SystemExit("No snapshot yet, and no --symbols/--watchlist given. Run: market-rank update")
        symbols = [r["symbol"] for r in records[:int(args.limit)]]

    if len(symbols) < 2:
        raise SystemExit("Need at least 2 symbols to compute a correlation matrix.")

    print(f"Fetching {args.period} of daily price history for {len(symbols)} symbols...")
    data = yf.download(symbols, period=args.period, auto_adjust=False, progress=False)["Close"]

    if isinstance(data, pd.Series):  # yfinance collapses to a Series when only one column survives
        raise SystemExit("Not enough overlapping price data to compute a correlation matrix.")

    returns = data.pct_change().dropna(how="all")
    missing = [s for s in symbols if s not in returns.columns or returns[s].dropna().empty]
    if missing:
        print(f"No usable price data for: {', '.join(missing)} (skipped)")
    returns = returns.drop(columns=missing, errors="ignore")

    if returns.shape[1] < 2:
        raise SystemExit("Not enough symbols with valid price data to compute a correlation matrix.")

    corr = returns.corr()
    _print_correlation_matrix(corr)


def _print_correlation_matrix(corr) -> None:
    symbols = list(corr.columns)
    col_width = max(7, max(len(s) for s in symbols) + 1)
    header = " " * col_width + "".join(f"{s:>{col_width}}" for s in symbols)
    print(header)
    print("-" * len(header))
    for row_symbol in symbols:
        row = f"{row_symbol:<{col_width}}"
        for col_symbol in symbols:
            row += f"{corr.loc[row_symbol, col_symbol]:>{col_width}.2f}"
        print(row)


def main() -> None:
    parser = argparse.ArgumentParser(prog="market-rank", description="Rank US equities using sector-relative fundamentals.")
    sub = parser.add_subparsers(required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--symbols", help="Comma-separated tickers (useful for a quick or focused run).")
    common.add_argument("--max-symbols", type=int, help="Limit universe size (testing only).")
    common.add_argument("--market-cap", type=int, choices=(100, 1000), help="Rank only the largest 100 or 1,000 US common equities by live market cap.")
    common.add_argument("--refresh-universe", action="store_true", help="Redownload listed symbols.")
    common.add_argument("--watchlist", action="store_true", help="Update only your watchlist symbols.")

    update_parser = sub.add_parser("update", parents=[common]); update_parser.set_defaults(func=update)
    top_parser = sub.add_parser("top"); top_parser.add_argument("--limit", default="100", help="Number of rows to show, or 'all' to show everything."); top_parser.set_defaults(func=top)
    show_parser = sub.add_parser("show"); show_parser.add_argument("symbol"); show_parser.set_defaults(func=show)
    run_parser = sub.add_parser("run", parents=[common]); run_parser.add_argument("--at", default=DEFAULT_OPEN_REFRESH_TIME, help="HH:MM ET, default 09:40"); run_parser.set_defaults(func=run)

    watchlist_parser = sub.add_parser("watchlist")
    watchlist_parser.add_argument("--add", help="Add a ticker to your watchlist.")
    watchlist_parser.add_argument("--delete", help="Remove a ticker from your watchlist.")
    watchlist_parser.add_argument("--list", action="store_true", help="Show your current watchlist.")
    watchlist_parser.add_argument("--top", action="store_true", help="Show your watchlist's current scores from the latest snapshot.")
    watchlist_parser.set_defaults(func=watchlist)

    correlate_parser = sub.add_parser("correlate", help="Show a correlation matrix of daily returns.")
    correlate_parser.add_argument("--symbols", help="Comma-separated tickers, e.g. AAPL,MSFT,NVDA.")
    correlate_parser.add_argument("--watchlist", action="store_true", help="Use your watchlist symbols.")
    correlate_parser.add_argument("--limit", default="10", help="If neither --symbols nor --watchlist given, use the top N from the current snapshot.")
    correlate_parser.add_argument("--period", default="3y", help="History window: 6mo, 1y, 3y, 5y, etc.")
    correlate_parser.set_defaults(func=correlate)

    args = parser.parse_args()
    args.func(args)
