import sys
import os
import pandas as pd
import yfinance as yf
import numpy as np

# Set up paths
backend_path = os.path.dirname(os.path.abspath(__file__))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from analytics.portfolio_returns import fetch_historical_prices, compute_weighted_returns
from analytics.benchmark import fetch_benchmark_returns
from analytics.metrics import calculate_metrics

def main():
    print("--- 1. Testing yfinance download of individual tickers ---")
    tickers = ["INFY.NS", "RELIANCE.NS", "TATAMOTORS.NS"]
    benchmark_symbol = "^NSEI"
    
    # Download using our library function or direct yf
    try:
        prices = fetch_historical_prices(tickers, period="3y")
        print(f"Prices shape: {prices.shape}")
        print(f"Prices columns: {list(prices.columns)}")
        print(f"Prices index timezone: {getattr(prices.index, 'tz', None)}")
    except Exception as e:
        print(f"Error fetching prices: {e}")
        prices = pd.DataFrame()
        
    try:
        benchmark = fetch_benchmark_returns(benchmark_symbol, period="3y")
        print(f"Benchmark returns shape: {benchmark.shape}")
        print(f"Benchmark index timezone: {getattr(benchmark.index, 'tz', None)}")
    except Exception as e:
        print(f"Error fetching benchmark: {e}")
        benchmark = pd.Series(dtype='float64')

    print("\n--- 3. Verifying portfolio return series ---")
    weights = {
        "INFY.NS": 0.33,
        "RELIANCE.NS": 0.33,
        "TATAMOTORS.NS": 0.34
    }
    portfolio_returns = compute_weighted_returns(prices, weights)
    print(f"Portfolio returns type: {type(portfolio_returns)}")
    print(f"Portfolio returns is empty? {portfolio_returns.empty}")
    print(f"Number of rows in portfolio returns: {len(portfolio_returns)}")
    if not portfolio_returns.empty:
        print("First 5 returns:")
        print(portfolio_returns.head(5))
        print("Last 5 returns:")
        print(portfolio_returns.tail(5))

    print("\n--- 4. Verifying benchmark return series ---")
    print(f"Benchmark returns is empty? {benchmark.empty}")
    print(f"Number of rows in benchmark returns: {len(benchmark)}")
    if not benchmark.empty:
        print("First 5 benchmark returns:")
        print(benchmark.head(5))
        print("Last 5 benchmark returns:")
        print(benchmark.tail(5))

    print("\n--- 5. Verifying merged portfolio/benchmark dataframe ---")
    # Emulate the merge from metrics.py
    # Remove tz first to be safe
    p_ret = portfolio_returns.copy()
    b_ret = benchmark.copy()
    for s in [p_ret, b_ret]:
        if s is not None and getattr(s.index, "tz", None) is not None:
            s.index = s.index.tz_localize(None)
            
    merged = pd.concat([p_ret, b_ret], axis=1, join="inner")
    print(f"merged.shape: {merged.shape}")
    print(f"merged is empty? {merged.empty}")
    if not merged.empty:
        print("First 5 merged rows:")
        print(merged.head(5))

if __name__ == "__main__":
    main()
