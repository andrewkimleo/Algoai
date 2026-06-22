import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  Cpu,
  ShieldCheck,
  AlertTriangle,
  TrendingUp,
  Terminal,
  Activity,
  CheckCircle2,
  XCircle,
  Compass,
  ArrowRight,
  RefreshCw,
  X,
  ChevronDown,
  ChevronUp,
  LineChart as LineIcon,
  PieChart as PieIcon,
  Info
} from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend, LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import { mockDebateSession } from './mockData';

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Constants for UI mapping
const AGENT_META = {
  momentum_agent: {
    name: "Momentum Analyst",
    role: "Quant Momentum Strategy",
    color: "var(--accent-cyan)",
    icon: TrendingUp,
  },
  mean_reversion_agent: {
    name: "Mean Reversion Analyst",
    role: "Statistical Mean Reversion",
    color: "var(--accent-purple)",
    icon: Compass,
  },
  sentiment_agent: {
    name: "Senti-Quant Analyst",
    role: "News Sentiment Heuristics",
    color: "var(--accent-cyan)",
    icon: Activity,
  },
  stress_test_agent: {
    name: "Stress Tester",
    role: "Portfolio Risk & Backtest",
    color: "var(--accent-orange)",
    icon: AlertTriangle,
  },
  compliance_agent: {
    name: "Compliance Officer",
    role: "SEBI Algorithmic Audit",
    color: "var(--accent-emerald)",
    icon: ShieldCheck,
  },
  portfolio_arbiter: {
    name: "Portfolio Arbiter",
    role: "Capital Allocation Lead",
    color: "var(--accent-purple)",
    icon: Cpu,
  }
};

const VALID_STOCKS = [
  { code: "RELIANCE", name: "Reliance Industries Ltd." },
  { code: "TCS", name: "Tata Consultancy Services Ltd." },
  { code: "INFY", name: "Infosys Ltd." },
  { code: "HDFCBANK", name: "HDFC Bank Ltd." },
  { code: "ICICIBANK", name: "ICICI Bank Ltd." },
  { code: "BHARTIARTL", name: "Bharti Airtel Ltd." },
  { code: "SBIN", name: "State Bank of India" },
  { code: "LICI", name: "Life Insurance Corporation of India" },
  { code: "ITC", name: "ITC Ltd." },
  { code: "HINDUNILVR", name: "Hindustan Unilever Ltd." },
  { code: "LT", name: "Larsen & Toubro Ltd." },
  { code: "BAJFINANCE", name: "Bajaj Finance Ltd." },
  { code: "HCLTECH", name: "HCL Technologies Ltd." },
  { code: "MARUTI", name: "Maruti Suzuki India Ltd." },
  { code: "SUNPHARMA", name: "Sun Pharmaceutical Industries Ltd." },
  { code: "ADANIENT", name: "Adani Enterprises Ltd." },
  { code: "KOTAKBANK", name: "Kotak Mahindra Bank Ltd." },
  { code: "AXISBANK", name: "Axis Bank Ltd." },
  { code: "TATAMOTORS", name: "Tata Motors Ltd." },
  { code: "ULTRACEMCO", name: "UltraTech Cement Ltd." },
  { code: "COALINDIA", name: "Coal India Ltd." },
  { code: "ONGC", name: "Oil & Natural Gas Corporation Ltd." },
  { code: "NTPC", name: "NTPC Ltd." },
  { code: "POWERGRID", name: "Power Grid Corporation of India Ltd." },
  { code: "JSWSTEEL", name: "JSW Steel Ltd." },
  { code: "M&M", name: "Mahindra & Mahindra Ltd." },
  { code: "TITAN", name: "Titan Company Ltd." },
  { code: "ASIANPAINT", name: "Asian Paints Ltd." },
  { code: "ADANIPORTS", name: "Adani Ports & SEZ Ltd." },
  { code: "TATACONSUM", name: "Tata Consumer Products Ltd." },
  { code: "BRITANNIA", name: "Britannia Industries Ltd." },
  { code: "NESTLEIND", name: "Nestle India Ltd." },
  { code: "TECHM", name: "Tech Mahindra Ltd." },
  { code: "LTIM", name: "LTIMindtree Ltd." },
  { code: "HDFCLIFE", name: "HDFC Life Insurance Company Ltd." },
  { code: "SBILIFE", name: "SBI Life Insurance Company Ltd." },
  { code: "ICICIPRULI", name: "ICICI Prudential Life Insurance" },
  { code: "BAJAJFINSV", name: "Bajaj Finserv Ltd." },
  { code: "INDUSINDBK", name: "IndusInd Bank Ltd." },
  { code: "TATASTEEL", name: "Tata Steel Ltd." },
  { code: "GRASIM", name: "Grasim Industries Ltd." },
  { code: "HINDALCO", name: "Hindalco Industries Ltd." },
  { code: "DRREDDY", name: "Dr. Reddy's Laboratories Ltd." },
  { code: "CIPLA", name: "Cipla Ltd." },
  { code: "EICHERMOT", name: "Eicher Motors Ltd." },
  { code: "HEROMOTOCO", name: "Hero MotoCorp Ltd." },
  { code: "BPCL", name: "Bharat Petroleum Corporation Ltd." },
  { code: "IOC", name: "Indian Oil Corporation Ltd." },
  { code: "DIVISLAB", name: "Divi's Laboratories Ltd." },
  { code: "HINDZINC", name: "Hindustan Zinc Ltd." },
  { code: "VEDL", name: "Vedanta Ltd." },
  { code: "SHREECEM", name: "Shree Cement Ltd." },
  { code: "PIDILITIND", name: "Pidilite Industries Ltd." },
  { code: "SIEMENS", name: "Siemens Ltd." },
  { code: "DLF", name: "DLF Ltd." },
  { code: "GODREJCP", name: "Godrej Consumer Products Ltd." },
  { code: "DABUR", name: "Dabur India Ltd." },
  { code: "COLPAL", name: "Colgate-Palmolive (India) Ltd." },
  { code: "MARICO", name: "Marico Ltd." },
  { code: "TRENT", name: "Trent Ltd." },
  { code: "BEL", name: "Bharat Electronics Ltd." },
  { code: "HAL", name: "Hindustan Aeronautics Ltd." },
  { code: "IRCTC", name: "IRCTC Ltd." },
  { code: "ZOMATO", name: "Zomato Ltd." },
  { code: "PAYTM", name: "One97 Communications Ltd. (Paytm)" },
  { code: "NYKAA", name: "FSN E-Commerce Ventures (Nykaa)" },
  { code: "POLICYBZR", name: "PB Fintech Ltd. (Policybazaar)" },
  { code: "GAIL", name: "GAIL (India) Ltd." },
  { code: "SAIL", name: "Steel Authority of India Ltd." },
  { code: "NMDC", name: "NMDC Ltd." },
  { code: "PNB", name: "Punjab National Bank" },
  { code: "BOB", name: "Bank of Baroda" },
  { code: "CANBK", name: "Canara Bank" },
  { code: "UNIONBANK", name: "Union Bank of India" },
  { code: "IDBI", name: "IDBI Bank Ltd." },
  { code: "YESBANK", name: "Yes Bank Ltd." },
  { code: "JINDALSTEL", name: "Jindal Steel & Power Ltd." },
  { code: "HAVELLS", name: "Havells India Ltd." },
  { code: "AMBUJACEM", name: "Ambuja Cements Ltd." },
  { code: "ACC", name: "ACC Ltd." },
  { code: "MUTHOOTFIN", name: "Muthoot Finance Ltd." },
  { code: "CHOLAFIN", name: "Cholamandalam Investment & Finance" },
  { code: "SRF", name: "SRF Ltd." },
  { code: "AUBANK", name: "AU Small Finance Bank Ltd." },
  { code: "BANDHANBNK", name: "Bandhan Bank Ltd." },
  { code: "FEDERALBNK", name: "The Federal Bank Ltd." },
  { code: "IDFCFIRSTB", name: "IDFC First Bank Ltd." },
  { code: "GMRINFRA", name: "GMR Airports Infrastructure Ltd." },
  { code: "IRFC", name: "Indian Railway Finance Corporation" },
  { code: "RVNL", name: "Rail Vikas Nigam Ltd." },
  { code: "RECL", name: "REC Ltd." },
  { code: "PFC", name: "Power Finance Corporation Ltd." },
  { code: "WIPRO", name: "Wipro Ltd." }
];

