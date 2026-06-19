// Mock debate data derived from real backend audit logs
export const mockDebateSession = {
  chat_id: "demo-hackathon-session",
  generated: new Date().toISOString(),
  total_messages: 7,
  messages: [
    {
      message_id: "demo-msg-1",
      timestamp: new Date(Date.now() - 300000).toISOString(),
      sender: "momentum_agent",
      message_type: "proposal",
      content: "[PROPOSAL] Momentum Strategy: Proposed picks: RELIANCE.NS, TCS.NS, INFY.NS",
      payload: {
        strategy: "momentum",
        picks: ["RELIANCE.NS", "TCS.NS", "INFY.NS"],
        weights: [40.0, 30.0, 30.0],
        backtest_summary: {
          win_rate: 62.5,
          max_drawdown: 8.2,
          sharpe: 1.45
        },
        raw_output: "STRATEGY: Momentum\nPICKS: RELIANCE.NS, TCS.NS, INFY.NS\nWEIGHTS: 40%, 30%, 30% \nRATIONALE: RELIANCE.NS is selected for its impressive 60-day momentum of 13.52%. TCS.NS is chosen for its strong short-term price breakout. INFY.NS qualifies due to its golden-cross configuration.\nRISK: Subject to sudden momentum reversals and sector rotation.",
        entry_condition: "50-day SMA crosses above 200-day SMA (golden cross)",
        exit_condition: "50-day SMA crosses below 200-day SMA or stop-loss hit",
        stop_loss_pct: 3.0,
        take_profit_pct: 6.0,
        position_size_pct: 10.0
      }
    },
    {
      message_id: "demo-msg-2",
      timestamp: new Date(Date.now() - 250000).toISOString(),
      sender: "mean_reversion_agent",
      message_type: "proposal",
      content: "[PROPOSAL] Mean Reversion Strategy: Proposed picks: SBIN.NS, AXISBANK.NS, ICICIBANK.NS",
      payload: {
        strategy: "mean_reversion",
        picks: ["SBIN.NS", "AXISBANK.NS", "ICICIBANK.NS"],
        weights: [60.0, 20.0, 20.0],
        backtest_summary: {
          win_rate: 58.3,
          max_drawdown: 5.6,
          sharpe: 1.28
        },
        raw_output: "STRATEGY: Mean Reversion\nPICKS: SBIN.NS, AXISBANK.NS, ICICIBANK.NS\nWEIGHTS: 60%, 20%, 20%\nRATIONALE: SBIN.NS is heavily oversold with a Z-Score of -2.05, representing an extreme price deviation. AXISBANK.NS and ICICIBANK.NS have Z-Scores of -1.31 and -1.06 respectively, indicating solid entry points for a technical rebound.\nRISK: Vulnerable to value traps where prices remain suppressed for extended periods.",
        entry_condition: "Daily RSI below 30 or Bollinger Band lower channel breach",
        exit_condition: "RSI crosses above 60 or trailing stop-loss activated",
        stop_loss_pct: 4.0,
        take_profit_pct: 8.0,
        position_size_pct: 10.0
      }
    },
    {
      message_id: "demo-msg-3",
      timestamp: new Date(Date.now() - 200000).toISOString(),
      sender: "sentiment_agent",
      message_type: "proposal",
      content: "[PROPOSAL] Sentiment Strategy: Proposed picks: WIPRO.NS, ICICIBANK.NS, AXISBANK.NS",
      payload: {
        strategy: "sentiment",
        picks: ["WIPRO.NS", "ICICIBANK.NS", "AXISBANK.NS"],
        weights: [40.0, 30.0, 30.0],
        backtest_summary: {
          win_rate: 68.1,
          max_drawdown: 9.5,
          sharpe: 1.62
        },
        raw_output: "STRATEGY: Sentiment Analysis\nPICKS: WIPRO.NS, ICICIBANK.NS, AXISBANK.NS\nWEIGHTS: 40%, 30%, 30%\nRATIONALE: WIPRO.NS has a positive news sentiment score of 0.56 following a share buyback announcement. ICICIBANK.NS has strong institutional purchase sentiment (0.36). AXISBANK.NS reports high social media buzz (0.33).\nRISK: News sentiment is highly volatile and prone to sudden reversals on macro developments.\nEXPLAINABILITY NOTE: Keyword-scored headlines only. Purely transparent SEBI-compliant keyword heuristics.",
        entry_condition: "7-day average sentiment score > +0.25 (positive outlook)",
        exit_condition: "Sentiment score drops below 0.0 or 5% loss limit reached",
        stop_loss_pct: 5.0,
        take_profit_pct: 10.0,
        position_size_pct: 10.0,
        explainability_note: "All signals derived from keyword-scored headlines as required under SEBI Feb 2025 algo framework. No black-box model used.",
        sebi_compliant: true
      }
    },
    {
      message_id: "demo-msg-4",
      timestamp: new Date(Date.now() - 150000).toISOString(),
      sender: "stress_test_agent",
      message_type: "challenge",
      content: "[CHALLENGE] Challenging 'momentum': Stress test breach identified in historical simulation",
      payload: {
        target_strategy: "momentum",
        reason: "Stress test simulation shows a Worst-Month drawdown of -17.40% during the market correction of Feb 2026. This severely breaches the proposed 3.0% stop-loss threshold. The strategy's momentum picks display extreme correlation under stress, increasing systemic risk.",
        severity: "high"
      }
    },
    {
      message_id: "demo-msg-5",
      timestamp: new Date(Date.now() - 100000).toISOString(),
      sender: "momentum_agent",
      message_type: "revision",
      content: "[REVISION] Updated 'Momentum Strategy': Revised picks and weights to hedge drawdown risk",
      payload: {
        strategy: "momentum",
        picks: ["SBIN.NS", "TCS.NS", "HDFCBANK.NS"],
        weights: [40.0, 30.0, 30.0],
        raw_output: "REVISION SUMMARY: In response to the Stress Test challenge, we have replaced RELIANCE.NS with SBIN.NS and TCS.NS to decrease correlation and hedge drawdown risk. We also reduced our weight in volatile sectors and adjusted the stop-loss to 4.5% to allow breathing room during short-term shocks.\nPICKS: SBIN.NS, TCS.NS, HDFCBANK.NS\nWEIGHTS: 40%, 30%, 30%",
        backtest_summary: {
          win_rate: 61.2,
          max_drawdown: 6.4,
          sharpe: 1.51
        },
        stop_loss_pct: 4.5,
        take_profit_pct: 9.0
      }
    },
    {
      message_id: "demo-msg-6",
      timestamp: new Date(Date.now() - 50000).toISOString(),
      sender: "compliance_agent",
      message_type: "compliance_verdict",
      content: "[COMPLIANCE] Compliance Verdict: 3/3 strategies audited against SEBI Algorithmic Trading Framework",
      payload: {
        target_strategy: "all_proposals",
        status: "approved",
        algo_tag_id: "SEBI-NSE-2026-9F82A3E8",
        reasoning: "All proposed and revised algorithms have undergone SEBI guidelines audits. 1) Order Frequency check passed (no High-Frequency HFT indicators). 2) Explainability audit verified (rule-based white-box decision trees). 3) Position exposure limits compliant (none exceed the 10% maximum portfolio allocation limit). Order tag assigned: SEBI-NSE-2026-9F82A3E8.",
        checks_run: [
          {
            "check_name": "Order Frequency Audit",
            passed: true,
            message: "Max frequency: 0.0001 orders/sec (well below retail algorithmic limit of 10/sec)."
          },
          {
            "check_name": "Explainability & Transparency",
            passed: true,
            message: "Transparent white-box models (SMA crossover, RSI thresholds, keyword counting). No black-box neural networks."
          },
          {
            "check_name": "Single-Position Limits",
            passed: true,
            message: "Maximum single-position exposure is 6.0% (within the SEBI 10.0% regulatory ceiling)."
          },
          {
            "check_name": "Audit Trail Readiness",
            passed: true,
            message: "Full message payload history logged with structural inputs and execution conditions."
          }
        ]
      }
    },
    {
      message_id: "demo-msg-7",
      timestamp: new Date(Date.now() - 10000).toISOString(),
      sender: "portfolio_arbiter",
      message_type: "final_verdict",
      content: "[FINAL VERDICT] Allocations approved: 45% Momentum, 35% Mean Reversion, 20% Sentiment",
      payload: {
        allocations: [
          {
            proposal_id: "demo-msg-5",
            strategy: "momentum",
            picks: ["SBIN.NS", "TCS.NS", "HDFCBANK.NS"],
            weights: [40.0, 30.0, 30.0],
            allocation_pct: 45.0,
            status: "approved",
            sender: "momentum_agent"
          },
          {
            proposal_id: "demo-msg-2",
            strategy: "mean_reversion",
            picks: ["SBIN.NS", "AXISBANK.NS", "ICICIBANK.NS"],
            weights: [60.0, 20.0, 20.0],
            allocation_pct: 35.0,
            status: "approved",
            sender: "mean_reversion_agent"
          },
          {
            proposal_id: "demo-msg-3",
            strategy: "sentiment",
            picks: ["WIPRO.NS", "ICICIBANK.NS", "AXISBANK.NS"],
            weights: [40.0, 30.0, 30.0],
            allocation_pct: 20.0,
            status: "approved",
            sender: "sentiment_agent"
          }
        ],
        reasoning: "The portfolio is fully optimized. We allocate 45% to Momentum (Revised) due to its excellent risk-hedged parameters following the stress test. We allocate 35% to Mean Reversion, capitalising on oversold opportunities, and 20% to Sentiment to capture short-term news events. Overall correlation coefficient remains below 0.35, presenting a highly diversified retail portfolio."
      }
    }
  ]
};
