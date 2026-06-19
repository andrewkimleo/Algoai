# 📈 AlgoDesk // Multi-Agent Quant Arena

AlgoDesk is a premium, high-fidelity quantitative multi-agent debate arena and risk arbitration dashboard. It simulates a collaborative, multi-stage trading board meeting where AI agents pitch strategies, stress-test each other's ideas, audit against regulatory compliance (SEBI guidelines), and finalize portfolio allocations.

The system is built as a **React (Vite) + Vanilla CSS** frontend streaming real-time status and logs from a **FastAPI + CrewAI** backend.

---

## 🏛️ Project Architecture

```
algoai/
├── backend/                  # FastAPI Server & Multi-Agent Debate Loop
│   ├── agents/               # CrewAI Agents (Strategy, Stress, Compliance, Arbiter)
│   ├── api/                  # SSE Event Stream & session endpoints
│   ├── band/                 # Room Manager & message schemas
│   ├── api_server.py         # Backend server entrypoint
│   └── requirements.txt      # Python dependencies
└── frontend/                 # React + Vite Dashboard
    ├── src/
    │   ├── App.jsx           # Main interactive dashboard UI
    │   ├── index.css         # Custom glassmorphism design system styles
    │   └── mockData.js       # Cache database for offline demo playback
    └── package.json          # Node dependencies
```

### The 4-Phase Multi-Agent Debate Pipeline
1. **Strategy Proposals**: Quantitative Strategy Analysts (**Momentum Analyst**, **Mean Reversion Analyst**, and **Senti-Quant Analyst**) scan the ticker universe and pitch initial portfolios with backtest parameters.
2. **Stress Challenges**: The **Stress Tester** audits proposals against historic drawdowns and Monte Carlo shocks, flagging high-risk assets.
3. **Revisions & Defenses**: Strategy Analysts defend their metrics and publish **Revised Proposals** with modified weights.
4. **Verdict & Capital Allocation**: 
   * The **Compliance Officer** audits revisions against regulatory guidelines (e.g., SEBI retail algorithmic trading constraints).
   * The **Portfolio Arbiter** evaluates the approved strategies, computes ticker correlation matrices via Yahoo Finance, downsizes overlapping exposures, ranks allocations by Sharpe ratio, and publishes a clean portfolio allocation list with human-readable reasoning.

---

## ✨ Features

* **Glassmorphism Dark UI**: Visually stunning dashboard displaying real-time agent metrics, asset weight bars, regulatory checklists, and allocation gauges.
* **Dual Execution Modes**:
  * **Interactive Demo Playback**: Instantly runs and controls a full pre-cached debate timeline (1x, 2x, 5x speed) with typewriter effects and spinner alerts. Ideal for quick demos and presentations.
  * **Live API Run**: Triggers active CrewAI workflows on the FastAPI backend, streaming live agent thoughts and final allocations via Server-Sent Events (SSE).
* **Console Terminal Logs**: Dedicated logs terminal at the bottom of the interface rendering CLI events, thinking loops, and audit logs.

---

## 🚀 Getting Started

### Prerequisites
* **Python 3.10 to 3.12**
* **Node.js 18+** & npm
* A **Groq API Key** (or another LLM provider key supported by CrewAI/LiteLLM)

---

### 1. Backend Installation & Startup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install the Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in your API key:
   ```env
   GROQ_API_KEY="your_groq_api_key_here"
   ```

5. Launch the FastAPI server:
   ```bash
   python api_server.py
   ```
   The backend API will run on **`http://localhost:8000`**. You can view Swagger documentation at `http://localhost:8000/docs`.

---

### 2. Frontend Installation & Startup

1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install Node packages:
   ```bash
   npm install
   ```

3. Start the Vite React development server:
   ```bash
   npm run dev
   ```
   The frontend will run on **`http://localhost:5173`**.

---

## 🎮 Running a Simulation

1. Open **`http://localhost:5173`** in your browser.
2. **Demo Playback**:
   * Keep the mode toggle at the top-right on **Demo Playback**.
   * Click **Play Demo Debate** to witness the complete agent pipeline run dynamically with accelerated playback speeds (1x to 5x).
3. **Live Run**:
   * Switch the mode toggle to **Live API Run**.
   * Enter comma-separated stock tickers (e.g., `RELIANCE, TATAMOTORS, INFY`) into the input box.
   * Click the green **Run Quant agents** button. The button will turn steel-gray and disable itself while showing a spinning loader.
   * Watch the console terminal at the bottom stream live agent logs, and observe active spinners on the dashboard components as they await the live SSE payloads from the backend.
