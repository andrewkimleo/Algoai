# AlgoAI Institutional-Grade Dashboard & Analytics Walkthrough

We have successfully implemented the production-grade Historical Portfolio Analytics system for AlgoAI. All metrics, curves, and risk calculations are derived dynamically from real-market historical price series (Yahoo Finance API) and actual session-based portfolio allocations.

---

## 🛠️ Summary of Changes Made

### 1. Backend Portfolio Analytics Engine (`backend/analytics/`)
We built a modular, production-ready performance calculations package:
- **`portfolio_returns.py`**: Downloads stockclose prices from `yfinance`, calculates daily returns, and aggregates weighted portfolio returns.
- **`equity_curve.py`**: Computes daily compounded equity growth from a base capital of ₹100,000.
- **`drawdown.py`**: Computes daily drawdowns relative to the running peak portfolio value.
- **`benchmark.py`**: Downloads close prices for the `^NSEI` (Nifty 50 Index) benchmark and aligns the index returns chronologically.
- **`metrics.py`**: Calculates portfolio metrics: CAGR, Sharpe Ratio, Sortino Ratio, Volatility, Max Drawdown, Calmar Ratio, CAGR, Alpha, Beta, and Information Ratio.

### 2. Individual Asset Caching Layer
To prevent yfinance API rate-limiting and accelerate data delivery, we refactored `fetch_historical_prices` inside `portfolio_returns.py` to:
- Normalize ticker strings (e.g. converting `RELIANCE` to `RELIANCE.NS`).
- Retrieve and cache ticker historical series **individually** using the file-based `cache_manager` (expiring in 24 hours).
- Avoid downloading identical historical data across different sessions or agent backtests.

### 3. Future-Ready Agent-Level Design
Exposed specialized strategy wrappers in `backend/analytics/__init__.py` to support future agent-level backtesting:
- `compute_portfolio_analytics` (Aggregated portfolio allocations)
- `compute_momentum_agent_analytics` (Momentum analyst proposed sub-portfolio)
- `compute_mean_reversion_agent_analytics` (Mean Reversion analyst sub-portfolio)
- `compute_sentiment_agent_analytics` (Senti-Quant analyst sub-portfolio)

### 4. Background Cache Warming & Non-Blocking Pipeline
- Orchestrated a **non-blocking background task** (`pre_fetch_historical_data`) in `backend/main.py` that begins warming the yfinance cache for selected tickers and benchmark index *as soon as* a session is initialized via `/api/start-session`.
- Ensures the debate pipeline is highly responsive, and the subsequent analytics fetch completes instantly when the final verdict is reached.
- Cleanly returns 404 / 400 JSON responses if a session is not found or capital decisions are not finalized yet.

### 5. Frontend Dynamic Analytics Component (`frontend/src/App.jsx`)
- Replaced the visual stubs in `PortfolioAnalyticsSection` with the complete Recharts implementation:
  - **LineChart**: Dynamically plots the compounded growth of the **AlgoAI Portfolio** vs **NIFTY 50 Index** from a ₹100k starting capital.
  - **AreaChart**: Visualizes historical drawdowns with red gradients and custom tooltips.
  - **Metadata Badges Header**: Displays lookup telemetry (`lookback_period`, `benchmark_symbol`, `asset_count`, `calculation_timestamp`).
  - **Interactive Tabs**: Allows users to toggle between the Equity Curve and Drawdown Track.
  - **Metrics Dashboard Grid**: Dynamically renders 9 annualized return/risk metrics using `AnimatedNumber` count-ups.
  - **Outperformance Banner**: Computes excess return and displays a styled success/failure badge.
- Added resets in `handleReset` to clear active analytics on session restarts.
- Implemented robust conditional views for loading states and specific empty states (e.g., `no completed portfolio`, `market data fetch failure`, `insufficient historical data`).

---

## 🔍 Frontend Blank Page / Crash Debugging & Resolution (June 2026)

### 1. Root Cause Analysis
- **The Issue**: When scrolling down to the Portfolio Analytics section, the page suddenly became blank or crashed.
- **Trigger**: The crash was caused by the `AnimatedNumber` component. The component uses an `IntersectionObserver` to trigger its animation *only* when it enters the viewport (when the user scrolls down to Row 4).
- **The Bug**: In the initial load or if calculation fails, some performance values in `metrics` (like Sharpe ratio, CAGR, max drawdown) are `null`, `undefined`, or `NaN`. When `hasAnimated` transitioned to `true`, the `useEffect` animation block tried to parse this invalid value. `parseFloat(NaN)` or `parseFloat(undefined)` produced `NaN`. The step function then called `setCount(value)` with a non-numeric value. During the subsequent render, the component executed `count.toFixed()`. Calling `toFixed` on a non-number (like `undefined`, `null`, or `NaN`) throws a runtime `TypeError` in JavaScript.
- **The Crash**: Because React has no internal safety boundaries for component rendering, an unhandled exception inside `AnimatedNumber` unmounted the entire React virtual DOM, crashing the browser tab and rendering a blank screen.