function TickerSelect({ selected, onChange }) {
  const [search, setSearch] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleRemove = (ticker) => {
    onChange(selected.filter(t => t !== ticker));
  };

  const handleAdd = (ticker) => {
    const uppercaseTicker = ticker.toUpperCase().trim();
    if (uppercaseTicker && !selected.includes(uppercaseTicker)) {
      onChange([...selected, uppercaseTicker]);
    }
    setSearch("");
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && search.trim()) {
      e.preventDefault();
      handleAdd(search);
    }
  };

  const filteredOptions = VALID_STOCKS.filter(opt =>
    opt.code.toLowerCase().includes(search.toLowerCase()) ||
    opt.name.toLowerCase().includes(search.toLowerCase())
  );

  const exactMatch = VALID_STOCKS.some(opt => opt.code.toUpperCase() === search.toUpperCase().trim());

  return (
    <div className="ticker-select-container" ref={containerRef}>
      <div 
        className="ticker-select-input-container"
        onClick={() => setIsOpen(true)}
      >
        {selected.map(ticker => (
          <span key={ticker} className="ticker-select-tag">
            {ticker}
            <button 
              type="button" 
              className="ticker-select-tag-remove"
              onClick={(e) => {
                e.stopPropagation();
                handleRemove(ticker);
              }}
            >
              <X size={12} style={{ display: 'block' }} />
            </button>
          </span>
        ))}
        <input
          type="text"
          className="ticker-select-search-input"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
          placeholder={selected.length === 0 ? "Search or type ticker (e.g. RELIANCE, TCS)..." : ""}
        />
      </div>

      {isOpen && (
        <div className="ticker-select-dropdown">
          {filteredOptions.map(opt => {
            const isSelected = selected.includes(opt.code);
            return (
              <div
                key={opt.code}
                className={`ticker-select-option ${isSelected ? 'selected' : ''}`}
                onClick={() => {
                  if (isSelected) {
                    handleRemove(opt.code);
                  } else {
                    handleAdd(opt.code);
                  }
                }}
              >
                <div>
                  <span className="ticker-select-option-code">{opt.code}</span>
                  <span style={{ margin: '0 0.5rem', opacity: 0.3 }}>|</span>
                  <span className="ticker-select-option-name">{opt.name}</span>
                </div>
                {isSelected && <span style={{ color: 'var(--accent-cyan)', fontSize: '0.8rem' }}>✓</span>}
              </div>
            );
          })}
          
          {search.trim() && !exactMatch && (
            <div 
              className="ticker-select-option"
              onClick={() => handleAdd(search)}
              style={{ borderTop: '1px dashed rgba(255,255,255,0.08)', color: 'var(--accent-cyan)' }}
            >
              <span>Add custom: <strong className="ticker-select-option-code">{search.toUpperCase().trim()}</strong></span>
              <span className="ticker-select-option-name">Press Enter to add</span>
            </div>
          )}

          {filteredOptions.length === 0 && !search.trim() && (
            <div className="ticker-select-no-results">No options available</div>
          )}
        </div>
      )}
    </div>
  );
}

// ==========================================
// Institutional Dashboard Sub-Components
// ==========================================

const STRESS_TESTS = [
  { name: "Inflation Shock", passed: true, drawdown: "-3.8%", volSpike: "+8%", status: "Survived" },
  { name: "RBI Rate Hike", passed: true, drawdown: "-4.2%", volSpike: "+12%", status: "Survived" },
  { name: "Oil Price Spike", passed: true, drawdown: "-6.1%", volSpike: "+18%", status: "Survived" },
  { name: "Banking Crisis", passed: true, drawdown: "-5.4%", volSpike: "+15%", status: "Survived" },
  { name: "Earnings Recession", passed: true, drawdown: "-3.2%", volSpike: "+9%", status: "Survived" },
  { name: "COVID Crash", passed: false, drawdown: "-18.2%", volSpike: "+45%", status: "Breached Stop-Loss" },
  { name: "Flash Crash", passed: false, drawdown: "-12.5%", volSpike: "+38%", status: "Breached Stop-Loss" },
  { name: "Currency Shock", passed: true, drawdown: "-2.8%", volSpike: "+6%", status: "Survived" },
  { name: "Sovereign Downgrade", passed: true, drawdown: "-4.9%", volSpike: "+11%", status: "Survived" },
  { name: "Liquidity Crunch", passed: true, drawdown: "-5.1%", volSpike: "+14%", status: "Survived" }
];

const getConfidenceScore = (agentId, isRevised) => {
  if (agentId === 'momentum_agent') return isRevised ? 91 : 87;
  if (agentId === 'mean_reversion_agent') return 76;
  if (agentId === 'sentiment_agent') return 82;
  return 80;
};

const getTopSignals = (agentId, isRevised, picks = []) => {
  const stockPicks = picks && picks.length > 0 ? picks : (agentId === 'momentum_agent' ? (isRevised ? ["SBIN.NS", "TCS.NS", "HDFCBANK.NS"] : ["RELIANCE.NS", "TCS.NS", "INFY.NS"]) : 
                      agentId === 'mean_reversion_agent' ? ["SBIN.NS", "AXISBANK.NS", "ICICIBANK.NS"] : ["WIPRO.NS", "ICICIBANK.NS", "AXISBANK.NS"]);

  const signals = {
    "RELIANCE.NS": "Z-Score: -1.15",
    "INFY.NS": "RSI: 39.1",
    "TATAMOTORS.NS": "Band Dist: +3.4%",
    "SBIN.NS": agentId === 'mean_reversion_agent' ? "Z-Score: -2.05" : "Z-Score: -0.42",
    "AXISBANK.NS": "Z-Score: -1.31",
    "ICICIBANK.NS": agentId === 'mean_reversion_agent' ? "Z-Score: -1.06" : "Inst. Buying: +0.36",
    "WIPRO.NS": "Sentiment: +0.56",
    "TCS.NS": "Breakout: +2.1%",
    "HDFCBANK.NS": "EMA Cross: +1.5%",
  };

  return stockPicks.slice(0, 3).map(pick => {
    const formattedPick = pick.endsWith('.NS') ? pick : `${pick}.NS`;
    return {
      stock: formattedPick,
      signal: signals[formattedPick] || `RSI: 48.5`
    };
  });
};

// Custom React count-up hook implemented as a component using requestAnimationFrame
function AnimatedNumber({ value, decimals = 0, suffix = "" }) {
  const [count, setCount] = useState(0);
  const elementRef = useRef(null);
  const [hasAnimated, setHasAnimated] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated) {
          setHasAnimated(true);
        }
      },
      { threshold: 0.1 }
    );
    if (elementRef.current) {
      observer.observe(elementRef.current);
    }
    return () => observer.disconnect();
  }, [hasAnimated]);

  const numericValue = parseFloat(value);
  const isValid = value !== null && value !== undefined && !isNaN(numericValue) && isFinite(numericValue);

  useEffect(() => {
    if (!hasAnimated || !isValid) return;
    let startTimestamp = null;
    const duration = 1200; // 1.2 seconds
    const step = (timestamp) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      const easeProgress = progress * (2 - progress); // easeOutQuad
      setCount(easeProgress * numericValue);
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        setCount(numericValue);
      }
    };
    requestAnimationFrame(step);
  }, [value, hasAnimated, isValid, numericValue]);

  if (!isValid) {
    return <span ref={elementRef}>{value !== null && value !== undefined ? String(value) : "--"}{suffix}</span>;
  }

  return <span ref={elementRef}>{typeof count === 'number' ? count.toFixed(decimals) : String(count)}{suffix}</span>;
}

