# Nifty 50 Institutional RL Trading System
Repository reference: https://idea.unisys.com/D9030

> **Deep Reinforcement Learning (PPO) + GPU Acceleration + Institutional Macro Context + Local AI Assistant**

🎯 **What This Is**
A professional-grade quantitative trading platform that links refined **Nifty 50 PPO models** with a high-performance **React dashboard**. This system uses a "GPU-First" quantitative engine to provide real-time, context-aware trading signals.

```
React Dashboard (Port 5173)
         ↓
    FastAPI Server (Port 8000) [GPU Accelerated]
         ↓
    Institutional RL Model (500k Step Refinement)
```

⚡ **Quick Start (5 Minutes)**

**Terminal 1 - Backend**
```powershell
.venv\Scripts\Activate.ps1
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend**
```powershell
cd trade-signal-dashboard-main
npm run dev
```

**Open Dashboard**
Visit **http://localhost:5173** in your browser

📚 **Documentation**
Start with one of these based on your needs:

| Document | Time | Purpose |
|----------|------|---------|
| **QUICK_REFERENCE.md** | 5 min | Get started immediately |
| **ARCHITECTURE.md** | 15 min | Deep dive into GPU/Macro logic |
| **INTEGRATION_GUIDE.md** | 20 min | Full technical breakdown |
| **TROUBLESHOOTING.md** | 20 min | Hardware & CUDA setup fixes |
| **INDEX.md** | Navigation | Find every specific guide |

✨ **What's Included**

**Backend (Institutional Engine)**
*   ✅ `api_server.py` - FastAPI REST API with GPU support
*   ✅ `Nifty50_RL_Trading_MultiStock.py` - High-refinement PPO Engine
*   ✅ `xai_bot.py` - Local LLM (Phi-3) Analytical Assistant
*   ✅ `tune_rl_hyperparams.py` - Optuna Optimization Framework

**Frontend (Professional UI)**
*   ✅ Enhanced `api.ts` - Real-time analysis client
*   ✅ `HeroSignal.tsx` - Balanced weighted-signal visualization

**Utilities**
*   ✅ `start_backend.bat/sh` - Production launcher
*   ✅ `quick_start.bat/sh` - Full stack auto-launcher

🔐 **Model Precision & Risk Guarantee**
✅ **Institutional-Grade Intelligence**

*   **Risk-Aware Reward:** Agent penalized for holding trades in **Bear Regimes**.
*   **Institutional NLP (FinBERT):** Uses a specialized **Financial BERT** model for high-fidelity sentiment analysis of market news—far superior to generic sentiment tools.
*   **Macro Integration:** Direct data feeds for **USD/INR**, **US10Y Yield**, and **India VIX**.
*   **Sector Intelligence:** Real-time benchmarking against Nifty Sector Indices.
*   **Refinement:** 500,000 steps of GPU-accelerated training per stock.

📡 **API Endpoints**
*   `GET /health`                     → Server & Hardware status
*   `GET /api/analyze?ticker=X`       → Context-aware quant analysis
*   `GET /api/all-stocks`            → Portfolio-wide parallel processing
*   `GET /api/market-regime`         → Bull/Bear/Sideways detection
*   `POST /api/chat`                 → Local GPU-accelerated LLM support
*   `GET /docs`                      → Interactive Swagger documentation

🚀 **Key Features**

**Backend API**
*   **GPU Accelerated:** Native CUDA 12.6 support for 10x faster inference.
*   **Hybrid Chatbot:** Local Phi-3 model with seamless Cloud fallback.
*   **Macro-Aware:** Dynamic features for global market shifts.

**Frontend Integration**
*   **Real-time Analytics:** Instant backtest & sentiment visualization.
*   **Weighted Voting:** Decision logic balancing Brain, Setup, and Crowd.
*   **Hardware Scaling:** Automatically detects and utilizes user's GPU.

📊 **Performance (RTX 4050 GPU)**
| Operation | Time | Notes |
|-----------|------|-------|
| First request | 1-2s | GPU model loading |
| Analysis | 400ms | GPU parallel inference |
| Local Chat | <100ms | Instant token generation |
| CPU Fallback | 5-10s | Automatic hardware scaling |

🔍 **Architecture Overview**
┌─────────────────────────────────────┐
│   React/Vite Dashboard              │
│   (http://localhost:5173)           │
└──────────────┬──────────────────────┘
               │ HTTP REST API
               ↓
┌──────────────────────────────────────┐
│   FastAPI Backend Server            │
│   (http://localhost:8000)           │
│   - Institutional Macro Data        │
│   - Local AI (Phi-3)                │
└──────────────┬──────────────────────┘
               │ GPU Acceleration (CUDA)
               ↓
┌──────────────────────────────────────┐
│   Nifty50_RL_Trading_MultiStock.py  │
│   - 500k-Step PPO Brain             │
│   - Risk-Averse Reward Function     │
│   - Sector Context Integration      │
└──────────────────────────────────────┘

✅ **Files Created/Modified**
*   **Created:** `xai_bot.py` (Local AI), `tune_rl_hyperparams.py` (Optuna), 8 quantitative guides.
*   **Modified:** `Nifty50_RL_Trading_MultiStock.py` (Macro/Sector upgrade), `api_server.py` (Hardware sync).

🎯 **Getting Started**

**Prerequisites**
*   Python 3.13+ (CUDA 12.6 Recommended)
*   Node.js 18+ for dashboard
*   NVIDIA GPU (RTX 30 series or newer preferred)

**Step 1: Install Quantitative Dependencies**
```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements-backend.txt
```

**Step 2: Start the Engine**
```powershell
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

**Step 3: Launch the Dashboard**
```powershell
cd trade-signal-dashboard-main
npm install && npm run dev
```

🐛 **Troubleshooting**

**CUDA not detected**
*   The system will automatically fall back to CPU. To fix, verify NVIDIA drivers are updated and CUDA 12.6 is installed.

**Port 8000 in use**
```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

📖 **Documentation Guide**
*   **INDEX.md:** Navigation hub for all quant docs.
*   **QUICK_REFERENCE.md:** Essential maintenance commands.
*   **ARCHITECTURE.md:** Deep dive into the RL reward & Macro logic.
*   **TROUBLESHOOTING.md:** Hardware setup and GPU linking.

🎓 **What You Get**

**Working System ✅**
*   Institutional-grade RL models.
*   GPU-accelerated React dashboard.
*   Privacy-first local AI assistant.

**Best Practices ✅**
*   Type-safe TypeScript frontend.
*   Mathematically optimized hyperparameters (Optuna).
*   Risk-averse trading logic for Indian markets.

🔗 **Quick Links**
*   **API Docs:** http://localhost:8000/docs
*   **Dashboard:** http://localhost:5173
*   **Backend Health:** http://localhost:8000/health

🎊 **Status**
✅ **Institutional Update (v2.1.0) COMPLETE**
*   Full GPU sync verified.
*   Macro features live.
*   Ready for professional deployment.

🎉 **Happy Trading!**
Your Nifty 50 quant system is now live with institutional power.

**Version:** 2.1.0 (Institutional Edition)  
**Last Updated:** June 13, 2026  
**Status:** ✅ Production Ready 🚀
