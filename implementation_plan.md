# Historical Portfolio Analytics Engine Plan

Implement a production-grade historical portfolio performance analytics pipeline in the backend using yfinance. All charts (Equity Curve, Drawdown History) and risk metrics (Sharpe, Sortino, Volatility, Max Drawdown, Calmar, CAGR, Alpha, Beta, Information Ratio) must be derived from actual daily asset prices and the final allocations approved by AlgoAI agents.

---

## User Review Required

> [!IMPORTANT]
> **Real Market Data**: This feature will download real 3-year daily price series for all active stocks and NIFTY (^NSEI) from Yahoo Finance (yfinance) on the fly.
> **No Mock telemetries**: In accordance with instructions, no synthetic data is used under any circumstances. If internet access is unavailable or yfinance rate limits occur, the API will display an error message rather than generating fake returns.

---

## Proposed Changes

### 1. Backend: Portfolio Analytics Engine

Create a new package directory `backend/analytics` with the following modular files:

#### [NEW] [__init__.py](file:///d:/Algoai/backend/analytics/__init__.py)
- Expose the main orchestrator function `compute_portfolio_analytics`.

#### [NEW] [portfolio_returns.py](file:///d:/Algoai/backend/analytics/portfolio_returns.py)
- Download 3-year historical close price data for portfolio tickers.
- Align dates and calculate individual asset returns.
- Compute daily weighted portfolio returns using target weights.

#### [NEW] [equity_curve.py](file:///d:/Algoai/backend/analytics/equity_curve.py)
- Compute daily equity values starting from an initial capital of 100,000.
- Formula: `equity[t] = equity[t-1] * (1 + portfolio_return[t])`.

#### [NEW] [drawdown.py](file:///d:/Algoai/backend/analytics/drawdown.py)
- Calculate running peak equity and daily drawdown percentages.
- Formula: `drawdown[t] = (equity[t] - peak[t]) / peak[t]`.

#### [NEW] [benchmark.py](file:///d:/Algoai/backend/analytics/benchmark.py)
- Download NIFTY Index (`^NSEI`) close prices.
- Compute benchmark daily returns and benchmark equity curve.
- Align NIFTY dates with portfolio dates.

#### [NEW] [metrics.py](file:///d:/Algoai/backend/analytics/metrics.py)
- Calculate annual CAGR, annualized return, volatility, Sharpe ratio, Sortino ratio, max drawdown, Calmar ratio, Information ratio, Beta, and Alpha.
- All metrics are calculated dynamically using the return series of the portfolio and NIFTY benchmark.

---

### 2. Backend: API Endpoint

#### [MODIFY] [api/server.py](file:///d:/Algoai/backend/api/server.py)
- Import `compute_portfolio_analytics` orchestrator.
- Add endpoint `GET /api/portfolio/analytics` matching the response schema:
  - `metrics`: All annualized risk ratios, Alpha, Beta, CAGR, Excess Return.
  - `equity_curve`: Chronological array of `{ date, value }`.
  - `drawdown_curve`: Chronological array of `{ date, drawdown }`.
  - `benchmark_curve`: Chronological array of `{ date, portfolio, benchmark }`.
- Default to the latest active session allocations if no `session_id` is supplied in query parameters. Support demo stock allocations if `session_id` is `"demo-hackathon-session"`.

---

### 3. Frontend: Dashboard Charts Integration

#### [MODIFY] [App.jsx](file:///d:/Algoai/frontend/src/App.jsx)
- **API telemetry**: Fetch `/api/portfolio/analytics?session_id=<id>` when the final verdict is reached, or when loading the demo playback.
- **Equity Curve Chart**: Render a Recharts `LineChart` plotting portfolio equity vs NIFTY benchmark.
- **Drawdown Chart**: Render a Recharts `AreaChart` plotting drawdown percentages.
- **Outperformance Badges**: Display Portfolio Return vs Benchmark Return and calculated Excess Return.
- **Risk metrics**: Feed count-up grids with the actual ratios returned from the API.

---

## Verification Plan

### Automated Tests
- Since commands are restricted in this environment, verification will be done manually or via running python main files locally.

### Manual Verification
1. Run the FastAPI server locally (`python backend/api_server.py`).
2. Switch frontend to Demo playback and run the debate, or run a Live API session.
3. Once final allocations are made, verify:
   - Equity curve chart plots Portfolio vs Nifty.
   - Drawdown history shows negative peak distance percentages.
   - Benchmark outperformances are calculated.
   - Ratios in the grid (Sharpe, Vol, Calmar, Sortino) match the exact values returned from the backend.
