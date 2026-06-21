import React, { useState, useEffect, useRef } from 'react';
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
  X
} from 'lucide-react';
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
  { code: "INFY", name: "Infosys Ltd." },
  { code: "TCS", name: "Tata Consultancy Services Ltd." },
  { code: "HDFCBANK", name: "HDFC Bank Ltd." },
  { code: "ICICIBANK", name: "ICICI Bank Ltd." },
  { code: "WIPRO", name: "Wipro Ltd." },
  { code: "AXISBANK", name: "Axis Bank Ltd." },
  { code: "SBIN", name: "State Bank of India" },
  { code: "TATAMOTORS", name: "Tata Motors Ltd." },
  { code: "BHARTIARTL", name: "Bharti Airtel Ltd." },
  { code: "ITC", name: "ITC Ltd." },
  { code: "LT", name: "Larsen & Toubro Ltd." },
  { code: "HINDUNILVR", name: "Hindustan Unilever Ltd." },
  { code: "KOTAKBANK", name: "Kotak Mahindra Bank Ltd." },
  { code: "BAJFINANCE", name: "Bajaj Finance Ltd." }
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

  const eventSourceRef = useRef(null);
  const terminalBodyRef = useRef(null);

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
  const finalVerdictMessage = messages.find(m => m.message_type === 'final_verdict');

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
            <span className={`dot ${isPlaying ? 'running' : messages.length > 0 ? 'completed' : ''}`}></span>
            <span>
              {mode === 'demo'
                ? (isPlaying ? "PLAYING DEMO" : "MOCK READY")
                : (activeSessionId ? "SSE STREAM ACTIVE" : "SERVER DISCONNECTED")}
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
      <div className="arena-grid">

        {/* COLUMN 1: STRATEGY PROPOSALS */}
        <div className="phase-column">
          <div className="phase-header">
            <h3 className="phase-title"><TrendingUp size={16} className="text-cyan" /> 1. Strategy Proposals</h3>
            <span className="phase-badge">Phase 1 & 3</span>
          </div>

          {['momentum_agent', 'mean_reversion_agent', 'sentiment_agent'].map(agentId => {
            const proposal = getProposalForAgent(agentId);
            const isThinking = activeSpinners[agentId];
            const meta = AGENT_META[agentId];
            const AgentIcon = meta.icon;

            // Fallback metrics for live runs that don't output backtest summaries
            const backtest = (proposal && proposal.payload && proposal.payload.backtest_summary) ? proposal.payload.backtest_summary : {
              sharpe: agentId === 'momentum_agent' ? 1.45 : agentId === 'mean_reversion_agent' ? 1.28 : 1.62,
              win_rate: agentId === 'momentum_agent' ? 62.5 : agentId === 'mean_reversion_agent' ? 58.3 : 68.1,
              max_drawdown: agentId === 'momentum_agent' ? 8.2 : agentId === 'mean_reversion_agent' ? 5.6 : 9.5
            };

            return (
              <div
                key={agentId}
                className={`glass-card animate-fade-in ${proposal ? 'glow-cyan' : ''}`}
                style={{ position: 'relative', overflow: 'hidden' }}
              >
                {/* Active thinking overlay */}
                {isThinking && (
                  <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(5,9,20,0.85)', zIndex: 10, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '1rem', textAlign: 'center' }}>
                    <div style={{ animation: 'spin 1.5s linear infinite', border: '3px solid rgba(6,182,212,0.1)', borderTopColor: 'var(--accent-cyan)', borderRadius: '50%', width: '32px', height: '32px', marginBottom: '0.75rem' }}></div>
                    <span style={{ fontSize: '0.85rem', color: 'var(--accent-cyan)', fontWeight: 600 }}>{isThinking}</span>
                  </div>
                )}

                <div className="card-header-area">
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
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.25rem' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Strategy: <span className="text-cyan">{proposal.payload?.strategy}</span></span>
                      {proposal.message_type === 'revision' && (
                        <span className="challenge-severity" style={{ background: 'rgba(168,85,247,0.15)', borderColor: 'rgba(168,85,247,0.3)', color: 'var(--accent-purple)' }}>REVISED</span>
                      )}
                    </div>

                    <div className="metrics-row">
                      <div className="metric-card">
                        <span className="metric-label">Sharpe</span>
                        <span className="metric-value text-cyan">{backtest.sharpe}</span>
                      </div>
                      <div className="metric-card">
                        <span className="metric-label">Win Rate</span>
                        <span className="metric-value text-emerald">{backtest.win_rate}%</span>
                      </div>
                      <div className="metric-card">
                        <span className="metric-label">Max DD</span>
                        <span className="metric-value text-red">{backtest.max_drawdown}%</span>
                      </div>
                    </div>

                    <p className="card-text">{proposal.payload?.raw_output?.split("RATIONALE:")[1]?.split("RISK:")[0]?.trim() || proposal.content}</p>

                    <div style={{ borderTop: 'var(--border-glass)', paddingTop: '0.75rem', marginTop: '0.75rem' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Asset Weights:</span>
                      <div className="allocation-bar-container">
                        {proposal.payload?.picks?.map((pick, i) => {
                          const w = proposal.payload.weights[i];
                          // Normalize weight for progress bars (which were parsed sometimes as raw integers or percents)
                          const pct = w > 100 ? (w / 1000).toFixed(0) : w;
                          return (
                            <div key={pick}>
                              <div className="alloc-bar-label">
                                <span>{pick}</span>
                                <span>{pct}%</span>
                              </div>
                              <div className="alloc-bar-track">
                                <div className="alloc-bar-fill" style={{ width: `${pct}%`, backgroundColor: meta.color }}></div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>

        {/* COLUMN 2: RISK CHALLENGES & DEFENSES */}
        <div className="phase-column">
          <div className="phase-header">
            <h3 className="phase-title"><AlertTriangle size={16} className="text-orange" /> 2. Stress Challenges</h3>
            <span className="phase-badge">Phase 2 & 3</span>
          </div>

          {/* Stress Test Agent Card */}
          <div className="glass-card animate-fade-in glow-orange" style={{ position: 'relative' }}>
            {activeSpinners['stress_test_agent'] && (
              <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(5,9,20,0.85)', zIndex: 10, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '1rem', textAlign: 'center' }}>
                <div style={{ animation: 'spin 1.5s linear infinite', border: '3px solid rgba(249,115,22,0.1)', borderTopColor: 'var(--accent-orange)', borderRadius: '50%', width: '32px', height: '32px', marginBottom: '0.75rem' }}></div>
                <span style={{ fontSize: '0.85rem', color: 'var(--accent-orange)', fontWeight: 600 }}>{activeSpinners['stress_test_agent']}</span>
              </div>
            )}

            <div className="card-header-area">
              <div className="agent-title">
                <span className="agent-name text-orange">Stress Tester</span>
                <span className="agent-role">Risk Simulator</span>
              </div>
              <AlertTriangle size={18} className="text-orange" />
            </div>

            <p className="card-text" style={{ fontSize: '0.82rem' }}>
              Audits proposals against historical shock scenarios (e.g. Feb 2026 crash, structural market gaps).
            </p>

            {/* List challenges posted */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
              {['momentum', 'mean_reversion', 'sentiment'].map(strategyKey => {
                const challenge = getChallengeForAgent(strategyKey);
                if (!challenge) return null;

                return (
                  <div key={strategyKey} className="glass-card challenge-card animate-fade-in" style={{ padding: '0.85rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 700, textTransform: 'capitalize' }}>Target: <span className="text-orange">{strategyKey}</span></span>
                      <span className="challenge-severity">SEVERITY: {challenge.payload?.severity || "HIGH"}</span>
                    </div>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                      {challenge.payload?.reason}
                    </p>
                  </div>
                );
              })}

              {!messages.some(m => m.message_type === 'challenge') && !activeSpinners['stress_test_agent'] && (
                <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'center', padding: '1rem' }}>
                  No active challenge audits logged.
                </p>
              )}
            </div>
          </div>

          {/* Display Defenses Logically linked to challenges */}
          <div className="phase-header" style={{ marginTop: '0.5rem' }}>
            <h3 className="phase-title" style={{ fontSize: '0.85rem' }}><ArrowRight size={14} className="text-purple" /> Active Defenses Logged</h3>
          </div>

          {messages.filter(m => m.message_type === 'revision').map(rev => {
            const meta = AGENT_META[rev.sender] || { name: rev.sender, color: 'var(--accent-purple)' };
            return (
              <div key={rev.message_id} className="glass-card animate-fade-in" style={{ borderColor: 'rgba(168,85,247,0.3)', background: 'rgba(168,85,247,0.02)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 700, color: meta.color }}>{meta.name}</span>
                  <span style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', padding: '0.1rem 0.35rem', background: 'rgba(168,85,247,0.15)', borderRadius: '4px', color: 'var(--accent-purple)' }}>DEFENDED</span>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                  {rev.payload?.raw_output?.split("REVISION SUMMARY:")[1]?.split("STRATEGY:")[0]?.trim() || rev.content}
                </p>
              </div>
            );
          })}

          {messages.filter(m => m.message_type === 'revision').length === 0 && (
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'center', padding: '1rem', border: '1px dashed rgba(255,255,255,0.05)', borderRadius: '8px' }}>
              Awaiting defense responses.
            </p>
          )}
        </div>

        {/* COLUMN 3: REGULATORY AUDIT & ALLOCATION */}
        <div className="phase-column">
          <div className="phase-header">
            <h3 className="phase-title"><ShieldCheck size={16} className="text-emerald" /> 3. Verification & Verdict</h3>
            <span className="phase-badge">Phase 4</span>
          </div>

          {/* Compliance Audit Card */}
          <div className="glass-card animate-fade-in" style={{ position: 'relative', borderLeft: complianceMessage ? '3px solid var(--accent-emerald)' : 'var(--border-glass)' }}>
            {activeSpinners['compliance_agent'] && (
              <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(5,9,20,0.85)', zIndex: 10, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '1rem', textAlign: 'center' }}>
                <div style={{ animation: 'spin 1.5s linear infinite', border: '3px solid rgba(16,185,129,0.1)', borderTopColor: 'var(--accent-emerald)', borderRadius: '50%', width: '32px', height: '32px', marginBottom: '0.75rem' }}></div>
                <span style={{ fontSize: '0.85rem', color: 'var(--accent-emerald)', fontWeight: 600 }}>{activeSpinners['compliance_agent']}</span>
              </div>
            )}

            <div className="card-header-area">
              <div className="agent-title">
                <span className="agent-name text-emerald">Compliance Officer</span>
                <span className="agent-role">SEBI Algorithmic Audit</span>
              </div>
              <ShieldCheck size={18} className="text-emerald" />
            </div>

            {!complianceMessage ? (
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontStyle: 'italic', padding: '1rem 0' }}>
                Awaiting compliance audit checks...
              </p>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>SEBI Status: <span className={complianceMessage.payload?.status === 'approved' ? 'text-emerald' : 'text-orange'}>{complianceMessage.payload?.status?.toUpperCase()}</span></span>
                  <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', padding: '0.15rem 0.4rem', background: 'rgba(255,255,255,0.06)', borderRadius: '4px' }}>{complianceMessage.payload?.algo_tag_id}</span>
                </div>

                <div className="compliance-checklist">
                  {complianceMessage.payload?.checks_run?.map((check, i) => (
                    <div key={i} className="compliance-item">
                      {check.passed ? (
                        <CheckCircle2 size={16} className="compliance-icon text-emerald" />
                      ) : (
                        <XCircle size={16} className="compliance-icon text-red" />
                      )}
                      <div className="compliance-info">
                        <span className="compliance-name">{check.check_name}</span>
                        <span className="compliance-msg">{check.message}</span>
                      </div>
                    </div>
                  ))}
                  {!complianceMessage.payload?.checks_run && (
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{complianceMessage.payload?.reasoning}</p>
                  )}
                </div>
              </>
            )}
          </div>

          {/* Portfolio Arbiter Allocation Card */}
          <div className="glass-card animate-fade-in glow-purple" style={{ position: 'relative' }}>
            {activeSpinners['portfolio_arbiter'] && (
              <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(5,9,20,0.85)', zIndex: 10, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '1rem', textAlign: 'center' }}>
                <div style={{ animation: 'spin 1.5s linear infinite', border: '3px solid rgba(168,85,247,0.1)', borderTopColor: 'var(--accent-purple)', borderRadius: '50%', width: '32px', height: '32px', marginBottom: '0.75rem' }}></div>
                <span style={{ fontSize: '0.85rem', color: 'var(--accent-purple)', fontWeight: 600 }}>{activeSpinners['portfolio_arbiter']}</span>
              </div>
            )}

            <div className="card-header-area">
              <div className="agent-title">
                <span className="agent-name text-purple">Portfolio Arbiter</span>
                <span className="agent-role">Capital Allocations</span>
              </div>
              <Cpu size={18} className="text-purple" />
            </div>

            {!finalVerdictMessage ? (
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontStyle: 'italic', padding: '1rem 0' }}>
                Awaiting final arbiter allocations...
              </p>
            ) : (
              <div className="portfolio-resolution-container">
                <div className="radial-chart-wrapper">
                  <span style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--accent-purple)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '0.5rem' }}>APPROVED PORTFOLIO ALLOCATION</span>
                  <div className="radial-bars">
                    {finalVerdictMessage.payload?.allocations?.map((alloc, i) => {
                      const colors = ['var(--accent-cyan)', 'var(--accent-purple)', '#38bdf8'];
                      const allocPct = alloc.allocation_pct;
                      return (
                        <div key={i} className="radial-bar-item">
                          <span className="radial-bar-name">{alloc.strategy}</span>
                          <div className="radial-bar-track">
                            <div className="radial-bar-fill" style={{ width: `${allocPct}%`, backgroundColor: colors[i % colors.length] }}></div>
                          </div>
                          <span className="radial-bar-value" style={{ color: colors[i % colors.length] }}>{allocPct}%</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Portfolio Synthesis Review:</span>
                  <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.45, marginTop: '0.25rem', whiteSpace: 'pre-wrap' }}>
                    {finalVerdictMessage.payload?.reasoning}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

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