### 2. Implemented Fixes & Protections
We applied a multi-layered defensive strategy to make the application fully crash-proof:
1. **Numeric Validation in `AnimatedNumber`**: Refactored `AnimatedNumber` to inspect the value type and verify it is a valid finite float. If not, it skips the `requestAnimationFrame` thread loop and renders a clean fallback string (`"--"`) directly without ever invoking `.toFixed()`.
2. **React Error Boundary**: Implemented a class-based `ErrorBoundary` wrapped around `PortfolioAnalyticsSection`. Any unexpected rendering exception inside the analytics panel will be isolated, rendering a professional localized error card with stack traces while keeping the rest of the application fully operational.
3. **Data Length Guards on Recharts**: Audited and secured `LineChart`, `AreaChart`, and `PieChart` components to check dataset lengths. If any series is null or empty, they render a clean placeholder description instead of attempting to chart empty bounds.
4. **De-duplicated State Streaming (useMemo & useRef)**:
   - Extracted `finalVerdictMessage` using `useMemo` so it computes only when messages actually change, and passed it down to decouple the analytics panel from standard message stream ticks.
   - Integrated a ref latch `fetchedVerdictSessionRef` inside the analytics fetch `useEffect` to ensure the endpoint `/api/portfolio/analytics` is fetched **exactly once** per session, preventing duplicate requests and state storms.

---

## 📈 NaN Metrics & Unaligned Index Date Resolution

### 1. Root Cause Analysis
- **The Bug**: When requesting historical performance, the calculations completed with `200 OK` but returned dictionaries containing `NaN` and `null` values, leaving the charts blank and rendering metrics as `NaN`.
- **Mismatched Timezones**: The Yahoo Finance downloader (`yf.download`) returned DatetimeIndex arrays that were timezone-aware (e.g. standard local exchange time `Asia/Kolkata` or `UTC`) for some indices (like NIFTY index `^NSEI`), but timezone-naive (`None`) for single equities.
- **Empty inner join**: During aligned calculations:
  ```python
  aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1, join="inner")
  ```
  Pandas was unable to align timezone-aware and timezone-naive timestamps on an inner join, causing the joined returns DataFrame to be completely **empty** (0 rows). Consequently, covariance, beta, alpha, standard deviation, and Sortino denominator equations failed or evaluated to division-by-zero or `NaN`.
- **Reindexing NaNs**: Reindexing timezone-naive portfolio index values against the timezone-aware benchmark returns:
  ```python
  aligned_bench_returns = bench_returns.reindex(port_returns.index)
  ```
  yielded a Series filled entirely with `NaN`s, cascading `NaN` through the benchmark equity curves and benchmark CAGR computations.

### 2. Resolution Implemented
- **Index Timezone Stripping**: Inserted defensive check lines inside `portfolio_returns.py`, `benchmark.py`, and `metrics.py`:
  ```python
  if getattr(series.index, "tz", None) is not None:
      series.index = series.index.tz_localize(None)
  ```
  This immediately removes any timezone offsets, aligning all date series strictly on standard timezone-naive calendar dates.
- **Defensive Metrics Calculation**: Overhauled the metric equations in `metrics.py` to:
  - Drop invalid/infinite inputs.
  - Assert non-zero standard deviations (`daily_vol > 0` and `downside_std > 0`) to prevent division by zero.
  - Automatically convert any remaining math-produced `NaN` or `inf` values to `0.0`.
- **Enhanced Logging**: Added explicit logging of shapes and returns:
  - Logs yfinance stock close prices shapes.
  - Logs benchmark close price series shapes.
  - Logs portfolio and benchmark daily returns (row count, first 5 rows, last 5 rows).
  - Logs inner joined portfolio-benchmark dimensions.
  - Logs all intermediate metric coefficients (CAGR, Volatility, Sharpe, Sortino, Alpha, Beta, Information Ratio).
- **Insufficient Data Check**: Added a fallback API handler in `server.py` that intercepts empty datasets or download failures and returns a clean `{ "status": "error", "message": "Insufficient historical data" }` response, which is handled gracefully by the frontend.

---

## 🧪 Verification & Testing Instructions

Open your local development environment:

### 1. Run Backend Server
Ensure the API server is active:
```bash
cd backend
python api_server.py
```

### 2. Run Frontend Server
```bash
cd frontend
npm run dev
```
Open `http://localhost:5173`.

### 3. Validate empty states
By default, the Portfolio Analytics section will show:
- *"Analytics Not Available Yet. No completed portfolio session has been created. Run a live simulation to generate actual allocations..."*