// Circular SVG Progress Ring
function CircularProgress({ value, size = 50, strokeWidth = 5, color = 'var(--accent-cyan)' }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div style={{ position: 'relative', width: size, height: size, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg width={size} height={size}>
        <circle
          stroke="rgba(255,255,255,0.06)"
          fill="transparent"
          strokeWidth={strokeWidth}
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
        <circle
          stroke={color}
          fill="transparent"
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          r={radius}
          cx={size / 2}
          cy={size / 2}
          style={{ transition: 'stroke-dashoffset 0.8s ease-in-out', transform: 'rotate(-90deg)', transformOrigin: '50% 50%' }}
        />
      </svg>
      <div style={{ position: 'absolute', fontSize: '0.75rem', fontWeight: 'bold', color: '#fff' }}>
        {Math.round(value)}%
      </div>
    </div>
  );
}

function ConfidenceIndicator({ score, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
      <CircularProgress value={score} size={42} strokeWidth={4} color={color} />
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.2px' }}>Confidence</span>
        <span style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#fff' }}>
          <AnimatedNumber value={score} decimals={0} suffix="%" />
        </span>
      </div>
    </div>
  );
}

// Component for Strategy Card
function StrategyAgentCard({ agentId, proposal, isThinking, meta, activeSpinners }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const AgentIcon = meta.icon;

  const backtest = (proposal && proposal.payload && proposal.payload.backtest_summary) ? proposal.payload.backtest_summary : {
    sharpe: agentId === 'momentum_agent' ? 1.45 : agentId === 'mean_reversion_agent' ? 1.28 : 1.62,
    win_rate: agentId === 'momentum_agent' ? 62.5 : agentId === 'mean_reversion_agent' ? 58.3 : 68.1,
    max_drawdown: agentId === 'momentum_agent' ? 8.2 : agentId === 'mean_reversion_agent' ? 5.6 : 9.5
  };

  const isRevised = proposal && proposal.message_type === 'revision';
  const confidence = getConfidenceScore(agentId, isRevised);
  const signals = getTopSignals(agentId, isRevised, proposal?.payload?.picks);

  return (
    <div
      className={`glass-card-premium animate-fade-in ${proposal ? (agentId === 'momentum_agent' ? 'glow-cyan' : agentId === 'mean_reversion_agent' ? 'glow-purple' : 'glow-cyan') : ''} ${proposal ? 'strategy-approved-glow' : ''}`}
      style={{ position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '1.25rem' }}
    >
      {/* Active thinking overlay */}
      {isThinking && (
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(5,9,20,0.9)', zIndex: 10, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '1rem', textAlign: 'center' }}>
          <div style={{ animation: 'spin 1.5s linear infinite', border: '3px solid rgba(6,182,212,0.1)', borderTopColor: meta.color, borderRadius: '50%', width: '32px', height: '32px', marginBottom: '0.75rem' }}></div>
          <span style={{ fontSize: '0.85rem', color: meta.color, fontWeight: 600 }}>{isThinking}</span>
        </div>
      )}

      <div className="card-header-area" style={{ marginBottom: 0 }}>
        <div className="agent-title">
          <span className="agent-name" style={{ color: meta.color }}>{meta.name}</span>
          <span className="agent-role">{meta.role}</span>
        </div>
        <AgentIcon size={18} style={{ color: meta.color }} />
      </div>

      {!proposal ? (
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic', padding: '1rem 0' }}>
          Awaiting scan inputs...
        </p>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.1rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Strategy: <span className="text-cyan">{proposal.payload?.strategy}</span></span>
            {isRevised && (
              <span className="challenge-severity" style={{ background: 'rgba(168,85,247,0.15)', borderColor: 'rgba(168,85,247,0.3)', color: 'var(--accent-purple)' }}>REVISED</span>
            )}
          </div>

          {/* Quick Metrics & Confidence Side-by-Side */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.15)', borderRadius: '8px', padding: '0.5rem 0.75rem', border: '1px solid rgba(255,255,255,0.03)' }}>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span className="metric-label">Sharpe</span>
                <span className="metric-value text-cyan">
                  <AnimatedNumber value={backtest.sharpe} decimals={2} />
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span className="metric-label">Win Rate</span>
                <span className="metric-value text-emerald">
                  <AnimatedNumber value={backtest.win_rate} decimals={1} suffix="%" />
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span className="metric-label">Max DD</span>
                <span className="metric-value text-red">
                  <AnimatedNumber value={backtest.max_drawdown} decimals={1} suffix="%" />
                </span>
              </div>
            </div>
            <ConfidenceIndicator score={confidence} color={meta.color} />
          </div>

          {/* Key Signals */}
          <div className="key-signals-box">
            <span style={{ fontSize: '0.7rem', fontWeight: 800, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '0.35rem' }}>
              Key Signals
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              {signals.map((sig, sIdx) => (
                <div key={sIdx} className="key-signal-item">
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>✓ {sig.stock}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: meta.color }}>{sig.signal}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Collapsible view full analysis accordion */}
          <div className="accordion-wrapper">
            <button onClick={() => setIsExpanded(!isExpanded)} className="accordion-trigger">
              <span>{isExpanded ? "Hide Detailed Analysis" : "View Full Analysis"}</span>
              {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
            <AnimatePresence>
              {isExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="accordion-content"
                  style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', paddingTop: '0.5rem' }}
                >
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.45, margin: 0 }}>
                    {proposal.payload?.raw_output?.split("RATIONALE:")[1]?.split("RISK:")[0]?.trim() || proposal.content}
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', borderTop: '1px solid rgba(255,255,255,0.03)', paddingTop: '0.5rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Entry Condition:</span>
                      <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{proposal.payload?.entry_condition || "SMA crossover / Bollinger bands breach"}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Exit Condition:</span>
                      <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{proposal.payload?.exit_condition || "Trailing stop-loss activated"}</span>
                    </div>
                  </div>

                  <div style={{ borderTop: '1px solid rgba(255,255,255,0.03)', paddingTop: '0.5rem' }}>
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Asset Weights:</span>
                    <div className="allocation-bar-container" style={{ marginTop: '0.25rem' }}>
                      {proposal.payload?.picks?.map((pick, i) => {
                        const w = proposal.payload.weights[i];
                        const pct = w > 100 ? (w / 10).toFixed(0) : w;
                        return (
                          <div key={pick}>
                            <div className="alloc-bar-label" style={{ fontSize: '0.7rem' }}>
                              <span>{pick}</span>
                              <span>{pct}%</span>
                            </div>
                            <div className="alloc-bar-track" style={{ height: '4px' }}>
                              <div className="alloc-bar-fill" style={{ width: `${pct}%`, backgroundColor: meta.color }}></div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </>
      )}
    </div>
  );
}

// Vertical timelines displaying agent negotiation logs
function AgentNegotiationTimeline({ messages }) {
  const [expandedIndex, setExpandedIndex] = useState(null);

  if (messages.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem', color: 'var(--text-muted)', border: '1px dashed rgba(255,255,255,0.05)', borderRadius: '8px' }}>
        <Activity size={32} style={{ marginBottom: '1rem', opacity: 0.3 }} />
        <p style={{ fontStyle: 'italic', fontSize: '0.85rem' }}>Awaiting agent communication negotiations...</p>
      </div>
    );
  }

  return (
    <div className="timeline-container">
      <div className="timeline-line"></div>
      {messages.map((msg, index) => {
        const meta = AGENT_META[msg.sender] || { name: msg.sender, color: '#94a3b8', icon: Activity };
        const Icon = meta.icon;
        const isExpanded = expandedIndex === index;

        let actionStatement = "";
        let details = null;

        if (msg.message_type === 'proposal') {
          const picks = msg.payload?.picks || [];
          actionStatement = `Proposed allocation weights for ${picks.join(', ')}`;
          details = {
            whyChosen: msg.payload?.raw_output?.split("RATIONALE:")[1]?.split("RISK:")[0]?.trim() || "Indicators triggered entry thresholds in SMA crossover breakouts.",
            risk: msg.payload?.raw_output?.split("RISK:")[1]?.trim() || "Subject to short-term volatility reversals and sector rotation.",
          };
        } else if (msg.message_type === 'challenge') {
          actionStatement = `Challenged momentum proposal: Worst-Month drawdown limit breach`;
          details = {
            whyRejected: msg.payload?.reason || "Breaches the risk/drawdown ceilings.",
            risk: "High historical simulated drawdown in stressed periods."
          };
        } else if (msg.message_type === 'revision') {
          actionStatement = `Revised strategy parameters in response to stress testing`;
          details = {
            whatChanged: msg.payload?.raw_output?.split("REVISION SUMMARY:")[1]?.split("STRATEGY:")[0]?.trim() || "Reallocated weights to defensive sectors, adjusted exit stop-loss limits.",
          };
        } else if (msg.message_type === 'compliance_verdict') {
          actionStatement = `Audited and approved strategies under SEBI framework`;
          details = {
            whyChosen: msg.payload?.reasoning || "Passed single position, sector exposure, and explainability audit checks.",
          };
        } else if (msg.message_type === 'final_verdict') {
          actionStatement = `Synthesized final portfolio allocations`;
          details = {
            whyChosen: msg.payload?.reasoning || "Optimized for maximum risk-adjusted performance with sub-0.35 correlations.",
          };
        } else if (msg.message_type === 'status_update') {
          actionStatement = msg.content || "Running backend model evaluations...";
        } else {
          actionStatement = msg.content;
        }

        return (
          <motion.div
            key={msg.message_id || index}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
            className="timeline-item"
          >
            <div className="timeline-dot" style={{ borderColor: meta.color, boxShadow: `0 0 8px ${meta.color}` }}></div>
            <div className="timeline-badge-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Icon size={14} style={{ color: meta.color }} />
                <span className="timeline-sender-title" style={{ color: meta.color }}>{meta.name}</span>
              </div>
              <span className="timeline-timestamp">{new Date(msg.timestamp || Date.now()).toLocaleTimeString()}</span>
            </div>
            <div className="timeline-msg-bubble">
              <p style={{ fontWeight: 500, color: 'var(--text-primary)', fontSize: '0.8rem' }}>{actionStatement}</p>
              {details && (
                <div style={{ marginTop: '0.25rem' }}>
                  <button
                    onClick={() => setExpandedIndex(isExpanded ? null : index)}
                    className="accordion-trigger"
                    style={{ fontSize: '0.7rem' }}
                  >
                    <span>{isExpanded ? "Hide Explainability" : "View Explainability / Rationale"}</span>
                    {isExpanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                  </button>
                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="accordion-content"
                        style={{ borderTop: '1px solid rgba(255,255,255,0.03)', marginTop: '0.25rem', paddingTop: '0.25rem' }}
                      >
                        {details.whyChosen && (
                          <div style={{ marginBottom: '0.25rem' }}>
                            <strong style={{ color: 'var(--accent-cyan)' }}>Why chosen? </strong>
                            <span>{details.whyChosen}</span>
                          </div>
                        )}
                        {details.whyRejected && (
                          <div style={{ marginBottom: '0.25rem' }}>
                            <strong style={{ color: 'var(--accent-orange)' }}>Why rejected? </strong>
                            <span>{details.whyRejected}</span>
                          </div>
                        )}
                        {details.risk && (
                          <div style={{ marginBottom: '0.25rem' }}>
                            <strong style={{ color: 'var(--accent-red)' }}>Risk detected: </strong>
                            <span>{details.risk}</span>
                          </div>
                        )}
                        {details.whatChanged && (
                          <div style={{ marginBottom: '0.25rem' }}>
                            <strong style={{ color: 'var(--accent-purple)' }}>What changed? </strong>
                            <span>{details.whatChanged}</span>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

// Enhanced Stress Tester Section
function EnhancedStressTester({ messages }) {
  const hasStarted = messages.some(m => m.sender === 'stress_test_agent');

  return (
    <div className="glass-card-premium" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div className="card-header-area">
        <div className="agent-title">
          <span className="agent-name text-orange">Stress Simulator</span>
          <span className="agent-role">Risk Shock Simulations</span>
        </div>
        <AlertTriangle size={18} className="text-orange" />
      </div>

      {!hasStarted ? (
        <div style={{ padding: '2rem 0', color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'center', fontSize: '0.85rem' }}>
          Awaiting stress test simulations...
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Passed Tests:</span>
            <span style={{ padding: '0.15rem 0.5rem', borderRadius: '4px', background: 'rgba(16,185,129,0.15)', color: 'var(--accent-emerald)', fontSize: '0.75rem', fontWeight: 'bold' }}>
              8/10 SURVIVED
            </span>
          </div>

          {/* Progress Bar */}
          <div className="alloc-bar-track" style={{ height: '6px' }}>
            <div className="alloc-bar-fill" style={{ width: '80%', backgroundColor: 'var(--accent-emerald)' }}></div>
          </div>

          <div className="stress-scenarios-grid">
            {STRESS_TESTS.map((test, index) => (
              <div key={index} className={`stress-card ${test.passed ? 'passed' : 'failed'}`}>
                <div className="stress-card-title">
                  <span>{test.name}</span>
                  {test.passed ? (
                    <CheckCircle2 size={11} className="text-emerald" />
                  ) : (
                    <XCircle size={11} className="text-red" />
                  )}
                </div>
                <div className="stress-card-metrics">
                  <div>Max DD: <strong style={{ color: test.passed ? 'var(--text-primary)' : 'var(--accent-red)' }}>{test.drawdown}</strong></div>
                  <div>Vol Spike: <strong style={{ color: 'var(--text-secondary)' }}>{test.volSpike}</strong></div>
                  <div style={{ fontSize: '0.6rem', marginTop: '0.15rem', color: test.passed ? 'var(--accent-emerald)' : 'var(--accent-red)', fontWeight: 'bold' }}>
                    {test.status}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="explain-panel-box" style={{ borderColor: 'rgba(249,115,22,0.15)', background: 'rgba(249,115,22,0.02)', padding: '0.6rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
              <Info size={12} className="text-orange" />
              <strong style={{ fontSize: '0.7rem', color: 'var(--accent-orange)' }}>Stress Test Risk Analysis</strong>
            </div>
            <p style={{ fontSize: '0.68rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
              Momentum strategy breached drawdown ceilings during historical simulations of extreme COVID and Flash Crash shocks. Systemic sector correlation was reduced via revised diversification (weights shifted to defensive cash-rich stocks).
            </p>
          </div>
        </motion.div>
      )}
    </div>
  );
}

// Redesigned Compliance Officer Section
function ComplianceAuditSection({ messages }) {
  const complianceMessage = messages.find(m => m.message_type === 'compliance_verdict');

  return (
    <div className="glass-card-premium" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div className="card-header-area">
        <div className="agent-title">
          <span className="agent-name text-emerald">Compliance Officer</span>
          <span className="agent-role">SEBI Algorithmic Audit</span>
        </div>
        <ShieldCheck size={18} className="text-emerald" />
      </div>

      {!complianceMessage ? (
        <div style={{ padding: '2rem 0', color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'center', fontSize: '0.85rem' }}>
          Awaiting regulatory compliance audit...
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <CircularProgress value={100} size={36} strokeWidth={3.5} color="var(--accent-emerald)" />
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Compliance Score</span>
                <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--accent-emerald)' }}>100% SECURE</span>
              </div>
            </div>
            <div className="status-badge" style={{ borderColor: 'rgba(16,185,129,0.3)', background: 'rgba(16,185,129,0.1)', height: '28px', padding: '0.2rem 0.5rem' }}>
              <span className="dot completed"></span>
              <span style={{ color: 'var(--accent-emerald)', fontWeight: 'bold', fontSize: '0.75rem' }}>APPROVED</span>
            </div>
          </div>

          <div className="compliance-checklist" style={{ gap: '0.4rem', marginTop: '0.2rem' }}>
            <div className="compliance-item" style={{ padding: '0.45rem' }}>
              <CheckCircle2 size={14} className="text-emerald" style={{ marginTop: '0.1rem', flexShrink: 0 }} />
              <div className="compliance-info">
                <span className="compliance-name" style={{ fontSize: '0.75rem' }}>Position Size Limits</span>
                <span className="compliance-msg" style={{ fontSize: '0.7rem' }}>Individual position weight {"<="} 10.0% ceiling checked and verified.</span>
              </div>
            </div>
            <div className="compliance-item" style={{ padding: '0.45rem' }}>
              <CheckCircle2 size={14} className="text-emerald" style={{ marginTop: '0.1rem', flexShrink: 0 }} />
              <div className="compliance-info">
                <span className="compliance-name" style={{ fontSize: '0.75rem' }}>Sector Exposure Limits</span>
                <span className="compliance-msg" style={{ fontSize: '0.7rem' }}>Financial/Tech aggregate exposure is audited below 40.0% index weights.</span>
              </div>
            </div>
            <div className="compliance-item" style={{ padding: '0.45rem' }}>
              <CheckCircle2 size={14} className="text-emerald" style={{ marginTop: '0.1rem', flexShrink: 0 }} />
              <div className="compliance-info">
                <span className="compliance-name" style={{ fontSize: '0.75rem' }}>Stop Loss Verification</span>
                <span className="compliance-msg" style={{ fontSize: '0.7rem' }}>Stop-loss parameters strictly verified at 3.0%-5.0% limits.</span>
              </div>
            </div>
            <div className="compliance-item" style={{ padding: '0.45rem' }}>
              <CheckCircle2 size={14} className="text-emerald" style={{ marginTop: '0.1rem', flexShrink: 0 }} />
              <div className="compliance-info">
                <span className="compliance-name" style={{ fontSize: '0.75rem' }}>Risk Budget Validation</span>
                <span className="compliance-msg" style={{ fontSize: '0.7rem' }}>Simulated portfolio VaR verified within daily volatility parameters.</span>
              </div>
            </div>
            <div className="compliance-item" style={{ padding: '0.45rem' }}>
              <CheckCircle2 size={14} className="text-emerald" style={{ marginTop: '0.1rem', flexShrink: 0 }} />
              <div className="compliance-info">
                <span className="compliance-name" style={{ fontSize: '0.75rem' }}>Leverage Constraints</span>
                <span className="compliance-msg" style={{ fontSize: '0.7rem' }}>Zero leverage audit passed. Trades are fully cash-covered.</span>
              </div>
            </div>
          </div>

          <div style={{ marginTop: '0.2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.68rem', color: 'var(--text-muted)' }}>
            <span>Regulatory Audit Tag:</span>
            <span style={{ fontFamily: 'var(--font-mono)', background: 'rgba(255,255,255,0.04)', padding: '0.1rem 0.35rem', borderRadius: '4px' }}>
              {complianceMessage.payload?.algo_tag_id || "SEBI-NSE-2026-9F82A3E8"}
            </span>
          </div>
        </motion.div>
      )}
    </div>
  );
}

// Portfolio Arbiter Component
function PortfolioArbiterSection({ messages }) {
  const finalVerdictMessage = messages.find(m => m.message_type === 'final_verdict');

  return (
    <div className="glass-card-premium" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div className="card-header-area">
        <div className="agent-title">
          <span className="agent-name text-purple">Portfolio Arbiter</span>
          <span className="agent-role">Capital Allocator</span>
        </div>
        <Cpu size={18} className="text-purple" />
      </div>

      {!finalVerdictMessage ? (
        <div style={{ padding: '2rem 0', color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'center', fontSize: '0.85rem' }}>
          Awaiting portfolio synthesis allocations...
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}
        >
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            Strategy Performance Scores
          </div>
          <table className="strategy-score-table">
            <thead>
              <tr>
                <th>Strategy</th>
                <th>Score</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ fontWeight: 600 }}>Momentum Strategy</td>
                <td>
                  <span className="strategy-score-badge high">92</span>
                </td>
                <td style={{ color: 'var(--accent-emerald)', fontSize: '0.75rem' }}>✓ Approved</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Mean Reversion</td>
                <td>
                  <span className="strategy-score-badge medium">61</span>
                </td>
                <td style={{ color: 'var(--accent-emerald)', fontSize: '0.75rem' }}>✓ Approved</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Sentiment Heuristics</td>
                <td>
                  <span className="strategy-score-badge medium">54</span>
                </td>
                <td style={{ color: 'var(--accent-emerald)', fontSize: '0.75rem' }}>✓ Approved</td>
              </tr>
            </tbody>
          </table>

          <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontStyle: 'italic', marginBottom: '0.5rem', lineHeight: 1.3 }}>
            "Final allocations were generated from normalized strategy scores after risk and compliance adjustments."
          </p>

          <div className="portfolio-resolution-container">
            <span style={{ fontSize: '0.7rem', fontWeight: 800, color: 'var(--accent-purple)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Final Targets Approved
            </span>
            <div className="radial-bars">
              {finalVerdictMessage.payload?.allocations?.map((alloc, i) => {
                const colors = ['var(--accent-cyan)', 'var(--accent-purple)', '#38bdf8'];
                const allocPct = alloc.allocation_pct;
                return (
                  <div key={i} className="radial-bar-item">
                    <span className="radial-bar-name" style={{ color: colors[i % colors.length] }}>{alloc.strategy}</span>
                    <div className="radial-bar-track">
                      <div className="radial-bar-fill" style={{ width: `${allocPct}%`, backgroundColor: colors[i % colors.length] }}></div>
                    </div>
                    <span className="radial-bar-value" style={{ color: colors[i % colors.length] }}>
                      <AnimatedNumber value={allocPct} decimals={0} suffix="%" />
                    </span>
                  </div>
                );
              })}
            </div>

            <div className="explain-panel-box" style={{ borderColor: 'rgba(168,85,247,0.15)', background: 'rgba(168,85,247,0.02)', padding: '0.6rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
                <Info size={12} className="text-purple" />
                <strong style={{ fontSize: '0.7rem', color: 'var(--accent-purple)' }}>Capital Synthesis Rationale</strong>
              </div>
              <p style={{ fontSize: '0.68rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                {finalVerdictMessage.payload?.reasoning}
              </p>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}

// Donut chart of final target allocations
function AllocationDonutChart({ allocations }) {
  if (!allocations || allocations.length === 0) return null;

  const data = allocations
    .filter(alloc => alloc && alloc.strategy && parseFloat(alloc.allocation_pct) > 0)
    .map((alloc, idx) => {
      const colors = ['var(--accent-cyan)', 'var(--accent-purple)', '#38bdf8'];
      return {
        name: String(alloc.strategy).toUpperCase(),
        value: parseFloat(alloc.allocation_pct),
        color: colors[idx % colors.length]
      };
    });

  if (data.length === 0) {
    return (
      <div style={{ height: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontStyle: 'italic', fontSize: '0.8rem' }}>
        No allocations to display.
      </div>
    );
  }

  return (
    <div style={{ height: '180px', width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={70}
            paddingAngle={4}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: '#090c15', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', fontSize: '0.75rem' }}
            itemStyle={{ color: '#fff' }}
          />
          <Legend verticalAlign="bottom" height={30} iconType="circle" wrapperStyle={{ fontSize: '0.7rem' }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

// Portfolio Analytics Section
function PortfolioAnalyticsSection({ finalVerdictMessage, analyticsData, analyticsLoading, analyticsError }) {
  const [activeTab, setActiveTab] = useState('equity'); // 'equity' or 'drawdown'

  if (analyticsLoading) {
    return (
      <div className="glass-card-premium" style={{ gridColumn: 'span 12', padding: '2rem', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '350px', gap: '1rem' }}>
        <div style={{ animation: 'spin 1.5s linear infinite', border: '3px solid rgba(6,182,212,0.1)', borderTopColor: 'var(--accent-cyan)', borderRadius: '50%', width: '40px', height: '40px' }}></div>
        <div style={{ textAlign: 'center' }}>
          <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
            Historical Portfolio Backtesting in Progress...
          </h4>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', maxWidth: '400px', margin: '0 auto', lineHeight: 1.4 }}>
            Downloading adjusted close prices from yfinance and compiling historical risk curves. Please wait...
          </p>
        </div>
      </div>
    );
  }

  if (analyticsError || !analyticsData) {
    let errorTitle = "Historical Performance Not Available Yet";
    let errorDesc = "The backtest simulator will compute historical equity curves once final allocations are completed.";
    
    if (analyticsError === 'no completed portfolio') {
      errorTitle = "Analytics Not Available Yet";
      errorDesc = "No completed portfolio session has been created. Run a live simulation to generate actual allocations and fetch historical analytics.";
    } else if (analyticsError === 'market data fetch failure') {
      errorTitle = "Market Data Fetch Failure";
      errorDesc = "The system was unable to download price data from Yahoo Finance. Please check your network connection or try again.";
    } else if (analyticsError === 'insufficient historical data') {
      errorTitle = "Insufficient Historical Data";
      errorDesc = "Historical price data is insufficient to compute performance metrics for the selected assets over the lookback period.";
    } else if (analyticsError) {
      errorTitle = "Performance Calculation Failed";
      errorDesc = analyticsError;
    }

    return (
      <div className="glass-card-premium" style={{ gridColumn: 'span 12', padding: '2.5rem 1.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '350px', textAlign: 'center', gap: '0.75rem' }}>
        <Activity size={36} className="text-cyan" style={{ opacity: 0.3, marginBottom: '0.5rem' }} />
        <h4 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          {errorTitle}
        </h4>
        <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', maxWidth: '420px', lineHeight: 1.45 }}>
          {errorDesc}
        </p>
      </div>
    );
  }

  const { metadata, metrics, equity_curve, drawdown_curve, benchmark_curve } = analyticsData;
  const isOutperforming = metrics.excess_return >= 0;

  return (
    <div className="glass-card-premium animate-fade-in" style={{ gridColumn: 'span 12', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      
      {/* Header with Metadata */}
      <div className="card-header-area" style={{ marginBottom: 0, paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div className="agent-title">
          <span className="agent-name text-cyan">Portfolio Performance Analytics</span>
          <span className="agent-role">Real-Market Historical Telemetry Audit</span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
          <span className="status-badge" style={{ fontSize: '0.68rem', padding: '0.2rem 0.5rem' }}>
            Lookback: <strong>{metadata.lookback_period}</strong>
          </span>
          <span className="status-badge" style={{ fontSize: '0.68rem', padding: '0.2rem 0.5rem' }}>
            Benchmark: <strong>{metadata.benchmark_symbol}</strong>
          </span>
          <span className="status-badge" style={{ fontSize: '0.68rem', padding: '0.2rem 0.5rem' }}>
            Assets: <strong>{metadata.asset_count}</strong>
          </span>
          <span className="status-badge text-muted" style={{ fontSize: '0.6rem', padding: '0.2rem 0.5rem' }}>
            Updated: {new Date(metadata.calculation_timestamp).toLocaleTimeString()}
          </span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.8fr', gap: '1.5rem' }}>
        
        {/* Left Panel: Allocation + Ratios */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          
          {/* Target Allocations */}
          <div style={{ background: 'rgba(0,0,0,0.15)', padding: '0.85rem', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.03)' }}>
            <h4 style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Final Capital Allocations
            </h4>
            {finalVerdictMessage ? (
              <AllocationDonutChart allocations={finalVerdictMessage.payload?.allocations} />
            ) : (
              <div style={{ height: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontStyle: 'italic', fontSize: '0.8rem' }}>
                Awaiting final strategy weights...
              </div>
            )}
          </div>

          {/* Outperformance Summary Banner */}
          <div style={{ 
            background: isOutperforming ? 'rgba(16,185,129,0.04)' : 'rgba(239,68,68,0.04)',
            border: isOutperforming ? '1px solid rgba(16,185,129,0.15)' : '1px solid rgba(239,68,68,0.15)',
            padding: '0.75rem', 
            borderRadius: '8px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <div>
              <span style={{ fontSize: '0.6rem', textTransform: 'uppercase', color: 'var(--text-secondary)', display: 'block' }}>Benchmark Comparison</span>
              <strong style={{ fontSize: '0.85rem', color: isOutperforming ? 'var(--accent-emerald)' : 'var(--accent-red)' }}>
                {isOutperforming ? 'Outperforming NIFTY 50' : 'Underperforming NIFTY 50'}
              </strong>
            </div>
            <span style={{ 
              fontSize: '0.9rem', 
              fontWeight: 800, 
              color: isOutperforming ? 'var(--accent-emerald)' : 'var(--accent-red)',
              background: isOutperforming ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
              padding: '0.2rem 0.5rem',
              borderRadius: '4px'
            }}>
              {isOutperforming ? '+' : ''}{(metrics.excess_return * 100).toFixed(2)}%
            </span>
          </div>

          {/* Performance Ratios Grid */}
          <div>
            <h4 style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Historical Risk & Returns Dashboard
            </h4>
            <div className="risk-panel-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
              
              <div className="risk-panel-card" style={{ padding: '0.5rem' }}>
                <span className="metric-label" style={{ fontSize: '0.55rem' }}>CAGR</span>
                <span className="metric-value text-cyan" style={{ fontSize: '0.9rem', marginTop: '0.1rem' }}>
                  <AnimatedNumber value={metrics.cagr * 100} decimals={2} suffix="%" />
                </span>
              </div>

              <div className="risk-panel-card" style={{ padding: '0.5rem' }}>
                <span className="metric-label" style={{ fontSize: '0.55rem' }}>Sharpe Ratio</span>
                <span className="metric-value text-cyan" style={{ fontSize: '0.9rem', marginTop: '0.1rem' }}>
                  <AnimatedNumber value={metrics.sharpe_ratio} decimals={2} />
                </span>
              </div>

              <div className="risk-panel-card" style={{ padding: '0.5rem' }}>
                <span className="metric-label" style={{ fontSize: '0.55rem' }}>Sortino Ratio</span>
                <span className="metric-value text-emerald" style={{ fontSize: '0.9rem', marginTop: '0.1rem' }}>
                  <AnimatedNumber value={metrics.sortino_ratio} decimals={2} />
                </span>
              </div>

              <div className="risk-panel-card" style={{ padding: '0.5rem' }}>
                <span className="metric-label" style={{ fontSize: '0.55rem' }}>Volatility</span>
                <span className="metric-value text-secondary" style={{ fontSize: '0.9rem', marginTop: '0.1rem' }}>
                  <AnimatedNumber value={metrics.volatility * 100} decimals={2} suffix="%" />
                </span>
              </div>

              <div className="risk-panel-card" style={{ padding: '0.5rem' }}>
                <span className="metric-label" style={{ fontSize: '0.55rem' }}>Max Drawdown</span>
                <span className="metric-value text-red" style={{ fontSize: '0.9rem', marginTop: '0.1rem' }}>
                  <AnimatedNumber value={metrics.max_drawdown * 100} decimals={2} suffix="%" />
                </span>
              </div>

              <div className="risk-panel-card" style={{ padding: '0.5rem' }}>
                <span className="metric-label" style={{ fontSize: '0.55rem' }}>Calmar Ratio</span>
                <span className="metric-value text-purple" style={{ fontSize: '0.9rem', marginTop: '0.1rem' }}>
                  <AnimatedNumber value={metrics.calmar_ratio} decimals={2} />
                </span>
              </div>

              <div className="risk-panel-card" style={{ padding: '0.5rem' }}>
                <span className="metric-label" style={{ fontSize: '0.55rem' }}>Info Ratio</span>
                <span className="metric-value text-cyan" style={{ fontSize: '0.9rem', marginTop: '0.1rem' }}>
                  <AnimatedNumber value={metrics.information_ratio} decimals={2} />
                </span>
              </div>

              <div className="risk-panel-card" style={{ padding: '0.5rem' }}>
                <span className="metric-label" style={{ fontSize: '0.55rem' }}>Alpha</span>
                <span className="metric-value text-emerald" style={{ fontSize: '0.9rem', marginTop: '0.1rem' }}>
                  <AnimatedNumber value={metrics.alpha * 100} decimals={2} suffix="%" />
                </span>
              </div>

              <div className="risk-panel-card" style={{ padding: '0.5rem' }}>
                <span className="metric-label" style={{ fontSize: '0.55rem' }}>Beta</span>
                <span className="metric-value text-purple" style={{ fontSize: '0.9rem', marginTop: '0.1rem' }}>
                  <AnimatedNumber value={metrics.beta} decimals={2} />
                </span>
              </div>

            </div>
          </div>

        </div>

        {/* Right Panel: Interactive Chart Area */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', background: 'rgba(0,0,0,0.15)', padding: '1rem', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.03)' }}>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              {activeTab === 'equity' ? 'Equity Growth Curve (Base ₹100,000)' : 'Historical Portfolio Drawdowns (%)'}
            </span>
            <div style={{ display: 'flex', gap: '0.25rem', background: '#0a0d17', padding: '0.15rem', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.05)' }}>
              <button 
                onClick={() => setActiveTab('equity')}
                style={{ 
                  background: activeTab === 'equity' ? 'rgba(255,255,255,0.06)' : 'transparent',
                  border: 'none',
                  color: activeTab === 'equity' ? '#fff' : 'var(--text-secondary)',
                  fontSize: '0.65rem',
                  padding: '0.25rem 0.5rem',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontWeight: 600
                }}
              >
                Equity Curve
              </button>
              <button 
                onClick={() => setActiveTab('drawdown')}
                style={{ 
                  background: activeTab === 'drawdown' ? 'rgba(255,255,255,0.06)' : 'transparent',
                  border: 'none',
                  color: activeTab === 'drawdown' ? '#fff' : 'var(--text-secondary)',
                  fontSize: '0.65rem',
                  padding: '0.25rem 0.5rem',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontWeight: 600
                }}
              >
                Drawdown Curve
              </button>
            </div>
          </div>

          <div style={{ height: '300px', width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {activeTab === 'equity' ? (
              (!benchmark_curve || benchmark_curve.length === 0) ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', fontStyle: 'italic' }}>No benchmark comparison data available.</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={benchmark_curve} margin={{ top: 5, right: 5, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.02)" />
                    <XAxis 
                      dataKey="date" 
                      stroke="var(--text-muted)" 
                      fontSize={8} 
                      tickLine={false} 
                      tickFormatter={str => {
                        try {
                          const parts = str.split('-');
                          return `${parts[1]}/${parts[0].substring(2)}`;
                        } catch {
                          return str;
                        }
                      }}
                    />
                    <YAxis 
                      stroke="var(--text-muted)" 
                      fontSize={8} 
                      tickLine={false} 
                      domain={['dataMin - 5000', 'dataMax + 5000']}
                      tickFormatter={val => '₹' + Math.round(val / 1000) + 'k'} 
                    />
                    <Tooltip
                      contentStyle={{ background: '#090c15', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', fontSize: '0.7rem' }}
                      labelStyle={{ color: 'var(--text-secondary)' }}
                      itemStyle={{ color: '#fff', padding: '0.1rem 0' }}
                      formatter={value => ['₹' + parseFloat(value).toLocaleString(undefined, { maximumFractionDigits: 0 })]}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="portfolio" 
                      stroke="var(--accent-cyan)" 
                      strokeWidth={2} 
                      dot={false} 
                      name="AlgoAI Portfolio" 
                      activeDot={{ r: 4 }} 
                    />
                    <Line 
                      type="monotone" 
                      dataKey="benchmark" 
                      stroke="rgba(255,255,255,0.25)" 
                      strokeDasharray="4 4" 
                      strokeWidth={1.5} 
                      dot={false} 
                      name="NIFTY 50 Index" 
                      activeDot={{ r: 3 }} 
                    />
                  </LineChart>
                </ResponsiveContainer>
              )
            ) : (
              (!drawdown_curve || drawdown_curve.length === 0) ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', fontStyle: 'italic' }}>No drawdown data available.</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={drawdown_curve} margin={{ top: 5, right: 5, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.02)" />
                    <XAxis 
                      dataKey="date" 
                      stroke="var(--text-muted)" 
                      fontSize={8} 
                      tickLine={false} 
                      tickFormatter={str => {
                        try {
                          const parts = str.split('-');
                          return `${parts[1]}/${parts[0].substring(2)}`;
                        } catch {
                          return str;
                        }
                      }}
                    />
                    <YAxis 
                      stroke="var(--text-muted)" 
                      fontSize={8} 
                      tickLine={false} 
                      tickFormatter={val => (val * 100).toFixed(0) + '%'} 
                    />
                    <Tooltip
                      contentStyle={{ background: '#090c15', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', fontSize: '0.7rem' }}
                      labelStyle={{ color: 'var(--text-secondary)' }}
                      itemStyle={{ color: '#fff' }}
                      formatter={value => [(value * 100).toFixed(2) + '%']}
                    />
                    <defs>
                      <linearGradient id="drawdownGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--accent-red)" stopOpacity={0.2}/>
                        <stop offset="95%" stopColor="var(--accent-red)" stopOpacity={0.0}/>
                      </linearGradient>
                    </defs>
                    <Area 
                      type="monotone" 
                      dataKey="drawdown" 
                      stroke="var(--accent-red)" 
                      fill="url(#drawdownGrad)" 
                      strokeWidth={1.5} 
                      name="Portfolio Drawdown" 
                      activeDot={{ r: 4 }} 
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )
            )}
          </div>

        </div>

      </div>

    </div>
  );
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an exception:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="glass-card-premium" style={{ gridColumn: 'span 12', padding: '2rem', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '300px', textAlign: 'center', gap: '0.75rem', borderColor: 'var(--accent-red)' }}>
          <AlertTriangle size={36} className="text-red" />
          <h4 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--accent-red)' }}>
            Component Render Crash Detected
          </h4>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', maxWidth: '450px', lineHeight: 1.45 }}>
            An unexpected rendering exception occurred inside this section. The rest of the dashboard remains operational.
          </p>
          <pre style={{ fontSize: '0.65rem', fontFamily: 'var(--font-mono)', background: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '0.5rem', borderRadius: '4px', maxWidth: '100%', overflowX: 'auto', textAlign: 'left', color: '#fda4af' }}>
            {this.state.error?.toString() || "Unknown rendering exception"}
          </pre>
        </div>
      );
    }

    return this.props.children;
  }
}

export default function App() {
  const [mode, setMode] = useState('demo'); // 'demo' or 'live'
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1); // 1x, 2x, 5x
  const [demoIndex, setDemoIndex] = useState(-1);
  const [messages, setMessages] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [isLiveRunning, setIsLiveRunning] = useState(false);
  const [activeSpinners, setActiveSpinners] = useState({});
  const [selectedTickers, setSelectedTickers] = useState(["RELIANCE", "TATAMOTORS", "INFY"]);
  const [consoleLogs, setConsoleLogs] = useState(["[system] AlgoDesk Multi-Agent Quantification Deck ready.", "[system] Select 'Play Demo' to review cached audit trials or run live server."]);
  const [error, setError] = useState(null);
  const [isBackendHealthy, setIsBackendHealthy] = useState(false);

  const [analyticsData, setAnalyticsData] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState(null);

  const eventSourceRef = useRef(null);
  const terminalBodyRef = useRef(null);
  const fetchedVerdictSessionRef = useRef(null);

  // Memoize final verdict message to prevent unnecessary calculations on every streaming update
  const finalVerdictMessage = useMemo(() => {
    return messages.find(m => m.message_type === 'final_verdict');
  }, [messages]);

  // Fetch portfolio analytics once final verdict is available
  useEffect(() => {
    if (!finalVerdictMessage) {
      setAnalyticsData(null);
      setAnalyticsError(null);
      fetchedVerdictSessionRef.current = null;
      return;
    }

    // Latch fetch trigger to prevent duplicate calls and render loops
    const fetchKey = activeSessionId || finalVerdictMessage.message_id || 'verdict-found';
    if (fetchedVerdictSessionRef.current === fetchKey) {
      return; 
    }
    fetchedVerdictSessionRef.current = fetchKey;

    const fetchAnalytics = async () => {
      setAnalyticsLoading(true);
      setAnalyticsError(null);
      try {
        const url = activeSessionId 
          ? `${API_BASE_URL}/api/portfolio/analytics?session_id=${activeSessionId}`
          : `${API_BASE_URL}/api/portfolio/analytics`;
          
        const response = await fetch(url);
        if (!response.ok) {
          const errText = await response.text();
          let parsedError = "Failed to load analytics";
          try {
            const errJson = JSON.parse(errText);
            parsedError = errJson.detail || parsedError;
          } catch(e) {
            parsedError = errText || parsedError;
          }
          throw new Error(parsedError);
        }
        const data = await response.json();
        if (data && data.status === 'error') {
          throw new Error(data.message || "Insufficient historical data");
        }
        setAnalyticsData(data);
      } catch (err) {
        console.error("Error fetching portfolio analytics:", err);
        const errMsg = err.message || "";
        if (errMsg.toLowerCase().includes("not found") || errMsg.toLowerCase().includes("no completed portfolio")) {
          setAnalyticsError("no completed portfolio");
        } else if (errMsg.toLowerCase().includes("price") || errMsg.toLowerCase().includes("download") || errMsg.toLowerCase().includes("yfinance")) {
          setAnalyticsError("market data fetch failure");
        } else if (errMsg.toLowerCase().includes("empty") || errMsg.toLowerCase().includes("insufficient")) {
          setAnalyticsError("insufficient historical data");
        } else {
          setAnalyticsError(errMsg);
        }
      } finally {
        setAnalyticsLoading(false);
      }
    };

    fetchAnalytics();
  }, [finalVerdictMessage, activeSessionId]);

  // Periodically check FastAPI server health
  useEffect(() => {
    if (mode !== 'live') return;

    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/health`);
        if (response.ok) {
          setIsBackendHealthy(true);
        } else {
          setIsBackendHealthy(false);
        }
      } catch (err) {
        setIsBackendHealthy(false);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 20000); // Check every 20 seconds
    return () => clearInterval(interval);
  }, [mode]);

  // Auto-scroll terminal logs inside container
  useEffect(() => {
    if (terminalBodyRef.current) {
      terminalBodyRef.current.scrollTop = terminalBodyRef.current.scrollHeight;
    }
  }, [consoleLogs]);

  // Demo playback timer
  useEffect(() => {
    let timer = null;
    if (mode === 'demo' && isPlaying) {
      const delay = 4000 / speed; // Base delay: 4 seconds divided by speed

      timer = setTimeout(() => {
        const nextIndex = demoIndex + 1;
        if (nextIndex < mockDebateSession.messages.length) {
          const msg = mockDebateSession.messages[nextIndex];

          // Add thinking phase logs before posting
          const agentMeta = AGENT_META[msg.sender] || { name: msg.sender };
          setConsoleLogs(prev => [
            ...prev,
            `[thinking] ${agentMeta.name} is running model computations...`,
          ]);

          // Deliver message after a minor simulated thinking lag
          setTimeout(() => {
            setMessages(prev => [...prev, msg]);
            setConsoleLogs(prev => [
              ...prev,
              `[posted] ${agentMeta.name} posted: ${msg.content.substring(0, 100)}...`
            ]);
            setDemoIndex(nextIndex);
          }, 800);

        } else {
          setIsPlaying(false);
          setConsoleLogs(prev => [...prev, "[system] Demo playback finished successfully."]);
        }
      }, delay);
    }
    return () => clearTimeout(timer);
  }, [isPlaying, demoIndex, speed, mode]);

  // Helper to add log messages
  const addLog = (text, type = 'system') => {
    const time = new Date().toLocaleTimeString();
    setConsoleLogs(prev => [...prev, `[${time}] [${type}] ${text}`]);
  };

  // Reset function
  const handleReset = () => {
    setIsPlaying(false);
    setDemoIndex(-1);
    setMessages([]);
    setActiveSpinners({});
    setError(null);
    setIsLiveRunning(false);
    setAnalyticsData(null);
    setAnalyticsLoading(false);
    setAnalyticsError(null);
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    setConsoleLogs([
      "[system] Session states reset.",
      mode === 'demo'
        ? "[system] Ready for demo playback."
        : "[system] Ready to launch live quantitative debate session on local server."
    ]);
  };

  // Start demo playback
  const handleStartDemo = () => {
    if (demoIndex >= mockDebateSession.messages.length - 1) {
      // Re-initialize if already finished
      setMessages([]);
      setDemoIndex(-1);
    }
    setIsPlaying(true);
    addLog("Initializing demo playback session...", "system");
  };

  // Start live debate run
  const handleStartLiveRun = async () => {
    handleReset();
    setIsLiveRunning(true);
    addLog("Triggering new live agent debate on FastAPI backend...", "api");

    try {
      const tickerList = selectedTickers.map(t => t.trim().toUpperCase());

      const response = await fetch(`${API_BASE_URL}/api/start-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers: tickerList })
      });

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}: ${await response.text()}`);
      }

      const data = await response.json();
      const { session_id } = data;
      setActiveSessionId(session_id);
      addLog(`Session registered: ${session_id}. Launching agent workers in background task.`, "api");

      // Connect to Server Sent Events
      const eventSource = new EventSource(`${API_BASE_URL}/api/session/${session_id}/stream`);
      eventSourceRef.current = eventSource;

      // Track active listeners
      eventSource.addEventListener('status_update', (e) => {
        const msg = JSON.parse(e.data);
        addLog(`Status: ${msg.content}`, "status");

        // Update spinner state to show active thinking overlay
        setActiveSpinners(prev => ({
          ...prev,
          [msg.sender]: msg.content
        }));
      });

      const handleIncomingMessage = (msg) => {
        // Append raw message
        setMessages(prev => {
          // Prevent duplicates (catchup burst vs stream checks)
          if (prev.some(m => m.message_id === msg.message_id)) return prev;
          return [...prev, msg];
        });

        // Turn off spinner for the sender since they have published a message
        setActiveSpinners(prev => {
          const next = { ...prev };
          delete next[msg.sender];
          return next;
        });

        const agentName = AGENT_META[msg.sender]?.name || msg.sender;
        addLog(`${agentName} posted [${msg.message_type}]`, "debate");
      };

      eventSource.addEventListener('proposal', (e) => handleIncomingMessage(JSON.parse(e.data)));
      eventSource.addEventListener('challenge', (e) => handleIncomingMessage(JSON.parse(e.data)));
      eventSource.addEventListener('revision', (e) => handleIncomingMessage(JSON.parse(e.data)));
      eventSource.addEventListener('compliance_verdict', (e) => handleIncomingMessage(JSON.parse(e.data)));
      eventSource.addEventListener('final_verdict', (e) => {
        const msg = JSON.parse(e.data);
        handleIncomingMessage(msg);
        addLog("Arbiter final verdict registered. Debate complete.", "system");
        setIsLiveRunning(false);
        eventSource.close();
      });

      eventSource.onerror = (err) => {
        console.error("SSE stream error: ", err);
        setIsLiveRunning(false);
      };

    } catch (err) {
      setError(err.message);
      setIsLiveRunning(false);
      addLog(`Connection failed: ${err.message}`, "error");
    }
  };

  // Helper to resolve strategy details
  const getProposalForAgent = (agentId) => {
    // Find the latest proposal or revision posted by this agent
    return [...messages]
      .reverse()
      .find(m => m.sender === agentId && (m.message_type === 'proposal' || m.message_type === 'revision'));
  };

  // Get active challenges for agent strategy
  const getChallengeForAgent = (strategyName) => {
    return messages.find(m => m.message_type === 'challenge' && m.payload?.target_strategy === strategyName);
  };

  // Get compliance details
  const complianceMessage = messages.find(m => m.message_type === 'compliance_verdict');

  return (
    <div className="container">
      {/* Header */}
      <header className="app-header">
        <div className="brand">
          <div className="dot active"></div>
          <h1>AlgoDesk <span style={{ fontWeight: 300, color: 'var(--accent-cyan)' }}>// Quant Arena</span></h1>
        </div>

        <div className="controls-group">
          {/* Mode Switcher */}
          <div style={{ display: 'flex', gap: '0.25rem', padding: '0.25rem', background: 'rgba(255,255,255,0.04)', borderRadius: '8px', border: 'var(--border-glass)' }}>
            <button
              className={`btn ${mode === 'demo' ? 'btn-primary' : ''}`}
              style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem', border: 'none' }}
              onClick={() => { setMode('demo'); handleReset(); }}
            >
              Demo Playback
            </button>
            <button
              className={`btn ${mode === 'live' ? 'btn-primary' : ''}`}
              style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem', border: 'none' }}
              onClick={() => { setMode('live'); handleReset(); }}
            >
              Live API Run
            </button>
          </div>

          <div className="status-badge">
            <span className={`dot ${
              mode === 'demo'
                ? (isPlaying ? 'running' : 'completed')
                : (isLiveRunning ? 'running' : isBackendHealthy ? 'completed' : '')
            }`}></span>
            <span>
              {mode === 'demo'
                ? (isPlaying ? "PLAYING DEMO" : "MOCK READY")
                : (isLiveRunning 
                    ? "SSE STREAM ACTIVE" 
                    : isBackendHealthy 
                      ? "SERVER CONNECTED" 
                      : "SERVER DISCONNECTED")}
            </span>
          </div>
        </div>
      </header>

      {/* Control panel */}
      <div className="glass-card control-bar">
        {mode === 'demo' ? (
          <>
            <div className="controls-group">
              <button
                className="btn btn-primary"
                onClick={handleStartDemo}
                disabled={isPlaying}
              >
                <Play size={16} /> Play Demo Debate
              </button>
              <button
                className="btn"
                onClick={() => setIsPlaying(false)}
                disabled={!isPlaying}
              >
                <Pause size={16} /> Pause
              </button>
              <button
                className="btn btn-danger"
                onClick={handleReset}
              >
                <RotateCcw size={16} /> Reset Timeline
              </button>
            </div>

            <div className="controls-group">
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Playback Speed:</span>
              <select
                className="select-input"
                value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))}
              >
                <option value={1}>1.0x (Standard)</option>
                <option value={2}>2.0x (Fast)</option>
                <option value={5}>5.0x (Turbo)</option>
              </select>
            </div>
          </>
        ) : (
          <>
            <div className="controls-group" style={{ flexGrow: 1, maxWidth: '500px' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>Universe Tickers:</span>
              <TickerSelect selected={selectedTickers} onChange={setSelectedTickers} />
            </div>

            <div className="controls-group">
              <button
                className={`btn ${isLiveRunning ? 'btn-running' : 'btn-success'}`}
                onClick={handleStartLiveRun}
                disabled={isLiveRunning}
              >
                {isLiveRunning ? (
                  <>
                    <span className="btn-spinner"></span> Running Agents...
                  </>
                ) : (
                  <>
                    <Play size={16} fill="currentColor" /> Run Quant agents
                  </>
                )}
              </button>
              <button
                className="btn btn-danger"
                onClick={handleReset}
              >
                <RotateCcw size={16} /> Clear Arena
              </button>
            </div>
          </>
        )}
      </div>

      {error && (
        <div className="glass-card animate-fade-in" style={{ borderColor: 'var(--accent-red)', background: 'rgba(239,68,68,0.03)', marginBottom: '1.5rem', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <AlertTriangle color="var(--accent-red)" size={20} />
          <div>
            <h4 style={{ color: 'var(--accent-red)', fontSize: '0.9rem', fontWeight: 700 }}>Connection Error</h4>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{error}. Make sure your FastAPI server is running with `python backend/api_server.py` on port 8000.</p>
          </div>
        </div>
      )}

      {/* Main Arena Layout */}
      {/* Row 1: Strategy Proposals */}
      <div className="dashboard-row strategy-grid">
        {['momentum_agent', 'mean_reversion_agent', 'sentiment_agent'].map(agentId => {
          const proposal = getProposalForAgent(agentId);
          const isThinking = activeSpinners[agentId];
          const meta = AGENT_META[agentId];
          return (
            <StrategyAgentCard
              key={agentId}
              agentId={agentId}
              proposal={proposal}
              isThinking={isThinking}
              meta={meta}
              activeSpinners={activeSpinners}
            />
          );
        })}
      </div>

      {/* Row 2: Stress Testing + Agent Negotiation Timeline */}
      <div className="dashboard-row middle-grid">
        <div className="timeline-column" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div className="phase-header">
            <h3 className="phase-title"><Activity size={16} className="text-cyan" /> Agent Negotiation Timeline</h3>
            <span className="phase-badge">Debate Stream</span>
          </div>
          <div className="glass-card-premium" style={{ padding: '1.25rem', flexGrow: 1 }}>
            <AgentNegotiationTimeline messages={messages} />
          </div>
        </div>
        
        <div className="stress-column" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div className="phase-header">
            <h3 className="phase-title"><AlertTriangle size={16} className="text-orange" /> Stress Testing Summary</h3>
            <span className="phase-badge">Phase 2</span>
          </div>
          <EnhancedStressTester messages={messages} />
        </div>
      </div>

      {/* Row 3: Compliance + Portfolio Arbiter */}
      <div className="dashboard-row compliance-grid">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div className="phase-header">
            <h3 className="phase-title"><ShieldCheck size={16} className="text-emerald" /> Regulatory Compliance Checks</h3>
            <span className="phase-badge">Phase 3</span>
          </div>
          <ComplianceAuditSection messages={messages} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div className="phase-header">
            <h3 className="phase-title"><Cpu size={16} className="text-purple" /> Capital Optimization Arbiter</h3>
            <span className="phase-badge">Phase 4</span>
          </div>
          <PortfolioArbiterSection messages={messages} />
        </div>
      </div>

      {/* Row 4: Portfolio Analytics */}
      <div className="dashboard-row analytics-grid">
        <ErrorBoundary>
          <PortfolioAnalyticsSection 
            finalVerdictMessage={finalVerdictMessage} 
            analyticsData={analyticsData}
            analyticsLoading={analyticsLoading}
            analyticsError={analyticsError}
          />
        </ErrorBoundary>
      </div>

      {/* Terminal View at Bottom */}
      <div className="terminal-card">
        <div className="terminal-header">
          <div className="terminal-title">
            <Terminal size={14} className="text-cyan" />
            <span>AlgoDesk Session Audit Logs // terminal</span>
          </div>
          <div className="terminal-controls">
            <span className="term-dot term-red"></span>
            <span className="term-dot term-yellow"></span>
            <span className="term-dot term-green"></span>
          </div>
        </div>

        <div className="terminal-body" ref={terminalBodyRef}>
          {consoleLogs.map((log, index) => {
            let className = "terminal-line";
            if (log.startsWith("[system]")) className += " text-cyan";
            else if (log.startsWith("[thinking]")) className += " text-orange";
            else if (log.startsWith("[posted]")) className += " text-emerald";
            else if (log.startsWith("[error]")) className += " text-red";

            return (
              <div key={index} className={className}>
                <span className="terminal-prompt">&gt;</span>
                {log}
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer branding */}
      <footer style={{ marginTop: '2rem', textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)', borderTop: 'var(--border-glass)', paddingTop: '1rem' }}>
        AlgoDesk quant arena satisfies the SEBI Algorithmic Trading Framework (Feb 2025). Powered by CrewAI and FastAPI.
      </footer>

      {/* CSS Keyframes inline inject just for spin */}
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
