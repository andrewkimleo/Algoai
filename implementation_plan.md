# Implementation Plan - Historical Portfolio Analytics Diagnostics & Resolution

We performed a forensic investigation into why the Historical Portfolio Analytics module is returning "Insufficient Historical Data" in the frontend.

## Forensic Findings

### 1. Root Cause
* **Strategic vs. Stock allocations:** The portfolio arbiter generates strategy-level allocation percentages (e.g. `{"strategy": "momentum", "allocation_pct": 10.0}`). To perform historical backtesting, the backend must map these strategy-level allocations to their underlying stock tickers (`picks` and `weights`).
* **Missing Suffix Mapping/Alignment in Arbiter:** In `portfolio_arbiter.py`, the matching logic checks:
  ```python
  prop = next((p for p in approved_proposals if p.get("strategy") == item.strategy), {})
  ```
  If the LLM returns `"strategy": "momentum"` but `approved_proposals` has `"strategy": "momentum_agent"` (or vice-versa), they mismatch. This sets `proposal_id = "unknown"`.
* **Empty Ticker Mapping in Payload:** When `proposal_id` is `"unknown"`, the lookup of `pick_info` inside `run_portfolio_arbiter` fails:
  ```python
  pick_info = next((p for p in all_picks if p["proposal_id"] == item.proposal_id), {})
  ```
  This returns an empty dict `{}`, so `picks` and `weights` are serialized as `[]` inside the `final_verdict` message allocations.
* **Weights Sum Zero Guard:** When `picks` and `weights` are empty lists, `zip(picks, wt_list)` runs 0 times in `server.py`, yielding an empty `weights` dictionary. This triggers a direct return of the error dict:
  ```python
  {"status": "error", "stage": "portfolio_input_validation", "reason": "Aggregate weight sum is zero. Cannot compute returns."}
  ```
* **Frontend Error Masking Bug:** In `App.jsx` (Line 1495), the API fetch handler checks:
  ```javascript
  if (data && data.status === 'error') {
    throw new Error(data.message || "Insufficient historical data");
  }
  ```
  Because the backend returns `data.reason` (not `data.message`), `data.message` is `undefined`. This causes the frontend to throw `"Insufficient historical data"`, which gets captured in the catch block and displays a generic `"Insufficient Historical Data"` error card in the UI, masking the true root cause.

---

## Proposed Changes

### 1. Robust Strategy Key Normalization in Arbiter
#### [MODIFY] [portfolio_arbiter.py](file:///d:/Algoai/backend/agents/portfolio_arbiter.py)
* Add a normalization helper function `normalize_strat(s: str) -> str` to strip suffixes (e.g., `_agent`, `_strategy`, `agent`, `strategy`, spaces, underscores) and convert to lowercase.
* Apply `normalize_strat` when finding matching proposals in both the LLM success branch and the deterministic fallback branch:
  ```python
  prop = next((p for p in approved_proposals if normalize_strat(p.get("strategy")) == normalize_strat(item.strategy)), {})
  if not prop:
      prop = next((p for p in approved_proposals if normalize_strat(p.get("sender")) == normalize_strat(item.strategy)), {})
  ```

### 2. Self-Healing Allocation Lookup in Server
#### [MODIFY] [server.py](file:///d:/Algoai/backend/api/server.py)
* If `picks` or `weights` is missing/empty for a strategy allocation inside the `final_verdict` message, query the session message history in reverse chronological order to find the latest `proposal` or `revision` message for that strategy and extract `picks` and `weights` dynamically.
* Populates both `"reason"` and `"message"` keys in all FastAPI-level validation errors.

### 3. Populating "message" alongside "reason" in Analytics Engine
#### [MODIFY] [__init__.py](file:///d:/Algoai/backend/analytics/__init__.py)
* Update all returning error dictionaries to include both `"reason"` and `"message"` keys. E.g.:
  ```python
  return {
      "status": "error",
      "stage": "market_download",
      "reason": f"ticker data empty or all NaN for {t_norm}",
      "message": f"ticker data empty or all NaN for {t_norm}"
  }
  ```

### 4. Direct Diagnostic Error Reporting in Frontend
#### [MODIFY] [App.jsx](file:///d:/Algoai/frontend/src/App.jsx)
* Refactor the fetch handler (Line 1495) to throw `data.reason || data.message || "Insufficient historical data"` so the exact backend diagnostic message appears on the screen in case of a pipeline error.

---

## Verification Plan

### Manual Verification
1. Open the UI and run a live simulation.
2. Confirm the debate completes.
3. Verify that the analytics load successfully without throwing "Insufficient Historical Data".
4. If any ticker fails yfinance download or lookback validation, confirm the specific failure reason is detailed inside the performance error card on screen (e.g. `"ticker LICI.NS has insufficient history"` or `"Aggregate weight sum is zero"`), rather than displaying the generic mask.