### 4. Execute a Live Simulation
- Configure your stock universe and click **Run Quant agents**.
- Wait for the debate pipeline to complete.
- Once the final verdict message is posted, you will notice a brief *"Historical Portfolio Backtesting in Progress..."* loading state, which then instantly populates the interactive Recharts charts and risk metrics panel using the cached prices.

---

## 🔍 Empty Portfolio Returns & Cache Pollution Resolution (June 2026)

### 1. Root Cause Analysis
- **The Issue**: Portfolio returns were empty inside the Historical Analytics Engine, causing `Insufficient historical data` errors to display on the frontend.
- **Stage where Data becomes Empty**: The data became empty in `compute_weighted_returns` inside [portfolio_returns.py](file:///d:/Algoai/backend/analytics/portfolio_returns.py) on Line 162: `returns_df = prices_df.pct_change().dropna()`.
- **Primary Cause**:
  1. **All-NaN Column Pollution**: When a yfinance download fails to return price data for a ticker (due to temporary API blocks, network timeouts, or invalid tickers) but still returns a `200 OK` structure, the columns for that ticker are returned with all `NaN` values.
  2. **Corrupted Cache Retention**: The engine previously cached these all-NaN Series in the local cache files (e.g. `yf_price_single_LICI_NS_3y.cache`). On subsequent calls, it hit the cache, loaded the all-NaN series, and loaded it into the `prices_df` DataFrame.
  3. **Global Dropna Drop-out**: Because `prices_df.pct_change().dropna()` runs a global `.dropna()`, if even one column in the DataFrame contains entirely `NaN` values, **every single row** in the DataFrame gets dropped, resulting in an empty returns series.

### 2. Resolution Implemented
We implemented a self-healing cache and strict download validation in [portfolio_returns.py](file:///d:/Algoai/backend/analytics/portfolio_returns.py):
1. **Self-Healing Cache Check**: Refactored the cache-hit check to assert `not cached_series.isna().all()`. If an all-NaN cache file is found, it is automatically bypassed, deleted from the local disk, and queued for re-download.
2. **Fresh Download Assertions**: Added validation checks inside both single-ticker and multi-ticker download blocks. If the downloaded series from yfinance is entirely `NaN`, the engine raises an explicit `ValueError` immediately and refuses to save it to the cache.
3. **Debugging Instrumentation**: Added robust log checkpoints inside [__init__.py](file:///d:/Algoai/backend/analytics/__init__.py) to log allocations, ticker validity, historical price dataframe shapes/columns, weight vectors, returns shapes, and to assert that `port_returns` is non-empty before proceeding.

---

## 📈 Production-Grade Diagnostics & Structured Error Reporting (June 2026)

We implemented a comprehensive 8-step verification and diagnostic logging pipeline across the historical analytics system.

### 1. Verification Stages Implemented
1. **Trace Analytics Pipeline (Step 1):** Injected deep log traces capturing weights, allocations, downloaded prices info (row counts, date boundaries), daily returns dataframe shape (before/after `.dropna()`), portfolio return shape, and aligned series shapes.
2. **Validate Portfolio Inputs (Step 2):** In [server.py](file:///d:/Algoai/backend/api/server.py), logged the allocations, weights, and asset list. Verified that weights are non-zero, strategic allocations sum to a positive quantity, and the asset list is not empty.
3. **Validate Market Data Download (Step 3):** Logged the row count, start date, and end date for every single asset ticker. If any ticker fails to download or returns entirely `NaN` values, an explicit error detailing the failed ticker is thrown.
4. **Check Column Matching (Step 4):** Verified that allocation keys match the downloaded price DataFrame columns exactly. Any mismatch is logged and returns a structured error.
5. **Check Date Alignment (Step 5 & 6):** Tracked and logged DataFrame shapes before and after dropping NaNs (`prices_df.shape` -> `pct_change.shape` -> `returns_df.shape`), pinpointing the exact transformation that filters out data. Logged the computed portfolio returns shape, `.head()`, and `.tail()`.
6. **Lookback Period Validation (Step 7):** Added verification to ensure that every selected asset has at least 3 years (1000 calendar days) of historical price data and that the benchmark has matching dates overlapping with the portfolio.
7. **Structured Error Reporting (Step 8):** Refactored the endpoint and engine to return a structured error JSON with `status: "error"`, the failed `stage` of execution, and the concrete `reason`.

### 2. Example API Error Responses
- **Input Validation Error:**
  ```json
  {
    "status": "error",
    "stage": "portfolio_input_validation",
    "reason": "Aggregate weight sum is zero. Cannot compute returns."
  }
  ```
- **Market Data Fetch Error:**
  ```json
  {
    "status": "error",
    "stage": "market_download",
    "reason": "ticker data unavailable: returned empty prices dataframe"
  }
  ```
- **Date Alignment/Dropna Error:**
  ```json
  {
    "status": "error",
    "stage": "date_alignment",
    "reason": "returns dataframe empty after date alignment and dropna"
  }
  ```


