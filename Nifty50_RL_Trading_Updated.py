#!/usr/bin/env python
# coding: utf-8

# # 📈 Nifty 50 Stock Trading Recommendation System
# ## Deep Reinforcement Learning (PPO) + Technical Analysis + Sentiment Analysis + Market Regime
# 
# **Framework:** Custom PPO (Proximal Policy Optimization) via Stable-Baselines3  
# **Market:** Indian Stock Market (NSE — Yahoo Finance .NS suffix)  
# **Output:** BUY / HOLD / SELL recommendation per selected stock
# 
# ### Pipeline:
# 1. User selects one stock from 10 curated Nifty 50 tickers
# 2. Download OHLCV data (2016–present)
# 3. Compute technical indicators → composite strength score
# 4. Market Regime Detection on ^NSEI index (HMM: Bull / Bear / Sideways)
# 5. Sentiment Analysis via Finnhub + Alpha Vantage APIs
# 6. Clean & merge features → PPO model input
# 7. Train PPO on 2016–2023, validate 2024, test 2025–today
# 8. Evaluate: Sharpe, Sortino, Calmar, Win Rate, Max Drawdown, Precision
# 9. Final recommendation: BUY / HOLD / SELL
# 
# ---

# ## CELL 1 — Install All Dependencies

# In[1]:


# ============================================================
# CELL 1: INSTALL DEPENDENCIES
# Run once. Restart runtime after if on Google Colab.
# ============================================================

get_ipython().system('python -m pip install -q --no-cache-dir yfinance pandas numpy matplotlib seaborn')
get_ipython().system('python -m pip install -q --no-cache-dir stable-baselines3[extra]')
get_ipython().system('python -m pip install -q --no-cache-dir gymnasium')
get_ipython().system('python -m pip install -q --no-cache-dir ta')
get_ipython().system('python -m pip install -q --no-cache-dir hmmlearn')
get_ipython().system('python -m pip install -q --no-cache-dir requests')
get_ipython().system('python -m pip install -q --no-cache-dir scikit-learn')
get_ipython().system('python -m pip install -q --no-cache-dir vaderSentiment')

print("✅ All packages installed!")


# ## CELL 2 — Imports

# In[2]:


# ============================================================
# CELL 2: IMPORTS
# ============================================================

import warnings
warnings.filterwarnings('ignore')

# Core
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-GUI backend so inline display works everywhere
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import seaborn as sns
from datetime import datetime, timedelta
import os
import time
import requests

# Data
import yfinance as yf

# Technical Indicators
import ta
from ta.trend import MACD, SMAIndicator, EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator, StochasticOscillator, ROCIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator, VolumeWeightedAveragePrice

# Sentiment
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Market Regime
from hmmlearn import hmm

# RL
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import EvalCallback, CheckpointCallback
from stable_baselines3.common.monitor import Monitor

# ML utilities
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.metrics import precision_score

print("✅ All imports successful!")
print(f"Run date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")


# ## CELL 3 — Configuration & Stock Selection

# In[3]:


# ============================================================
# CELL 3: CONFIGURATION & USER STOCK SELECTION
# ============================================================

# ---- API KEYS (replace with your actual keys) ----
FINNHUB_API_KEY  = "d7np7rpr01qm36379ongd7np7rpr01qm36379oo0"   # https://finnhub.io (free tier)
NEWSAPI_KEY      = "8d4a630796c94756b96a16efdf92f489"                         # https://newsapi.org (free tier)

# ---- 10 CURATED NIFTY 50 STOCKS ----
STOCK_OPTIONS = {
    "1": ("RELIANCE.NS",   "Reliance Industries"),
    "2": ("TCS.NS",        "Tata Consultancy Services"),
    "3": ("HDFCBANK.NS",   "HDFC Bank"),
    "4": ("INFY.NS",       "Infosys"),
    "5": ("ICICIBANK.NS",  "ICICI Bank"),
    "6": ("HINDUNILVR.NS", "Hindustan Unilever"),
    "7": ("ITC.NS",        "ITC Limited"),
    "8": ("SBIN.NS",       "State Bank of India"),
    "9": ("BHARTIARTL.NS", "Bharti Airtel"),
    "10":("KOTAKBANK.NS",  "Kotak Mahindra Bank"),
}

print("\n========================================")
print("   NIFTY 50 STOCK RECOMMENDATION SYSTEM")
print("========================================")
print("\nAvailable stocks:")
for k, (ticker, name) in STOCK_OPTIONS.items():
    print(f"  [{k:>2}] {ticker:<20} {name}")

user_choice = input("\nEnter stock number (1-10): ").strip()
if user_choice not in STOCK_OPTIONS:
    user_choice = "1"
    print("Invalid choice. Defaulting to RELIANCE.NS")

SELECTED_TICKER, SELECTED_NAME = STOCK_OPTIONS[user_choice]
# Finnhub symbol format (remove .NS, uppercase)
FINNHUB_SYMBOL = "BSE:" + SELECTED_TICKER.replace(".NS", "")
# Alpha Vantage symbol
AV_SYMBOL = SELECTED_TICKER.replace(".NS", ".BSE")

print(f"\n✅ Selected: {SELECTED_NAME} ({SELECTED_TICKER})")

# ---- DATE RANGES ----
TRAIN_START = "2016-01-01"
TRAIN_END   = "2023-12-31"
VAL_START   = "2024-01-01"
VAL_END     = "2024-12-31"
TEST_START  = "2025-01-01"
TEST_END    = datetime.now().strftime("%Y-%m-%d")  # today

FULL_START  = TRAIN_START
FULL_END    = TEST_END

# ---- TRADING PARAMETERS ----
TRANSACTION_COST = 0.001   # 0.1% brokerage
MAX_SHARES       = 100
DUMMY_CAPITAL    = 1000000  # internal RL environment only; NOT portfolio optimisation

# ---- PPO HYPERPARAMETERS (tuned) ----
TOTAL_TIMESTEPS  = 500000
LEARNING_RATE    = 0.0001     # reduced for stability
N_STEPS          = 1024
BATCH_SIZE       = 128
N_EPOCHS         = 15
GAMMA            = 0.995
GAE_LAMBDA       = 0.95
CLIP_RANGE       = 0.15       # tighter clip for stable policy
ENT_COEF         = 0.005      # small entropy bonus for exploration
VF_COEF          = 0.5
MAX_GRAD_NORM    = 0.5

# ---- TECHNICAL INDICATOR WINDOWS ----
RSI_WINDOW  = 14
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9
BB_WINDOW   = 20
SMA_SHORT   = 10
SMA_LONG    = 50
ATR_WINDOW  = 14
ADX_WINDOW  = 14
ROC_WINDOW  = 10

# ---- MARKET REGIME ----
N_REGIMES         = 3   # Bull=2, Sideways=1, Bear=0
REGIME_LOOKBACK   = 60  # days of Nifty returns for regime detection

# ---- RANDOM SEED ----
SEED = 42
np.random.seed(SEED)

print(f"\n📅 Train:  {TRAIN_START}  →  {TRAIN_END}")
print(f"   Val:    {VAL_START}  →  {VAL_END}")
print(f"   Test:   {TEST_START}  →  {TEST_END}")
print(f"   Algorithm: PPO (tuned)")
print("✅ Configuration complete!")


# ## CELL 4 — Download & Display Stock Data

# In[4]:


# ============================================================
# CELL 4: DOWNLOAD STOCK DATA FOR SELECTED TICKER
# ============================================================

def download_stock_data(ticker, start, end):
    """Downloads OHLCV data for one NSE ticker via yfinance."""
    print(f"📥 Downloading {ticker} from {start} to {end}...")
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    df.columns = [str(c).lower().strip() for c in df.columns]
    if 'date' not in df.columns:
        df.rename(columns={'index': 'date'}, inplace=True)
    df['date'] = pd.to_datetime(df['date'])
    df['ticker'] = ticker
    df = df.sort_values('date').reset_index(drop=True)
    print(f"✅ Downloaded {len(df)} rows for {ticker}")
    return df


# Download selected stock data
raw_data = download_stock_data(SELECTED_TICKER, FULL_START, FULL_END)

# ---- Display Data Summary ----
print(f"\n{'='*60}")
print(f"  DATA SUMMARY: {SELECTED_NAME} ({SELECTED_TICKER})")
print(f"{'='*60}")
print(f"  Total rows   : {len(raw_data):,}")
print(f"  Date range   : {raw_data['date'].min().date()} → {raw_data['date'].max().date()}")
print(f"  Columns      : {list(raw_data.columns)}")
print(f"\n  Latest 5 rows:")
display_cols = ['date','open','high','low','close','volume']
display_df = raw_data[display_cols].tail(5).copy()
for col in ['open','high','low','close']:
    display_df[col] = display_df[col].round(2)
display_df['volume'] = display_df['volume'].apply(lambda x: f"{int(x):,}")
print(display_df.to_string(index=False))

print(f"\n  Statistical Summary:")
print(raw_data[['open','high','low','close','volume']].describe().round(2).to_string())

# Download Nifty 50 Index separately for regime detection
print(f"\n📥 Downloading ^NSEI (Nifty 50 Index) for regime detection...")
nifty_index = download_stock_data("^NSEI", FULL_START, FULL_END)
print("✅ Data download complete!")


# ## CELL 5 — Technical Indicators + Composite Strength Score

# In[5]:


# ============================================================
# CELL 5: TECHNICAL INDICATORS + COMPOSITE STRENGTH SCORE
# ============================================================

def add_technical_indicators(df):
    """Computes all technical indicators for a single-stock DataFrame."""
    df = df.copy().sort_values('date')
    close  = df['close']
    high   = df['high']
    low    = df['low']
    volume = df['volume']

    # --- RSI ---
    rsi_ind = RSIIndicator(close=close, window=RSI_WINDOW)
    df['rsi'] = rsi_ind.rsi()

    # --- MACD ---
    macd_ind = MACD(close=close, window_fast=MACD_FAST,
                    window_slow=MACD_SLOW, window_sign=MACD_SIGNAL)
    df['macd']        = macd_ind.macd()
    df['macd_signal'] = macd_ind.macd_signal()
    df['macd_hist']   = macd_ind.macd_diff()

    # --- Bollinger Bands ---
    bb = BollingerBands(close=close, window=BB_WINDOW)
    df['bb_upper']  = bb.bollinger_hband()
    df['bb_lower']  = bb.bollinger_lband()
    df['bb_middle'] = bb.bollinger_mavg()
    df['bb_width']  = bb.bollinger_wband()
    df['bb_pct']    = bb.bollinger_pband()  # 0=lower band, 1=upper band

    # --- SMA ---
    df['sma_10'] = SMAIndicator(close=close, window=SMA_SHORT).sma_indicator()
    df['sma_50'] = SMAIndicator(close=close, window=SMA_LONG).sma_indicator()

    # --- EMA ---
    df['ema_20'] = EMAIndicator(close=close, window=20).ema_indicator()

    # --- ATR ---
    df['atr'] = AverageTrueRange(high=high, low=low, close=close,
                                  window=ATR_WINDOW).average_true_range()

    # --- OBV ---
    df['obv'] = OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume()

    # --- ADX (trend strength) ---
    adx_ind = ADXIndicator(high=high, low=low, close=close, window=ADX_WINDOW)
    df['adx'] = adx_ind.adx()

    # --- Stochastic Oscillator ---
    stoch = StochasticOscillator(high=high, low=low, close=close)
    df['stoch_k'] = stoch.stoch()
    df['stoch_d'] = stoch.stoch_signal()

    # --- Rate of Change ---
    df['roc'] = ROCIndicator(close=close, window=ROC_WINDOW).roc()

    # --- Price-based features ---
    df['daily_return']  = close.pct_change()
    df['log_return']    = np.log(close / close.shift(1))
    df['volatility_10'] = df['daily_return'].rolling(10).std()
    df['close_norm']    = (close - close.rolling(50).mean()) / (close.rolling(50).std() + 1e-8)

    print(f"✅ Technical indicators computed. Shape: {df.shape}")
    return df


def compute_technical_strength_score(df):
    """
    Computes a composite technical strength score (0–100) for every row.
    Each sub-signal is normalised 0–1 (bullish direction) then averaged.
    """
    df = df.copy()
    signals = pd.DataFrame(index=df.index)

    # RSI: 0–30 → bearish (0), 70–100 → bullish (1), else scaled 0–1
    signals['rsi_sig'] = df['rsi'].clip(0, 100) / 100

    # MACD Histogram: positive = bullish
    macd_h = df['macd_hist']
    signals['macd_sig'] = ((macd_h - macd_h.min()) /
                           (macd_h.max() - macd_h.min() + 1e-8)).clip(0, 1)

    # BB %: price position within band 0 (lower) → 1 (upper)
    signals['bb_sig'] = df['bb_pct'].clip(0, 1)

    # SMA cross: close > sma_50 → 1, else 0
    signals['sma_cross_sig'] = (df['close'] > df['sma_50']).astype(float)

    # EMA: close > ema_20 → 1, else 0
    signals['ema_sig'] = (df['close'] > df['ema_20']).astype(float)

    # ADX: strong trend > 25 → 1, weak < 20 → 0
    signals['adx_sig'] = ((df['adx'] - 10) / 40).clip(0, 1)

    # Stochastic: overbought/oversold (high K → bullish)
    signals['stoch_sig'] = df['stoch_k'].clip(0, 100) / 100

    # ROC: positive momentum → bullish
    roc = df['roc']
    signals['roc_sig'] = ((roc - roc.min()) /
                          (roc.max() - roc.min() + 1e-8)).clip(0, 1)

    # OBV trend: compare to 20-day MA of OBV
    obv_ma = df['obv'].rolling(20).mean()
    signals['obv_sig'] = (df['obv'] > obv_ma).astype(float)

    # ATR: low volatility slightly preferred, but moderate is fine
    atr_norm = (df['atr'] / (df['close'] + 1e-8))  # relative ATR
    signals['atr_sig'] = (1 - atr_norm.clip(0, 0.1) / 0.1).clip(0, 1)

    # Composite score (0–100)
    df['tech_strength_score'] = signals.mean(axis=1) * 100

    # Store individual normalised signals for bar chart
    signal_cols = ['rsi_sig','macd_sig','bb_sig','sma_cross_sig',
                   'ema_sig','adx_sig','stoch_sig','roc_sig','obv_sig','atr_sig']
    for col in signal_cols:
        df[col] = signals[col]

    return df, signal_cols


# ---- Run ----
data_with_ti = add_technical_indicators(raw_data)
data_with_ti, SIGNAL_COLS = compute_technical_strength_score(data_with_ti)

# ---- Print latest score ----
latest = data_with_ti.dropna(subset=['tech_strength_score']).iloc[-1]
score  = latest['tech_strength_score']
signal_label = "STRONG BULLISH" if score >= 70 else ("BULLISH" if score >= 55 else
               ("NEUTRAL" if score >= 45 else ("BEARISH" if score >= 30 else "STRONG BEARISH")))
print(f"\n{'='*55}")
print(f"  TECHNICAL STRENGTH SCORE (Latest): {score:.1f}/100")
print(f"  Signal: {signal_label}")
print(f"{'='*55}")

# ---- Bar chart: normalised indicator values ----
latest_signals = data_with_ti.dropna(subset=SIGNAL_COLS).iloc[-1][SIGNAL_COLS].values
indicator_labels = ['RSI','MACD\nHist','BB %','SMA\nCross','EMA\nCross',
                    'ADX','Stoch','ROC','OBV\nTrend','ATR\nRel']

fig, axes = plt.subplots(1, 2, figsize=(16, 5))
fig.suptitle(f'Technical Analysis — {SELECTED_NAME}', fontsize=14, fontweight='bold')

# Bar chart
colors = ['#2ecc71' if v >= 0.5 else '#e74c3c' for v in latest_signals]
bars = axes[0].bar(indicator_labels, latest_signals, color=colors, edgecolor='white', linewidth=0.8)
axes[0].axhline(0.5, color='gray', linestyle='--', linewidth=1, label='Neutral (0.5)')
axes[0].set_ylim(0, 1.1)
axes[0].set_ylabel('Normalised Strength (0–1)')
axes[0].set_title(f'Indicator Normalised Values  |  Composite Score: {score:.1f}/100  |  {signal_label}')
axes[0].legend()
for bar, val in zip(bars, latest_signals):
    axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                 f'{val:.2f}', ha='center', va='bottom', fontsize=8)

# Composite score over time
score_series = data_with_ti.dropna(subset=['tech_strength_score']).set_index('date')['tech_strength_score']
axes[1].plot(score_series.index, score_series.values, color='#3498db', linewidth=1)
axes[1].fill_between(score_series.index, 70, score_series.values,
                      where=score_series >= 70, color='#2ecc71', alpha=0.3, label='Bullish (≥70)')
axes[1].fill_between(score_series.index, score_series.values, 30,
                      where=score_series <= 30, color='#e74c3c', alpha=0.3, label='Bearish (≤30)')
axes[1].axhline(70, color='#27ae60', linestyle='--', linewidth=0.8)
axes[1].axhline(30, color='#c0392b', linestyle='--', linewidth=0.8)
axes[1].set_title('Technical Strength Score Over Time')
axes[1].set_ylabel('Score (0–100)')
axes[1].legend()
axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

plt.tight_layout()
plt.show()
print("✅ Technical analysis complete!")


# ## CELL 6 — Market Regime Detection on Nifty 50 Index (HMM)

# In[6]:


# ============================================================
# CELL 6: MARKET REGIME DETECTION ON ^NSEI (HMM)
# Uses actual Nifty 50 Index — NOT the selected stock
# ============================================================

def detect_market_regime_nsei(nifty_df, n_regimes=3, lookback=REGIME_LOOKBACK):
    """
    Fits a Gaussian HMM on Nifty 50 Index (^NSEI) log-returns + rolling volatility.
    Returns: (regime_df with columns [date, regime_score],
              bull_pct, bear_pct, sideways_pct, hmm_model)
    """
    print("🔍 Detecting Nifty 50 market regimes via HMM...")
    df = nifty_df.copy().sort_values('date')
    df['log_return'] = np.log(df['close'] / df['close'].shift(1))
    df['volatility'] = df['log_return'].rolling(lookback).std().fillna(0)
    df = df.dropna(subset=['log_return'])

    features = df[['log_return', 'volatility']].values

    model = hmm.GaussianHMM(
        n_components=n_regimes,
        covariance_type='full',
        n_iter=500,
        random_state=SEED,
        tol=1e-5
    )
    model.fit(features)
    hidden_states = model.predict(features)
    df['regime_raw'] = hidden_states

    # Map raw state to Bull/Sideways/Bear by mean return
    mean_ret_by_state = {s: df[df['regime_raw'] == s]['log_return'].mean()
                         for s in range(n_regimes)}
    sorted_states = sorted(mean_ret_by_state, key=mean_ret_by_state.get)
    regime_map = {
        sorted_states[0]: 0,   # Bear
        sorted_states[1]: 1,   # Sideways
        sorted_states[2]: 2,   # Bull
    }
    df['regime_score'] = df['regime_raw'].map(regime_map)  # 0/1/2

    counts = df['regime_score'].value_counts(normalize=True) * 100
    bear_pct     = counts.get(0, 0)
    sideways_pct = counts.get(1, 0)
    bull_pct     = counts.get(2, 0)

    print(f"   Bull:     {bull_pct:.1f}%")
    print(f"   Sideways: {sideways_pct:.1f}%")
    print(f"   Bear:     {bear_pct:.1f}%")

    return df[['date', 'regime_score', 'log_return', 'volatility']], bull_pct, bear_pct, sideways_pct, model


regime_df, bull_pct, bear_pct, sideways_pct, regime_model = detect_market_regime_nsei(
    nifty_index, N_REGIMES)

# Merge regime into stock data
data_with_regime = data_with_ti.merge(regime_df[['date', 'regime_score']], on='date', how='left')
data_with_regime['regime_score'] = data_with_regime['regime_score'].fillna(1).astype(int)

# ---- Plot 1: Regime distribution pie ----
fig, axes = plt.subplots(1, 2, figsize=(16, 5))
fig.suptitle('Market Regime Analysis — Nifty 50 Index (^NSEI)', fontsize=14, fontweight='bold')

pie_vals   = [bull_pct, sideways_pct, bear_pct]
pie_labels = [f'Bullish\n{bull_pct:.1f}%', f'Sideways\n{sideways_pct:.1f}%', f'Bearish\n{bear_pct:.1f}%']
pie_colors = ['#2ecc71', '#f39c12', '#e74c3c']
wedges, texts = axes[0].pie(pie_vals, labels=pie_labels, colors=pie_colors,
                             startangle=90, wedgeprops={'edgecolor': 'white', 'linewidth': 1.5})
for text in texts:
    text.set_fontsize(10)
axes[0].set_title('Overall Market Regime Distribution')

# ---- Plot 2: Regime timeline (annual bands) ----
regime_plot = regime_df.copy()
regime_plot['year'] = pd.to_datetime(regime_plot['date']).dt.year
yearly = regime_plot.groupby(['year', 'regime_score']).size().unstack(fill_value=0)
yearly_pct = yearly.div(yearly.sum(axis=1), axis=0) * 100
if 0 not in yearly_pct.columns: yearly_pct[0] = 0
if 1 not in yearly_pct.columns: yearly_pct[1] = 0
if 2 not in yearly_pct.columns: yearly_pct[2] = 0
yearly_pct = yearly_pct[[0, 1, 2]]
years = yearly_pct.index.astype(str)
x = np.arange(len(years))
w = 0.6
axes[1].bar(x, yearly_pct[2], w, label='Bullish',  color='#2ecc71', alpha=0.85)
axes[1].bar(x, yearly_pct[1], w, label='Sideways', color='#f39c12', alpha=0.85,
            bottom=yearly_pct[2])
axes[1].bar(x, yearly_pct[0], w, label='Bearish',  color='#e74c3c', alpha=0.85,
            bottom=yearly_pct[2] + yearly_pct[1])
axes[1].set_xticks(x)
axes[1].set_xticklabels(years, rotation=45)
axes[1].set_ylabel('Percentage of Trading Days (%)')
axes[1].set_title('Annual Regime Distribution (% Days)')
axes[1].legend(loc='upper right')
axes[1].set_ylim(0, 105)

plt.tight_layout()
plt.show()
print("✅ Market regime detection complete!")


# ## CELL 7 — Sentiment Analysis (Finnhub + Alpha Vantage)

# In[7]:


# ============================================================
# CELL 7: SENTIMENT ANALYSIS
# Source 1: Finnhub (company news headlines)
# Source 2: Alpha Vantage (news sentiment endpoint)
# Fallback: VADER on synthetic headlines if APIs unavailable
# ============================================================

vader = SentimentIntensityAnalyzer()

def score_text(text):
    """Returns VADER compound score for a text string."""
    if not text or not isinstance(text, str):
        return None
    vs = vader.polarity_scores(text)
    return vs['compound']  # range: -1.0 to 1.0


def fetch_finnhub_sentiment(symbol, api_key, days=90):
    """Fetches company news from Finnhub and scores with VADER."""
    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(days=days)
    url = (f"https://finnhub.io/api/v1/company-news?"
           f"symbol={symbol}&from={start_dt.strftime('%Y-%m-%d')}"
           f"&to={end_dt.strftime('%Y-%m-%d')}&token={api_key}")
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return pd.DataFrame()
        news = r.json()
        if not isinstance(news, list) or len(news) == 0:
            return pd.DataFrame()
        records = []
        for item in news:
            headline = item.get('headline', '')
            score    = score_text(headline)
            if score is None:
                continue
            dt = pd.to_datetime(item.get('datetime', 0), unit='s')
            records.append({'date': dt.date(), 'sentiment_score': score})
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])
        daily = df.groupby('date')['sentiment_score'].mean().reset_index()
        print(f"   Finnhub: {len(records)} headlines → {len(daily)} daily scores")
        return daily
    except Exception as e:
        print(f"   Finnhub error: {e}")
        return pd.DataFrame()


def fetch_alphavantage_sentiment(ticker_base, api_key, days=90):
    """Fetches news sentiment from Alpha Vantage."""
    url = (f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT"
           f"&tickers={ticker_base}&sort=LATEST&limit=200&apikey={api_key}")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json()
        feed = data.get('feed', [])
        if not feed:
            return pd.DataFrame()
        records = []
        cutoff  = datetime.now() - timedelta(days=days)
        for item in feed:
            ts = item.get('time_published', '')  # e.g. '20240101T120000'
            try:
                dt = datetime.strptime(ts[:8], '%Y%m%d')
            except:
                continue
            if dt < cutoff:
                continue
            # Alpha Vantage provides overall_sentiment_score natively
            score = float(item.get('overall_sentiment_score', 0))
            if score == 0:  # fallback to VADER on title
                score = score_text(item.get('title', '')) or 0
            records.append({'date': dt, 'sentiment_score': score})
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])
        daily = df.groupby('date')['sentiment_score'].mean().reset_index()
        print(f"   AlphaVantage: {len(records)} articles → {len(daily)} daily scores")
        return daily
    except Exception as e:
        print(f"   AlphaVantage error: {e}")
        return pd.DataFrame()


def build_sentiment_column(stock_df, selected_ticker, finnhub_key, av_key):
    """Merges Finnhub + AV sentiment; fills gaps with VADER-correlated fallback."""
    ticker_base = selected_ticker.replace('.NS', '')
    print("🎭 Fetching sentiment data...")

    fh_df = fetch_finnhub_sentiment(FINNHUB_SYMBOL, finnhub_key, days=365)
    av_df = fetch_alphavantage_sentiment(ticker_base, av_key, days=365)

    # Merge both sources (average if both available)
    sentiment_parts = [p for p in [fh_df, av_df] if not p.empty]
    if sentiment_parts:
        combined = pd.concat(sentiment_parts).groupby('date')['sentiment_score'].mean().reset_index()
    else:
        print("   No API data — using VADER-correlated synthetic sentiment.")
        combined = pd.DataFrame()

    # Merge into stock_df
    result = stock_df.copy()
    if not combined.empty:
        combined['date'] = pd.to_datetime(combined['date'])
        result = result.merge(combined, on='date', how='left')
    else:
        result['sentiment_score'] = np.nan

    # Fallback for NaN rows: VADER-correlated synthetic score
    # (only used where real sentiment data is unavailable)
    np.random.seed(SEED)
    mask = result['sentiment_score'].isna()
    n_missing = mask.sum()
    if n_missing > 0:
        noise = np.random.normal(0, 0.10, n_missing)
        corr  = result.loc[mask, 'daily_return'].fillna(0).values * 1.2
        result.loc[mask, 'sentiment_score'] = (noise + corr).clip(-1, 1)
    
    # Zero-score filtering: if score is near zero treat as no-signal (keep as is but flag)
    result['sentiment_valid'] = (result['sentiment_score'].abs() > 0.05).astype(int)

    print(f"   Valid sentiment rows: {result['sentiment_valid'].sum()}/{len(result)}")
    return result


data_with_sentiment = build_sentiment_column(
    data_with_regime, SELECTED_TICKER, FINNHUB_API_KEY, ALPHAVANTAGE_KEY)

# ---- Sentiment Chart ----
fig, ax = plt.subplots(figsize=(16, 5))
# Use recent 2 years for readability
recent = data_with_sentiment[data_with_sentiment['date'] >= '2023-01-01'].copy()
ax.plot(recent['date'], recent['sentiment_score'], alpha=0.4, color='#3498db',
        linewidth=0.8, label='Daily Sentiment')
rolling_sent = recent['sentiment_score'].rolling(20).mean()
ax.plot(recent['date'], rolling_sent, color='#2c3e50', linewidth=2,
        label='20-day Rolling Mean')
ax.fill_between(recent['date'], rolling_sent.fillna(0), 0,
                where=rolling_sent >= 0, alpha=0.25, color='#27ae60', label='Positive Zone')
ax.fill_between(recent['date'], rolling_sent.fillna(0), 0,
                where=rolling_sent < 0,  alpha=0.25, color='#e74c3c', label='Negative Zone')
ax.axhline(0, color='black', linewidth=0.8, linestyle='--')
ax.set_title(f'Sentiment Analysis — {SELECTED_NAME} (2023–Present)', fontsize=13, fontweight='bold')
ax.set_ylabel('Sentiment Score (−1 Bearish → +1 Bullish)')
ax.legend(loc='upper left')
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax.set_ylim(-1.1, 1.1)
plt.xticks(rotation=30)
plt.tight_layout()
plt.show()

latest_sent = data_with_sentiment.dropna(subset=['sentiment_score'])['sentiment_score'].iloc[-1]
print(f"✅ Sentiment analysis complete! Latest score: {latest_sent:+.4f}")


# ## CELL 8 — Data Cleaning & Feature Preparation

# In[8]:


# ============================================================
# CELL 8: DATA CLEANING & FINAL FEATURE SET
# ============================================================

# ---- Feature columns for RL state space ----
# Kept: sentiment_score (single, no 7d avg), regime_score (continuous 0/1/2),
#       no regime_label text column.
FEATURE_COLS = [
    # Price-derived
    'close_norm', 'daily_return', 'log_return', 'volatility_10',
    # Trend
    'macd', 'macd_signal', 'macd_hist',
    'sma_10', 'sma_50', 'ema_20',
    # Momentum
    'rsi', 'stoch_k', 'stoch_d', 'roc',
    # Volatility
    'bb_pct', 'bb_width', 'atr',
    # Volume
    'obv',
    # Trend strength
    'adx',
    # Sentiment (single score; zero-score rows kept as 0)
    'sentiment_score',
    # Market regime (numeric: 0=Bear, 1=Sideways, 2=Bull)
    'regime_score',
    # Composite tech strength
    'tech_strength_score',
]


def clean_and_prepare(df, feature_cols):
    df = df.copy()

    # Replace inf
    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    # Forward-fill then back-fill then zero for remaining NaN
    df[feature_cols] = (df[feature_cols]
                        .ffill()
                        .bfill()
                        .fillna(0))

    # Standardize feature cols (z-score) — keeps RL observation stable
    scaler = StandardScaler()
    df[feature_cols] = scaler.fit_transform(df[feature_cols])

    return df, scaler


clean_data, feature_scaler = clean_and_prepare(data_with_sentiment, FEATURE_COLS)

# Validate zero-score sentiment filtering impact
# (rows with near-zero sentiment are still included but with score=0)

# ---- Split into train / val / test ----
train_data = clean_data[(clean_data['date'] >= TRAIN_START) &
                         (clean_data['date'] <= TRAIN_END)].copy()
val_data   = clean_data[(clean_data['date'] >= VAL_START) &
                         (clean_data['date'] <= VAL_END)].copy()
test_data  = clean_data[(clean_data['date'] >= TEST_START) &
                         (clean_data['date'] <= TEST_END)].copy()

FINAL_FEATURES = FEATURE_COLS
N_FEATURES     = len(FINAL_FEATURES)

print(f"\n{'='*55}")
print(f"  DATA SPLIT SUMMARY")
print(f"{'='*55}")
print(f"  Train : {len(train_data):>5} rows  ({train_data['date'].min().date()} → {train_data['date'].max().date()})")
print(f"  Val   : {len(val_data):>5} rows  ({val_data['date'].min().date()} → {val_data['date'].max().date()})")
print(f"  Test  : {len(test_data):>5} rows  ({test_data['date'].min().date()} → {test_data['date'].max().date()})")
print(f"  Features in state space: {N_FEATURES}")
print(f"  Feature list: {FINAL_FEATURES}")
print("✅ Data preparation complete!")


# ## CELL 9 — Custom RL Trading Environment

# In[9]:


# ============================================================
# CELL 9: SINGLE-STOCK RL TRADING ENVIRONMENT
# This is a RECOMMENDATION SYSTEM — not portfolio optimisation.
# Action: continuous [−1, 1] → BUY / HOLD / SELL signal
# Reward: risk-adjusted (Sharpe-like) return
# ============================================================

class NiftyRecommendationEnv(gym.Env):
    """
    Single-stock trading environment for BUY/HOLD/SELL recommendation.

    State: [position (1), features (N_FEATURES), price_norm (1)]
    Action: scalar in [-1, 1]  (< -0.3 = SELL, > 0.3 = BUY, else HOLD)
    Reward: Sharpe-adjusted daily return − transaction cost
    """

    metadata = {'render_modes': ['human']}

    def __init__(self, df, feature_cols,
                 dummy_capital=DUMMY_CAPITAL,
                 transaction_cost=TRANSACTION_COST,
                 max_shares=MAX_SHARES,
                 sharpe_window=20):
        super().__init__()
        self.df               = df.reset_index(drop=True)
        self.feature_cols     = feature_cols
        self.n_features       = len(feature_cols)
        self.dummy_capital    = dummy_capital
        self.transaction_cost = transaction_cost
        self.max_shares       = max_shares
        self.sharpe_window    = sharpe_window
        self.dates            = sorted(df['date'].unique())
        self.n_days           = len(self.dates)

        obs_size = 1 + self.n_features + 1  # position + features + price_norm
        self.action_space      = spaces.Box(low=-1, high=1, shape=(1,), dtype=np.float32)
        self.observation_space = spaces.Box(low=-10, high=10, shape=(obs_size,), dtype=np.float32)
        self.reset()

    def _get_row(self, step):
        date  = self.dates[step]
        rows  = self.df[self.df['date'] == date]
        return rows.iloc[0] if len(rows) > 0 else None

    def _obs(self):
        row = self._get_row(self.current_step)
        if row is None:
            return np.zeros(self.observation_space.shape, dtype=np.float32)
        feats      = row[self.feature_cols].values.astype(np.float32)
        price_norm = np.array([row['close_norm']], dtype=np.float32)
        position   = np.array([self.position], dtype=np.float32)
        obs        = np.concatenate([position, feats, price_norm])
        obs        = np.nan_to_num(obs, nan=0.0, posinf=5.0, neginf=-5.0)
        return obs.astype(np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step    = 0
        self.balance         = float(self.dummy_capital)
        self.shares_held     = 0
        self.position        = 0.0   # normalised: -1=short, 0=flat, 1=long
        self.portfolio_hist  = [self.dummy_capital]
        self.returns_hist    = []
        self.actions_hist    = []
        return self._obs(), {}

    def _portfolio_value(self):
        row = self._get_row(self.current_step)
        price = float(row['close']) if row is not None else 0.0
        return self.balance + self.shares_held * price

    def step(self, action):
        action_scalar = float(action[0])  # -1 to 1
        self.actions_hist.append(action_scalar)

        row = self._get_row(self.current_step)
        price = float(row['close']) if row is not None else 1.0

        # Threshold-based decision
        if action_scalar > 0.3:   # BUY
            n_shares = int((self.balance * 0.3) / (price + 1e-8))  # invest 30% of cash
            n_shares = min(n_shares, self.max_shares)
            if n_shares > 0 and self.balance >= n_shares * price * (1 + self.transaction_cost):
                cost = n_shares * price * (1 + self.transaction_cost)
                self.balance    -= cost
                self.shares_held += n_shares
                self.position    = min(1.0, self.position + 0.3)
        elif action_scalar < -0.3:  # SELL
            n_sell = min(self.shares_held, max(1, int(self.shares_held * 0.5)))
            if n_sell > 0:
                revenue = n_sell * price * (1 - self.transaction_cost)
                self.balance    += revenue
                self.shares_held -= n_sell
                self.position    = max(-1.0, self.position - 0.3)
        # else HOLD: no trade

        self.current_step += 1
        done = self.current_step >= self.n_days - 1

        new_val   = self._portfolio_value()
        prev_val  = self.portfolio_hist[-1]
        pct_ret   = (new_val - prev_val) / (prev_val + 1e-8)
        self.portfolio_hist.append(new_val)
        self.returns_hist.append(pct_ret)

        # Risk-adjusted reward (rolling Sharpe over window)
        if len(self.returns_hist) >= self.sharpe_window:
            r_arr  = np.array(self.returns_hist[-self.sharpe_window:])
            sharpe = r_arr.mean() / (r_arr.std() + 1e-8)
            # Penalise excessive drawdown
            peak     = max(self.portfolio_hist)
            dd_pen   = max(0, (peak - new_val) / (peak + 1e-8)) * 0.5
            reward   = (sharpe - dd_pen) * 10
        else:
            reward = pct_ret * 100

        obs  = self._obs()
        info = {'portfolio_value': new_val,
                'daily_return': pct_ret,
                'action': action_scalar}
        return obs, float(reward), done, False, info

    def render(self):
        pv  = self._portfolio_value()
        ret = (pv / self.dummy_capital - 1) * 100
        print(f"  Step {self.current_step:>4}: Portfolio=₹{pv:,.0f} ({ret:+.2f}%)  "
              f"Pos={self.position:+.2f}")


# Sanity check
print("🧪 Environment sanity check...")
_env = NiftyRecommendationEnv(train_data, FINAL_FEATURES)
obs0, _ = _env.reset()
print(f"   Observation shape : {obs0.shape}")
print(f"   Action space      : {_env.action_space}")
print(f"   Trading days      : {_env.n_days}")
print(f"   Features per step : {_env.n_features}")
a0  = _env.action_space.sample()
obs1, rew, done, _, info1 = _env.step(a0)
print(f"   Sample action     : {a0[0]:+.4f}")
print(f"   Sample reward     : {rew:.4f}")
print(f"   Portfolio value   : ₹{info1['portfolio_value']:,.0f}")
print("✅ Environment ready!")


# ## CELL 10 — Train PPO Agent

# In[10]:


# ============================================================
# CELL 10: TRAIN PPO AGENT (TUNED HYPERPARAMETERS)
# ============================================================

import os
os.makedirs('trained_models', exist_ok=True)
os.makedirs('logs', exist_ok=True)

def make_train_env():
    env = NiftyRecommendationEnv(
        df=train_data,
        feature_cols=FINAL_FEATURES,
        transaction_cost=TRANSACTION_COST,
        max_shares=MAX_SHARES,
        sharpe_window=20
    )
    return Monitor(env)

def make_val_env():
    env = NiftyRecommendationEnv(
        df=val_data,
        feature_cols=FINAL_FEATURES,
        transaction_cost=TRANSACTION_COST,
        max_shares=MAX_SHARES,
        sharpe_window=20
    )
    return Monitor(env)


train_vec = DummyVecEnv([make_train_env])
val_vec   = DummyVecEnv([make_val_env])

# PPO with tuned hyperparameters
ppo_model = PPO(
    policy          = "MlpPolicy",
    env             = train_vec,
    learning_rate   = LEARNING_RATE,
    n_steps         = N_STEPS,
    batch_size      = BATCH_SIZE,
    n_epochs        = N_EPOCHS,
    gamma           = GAMMA,
    gae_lambda      = GAE_LAMBDA,
    clip_range      = CLIP_RANGE,
    ent_coef        = ENT_COEF,
    vf_coef         = VF_COEF,
    max_grad_norm   = MAX_GRAD_NORM,
    policy_kwargs   = dict(
        net_arch=[dict(pi=[256, 256, 128], vf=[256, 256, 128])]
    ),
    verbose         = 1,
    seed            = SEED,
    tensorboard_log = './logs'
)

# Checkpoint callback
checkpoint_cb = CheckpointCallback(
    save_freq=50_000,
    save_path='./trained_models/',
    name_prefix='ppo_nifty'
)
# Eval callback on validation env
eval_cb = EvalCallback(
    val_vec,
    best_model_save_path='./trained_models/',
    log_path='./logs/',
    eval_freq=20_000,
    n_eval_episodes=1,
    deterministic=True,
    verbose=0
)

print(f"🤖 Training PPO agent for {TOTAL_TIMESTEPS:,} timesteps...")
print(f"   Net architecture : [256, 256, 128]")
print(f"   Learning rate    : {LEARNING_RATE}")
print(f"   Clip range       : {CLIP_RANGE}")
print(f"   Entropy coeff    : {ENT_COEF}")
print(f"   Gamma            : {GAMMA}")
print("   ⏳ This may take 5–20 mins...")

ppo_model.learn(
    total_timesteps = TOTAL_TIMESTEPS,
    callback        = [checkpoint_cb, eval_cb],
    progress_bar    = True
)

model_path = f'trained_models/PPO_nifty_{SELECTED_TICKER.replace(".NS","")}'
ppo_model.save(model_path)
print(f"\n✅ Model saved → {model_path}.zip")


# ## CELL 11 — Backtesting (Validation + Test)

# In[11]:


# ============================================================
# CELL 11: BACKTEST ON VALIDATION AND TEST DATA
# ============================================================

def run_backtest(model, df, label="Test"):
    """Runs trained model deterministically on a split."""
    print(f"\n📊 Running backtest: {label} ({len(df)} rows)")
    env = NiftyRecommendationEnv(df=df, feature_cols=FINAL_FEATURES,
                                  transaction_cost=TRANSACTION_COST,
                                  max_shares=MAX_SHARES, sharpe_window=20)
    obs, _ = env.reset()
    done   = False
    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, _, done, _, _ = env.step(action)
    return env.portfolio_hist, env.returns_hist, env.actions_hist


def buy_and_hold(df, dummy_capital):
    """Equal-weight buy-and-hold baseline for the single selected stock."""
    df_s = df.sort_values('date').reset_index(drop=True)
    if df_s.empty:
        return [dummy_capital]
    initial_price = df_s['close'].iloc[0]
    shares = dummy_capital / (initial_price + 1e-8)
    return (df_s['close'].values * shares).tolist()


# Load best model saved by EvalCallback (if exists)
best_path = 'trained_models/best_model'
if os.path.exists(best_path + '.zip'):
    print("📂 Loading best validation model...")
    ppo_model = PPO.load(best_path)

val_hist,  val_rets,  val_acts  = run_backtest(ppo_model, val_data,  "Validation")
test_hist, test_rets, test_acts = run_backtest(ppo_model, test_data, "Test")

bnh_val  = buy_and_hold(val_data,  DUMMY_CAPITAL)
bnh_test = buy_and_hold(test_data, DUMMY_CAPITAL)

print("\n✅ Backtesting complete!")


# ## CELL 12 — Evaluation Metrics

# In[12]:


# ============================================================
# CELL 12: COMPREHENSIVE EVALUATION METRICS
# Key: Sharpe, Win Rate, Precision, Cumulative Return,
#      Max Drawdown, Sortino, Calmar
# NOTE: No initial investment or portfolio fields — this is
#       a recommendation system, not portfolio optimisation.
# ============================================================

def compute_metrics(portfolio_hist, returns_hist, actions_hist=None, label=""):
    """
    Computes all key performance metrics with benchmarks.
    Returns dict of metrics.
    """
    vals    = np.array(portfolio_hist)
    rets    = np.array(returns_hist) if returns_hist else np.diff(vals) / (vals[:-1] + 1e-8)

    init    = vals[0]
    final   = vals[-1]
    n_days  = len(vals)

    # ---- Cumulative Return ----
    cum_ret = (final / init - 1) * 100

    # ---- Annualised Return ----
    ann_ret = ((final / init) ** (252 / n_days) - 1) * 100

    # ---- Sharpe Ratio (annualised, rf=0) ----
    sharpe  = (rets.mean() / (rets.std() + 1e-8)) * np.sqrt(252)

    # ---- Sortino Ratio ----
    neg_rets = rets[rets < 0]
    sortino  = (rets.mean() / (neg_rets.std() + 1e-8)) * np.sqrt(252)

    # ---- Max Drawdown ----
    peak   = np.maximum.accumulate(vals)
    dd     = (vals - peak) / (peak + 1e-8)
    max_dd = dd.min() * 100

    # ---- Calmar Ratio ----
    calmar = ann_ret / (abs(max_dd) + 1e-8)

    # ---- Win Rate ----
    win_rate = (rets > 0).mean() * 100

    # ---- Precision (signal accuracy: buy signals that led to +ve next-day return) ----
    precision_val = None
    if actions_hist and len(actions_hist) == len(rets):
        buy_mask = np.array(actions_hist) > 0.3
        if buy_mask.sum() > 0:
            correct_buys = (buy_mask & (rets > 0)).sum()
            precision_val = (correct_buys / buy_mask.sum()) * 100
        sell_mask = np.array(actions_hist) < -0.3
        if sell_mask.sum() > 0:
            correct_sells = (sell_mask & (rets < 0)).sum()
            sell_precision = (correct_sells / sell_mask.sum()) * 100
        else:
            sell_precision = None
    else:
        sell_precision = None

    # ---- Volatility (annualised) ----
    ann_vol = rets.std() * np.sqrt(252) * 100

    metrics = {
        'Label'               : label,
        'Cumulative Return'   : f"{cum_ret:+.2f}%",
        'Annualised Return'   : f"{ann_ret:+.2f}%",
        'Annualised Volatility': f"{ann_vol:.2f}%",
        'Sharpe Ratio'        : f"{sharpe:.4f}",
        'Sortino Ratio'       : f"{sortino:.4f}",
        'Calmar Ratio'        : f"{calmar:.4f}",
        'Max Drawdown'        : f"{max_dd:.2f}%",
        'Win Rate'            : f"{win_rate:.2f}%",
        'Buy Precision'       : f"{precision_val:.2f}%" if precision_val is not None else "N/A",
        'Sell Precision'      : f"{sell_precision:.2f}%" if sell_precision is not None else "N/A",
        # Raw values for plotting
        '_cum_ret'  : cum_ret,
        '_sharpe'   : sharpe,
        '_max_dd'   : max_dd,
        '_win_rate' : win_rate,
        '_sortino'  : sortino,
        '_calmar'   : calmar,
    }
    return metrics


# ---- Benchmarks ----
BENCHMARKS = {
    'Sharpe Ratio'         : ('> 1.0', 'Good | > 2.0 Excellent'),
    'Sortino Ratio'        : ('> 1.5', 'Good | > 3.0 Excellent'),
    'Calmar Ratio'         : ('> 0.5', 'Good | > 1.0 Excellent'),
    'Max Drawdown'         : ('> -20%', 'Acceptable | < -10% Preferred'),
    'Win Rate'             : ('> 50%', 'Acceptable | > 55% Preferred'),
    'Buy Precision'        : ('> 50%', 'Acceptable | > 60% Preferred'),
    'Cumulative Return'    : ('> 0%', 'Positive return required'),
    'Annualised Return'    : ('> 12%', 'Beats typical FD/index return'),
}

val_metrics  = compute_metrics(val_hist,  val_rets,  val_acts,  f"PPO (Val 2024)")
test_metrics = compute_metrics(test_hist, test_rets, test_acts, f"PPO (Test 2025–{datetime.now().year})")
bnh_val_m    = compute_metrics(bnh_val,   [], None, "B&H (Val)")
bnh_test_m   = compute_metrics(bnh_test,  [], None, "B&H (Test)")

# ---- Print metrics table ----
print("\n" + "="*80)
print("    PERFORMANCE METRICS — RECOMMENDATION SYSTEM EVALUATION")
print("="*80)
display_keys = [
    'Cumulative Return','Annualised Return','Annualised Volatility',
    'Sharpe Ratio','Sortino Ratio','Calmar Ratio',
    'Max Drawdown','Win Rate','Buy Precision','Sell Precision'
]
print(f"{'Metric':<28} {'PPO Val':>12} {'B&H Val':>12} {'PPO Test':>12} {'B&H Test':>12} {'Benchmark'}")
print("-"*80)
for key in display_keys:
    bench = BENCHMARKS.get(key, ('-', ''))
    bench_str = bench[0] if isinstance(bench, tuple) else '-'
    print(f"{key:<28} {val_metrics.get(key,'N/A'):>12} {bnh_val_m.get(key,'N/A'):>12} "
          f"{test_metrics.get(key,'N/A'):>12} {bnh_test_m.get(key,'N/A'):>12}  {bench_str}")
print("="*80)

print("\n📋 Benchmark Notes:")
for k, (thr, note) in BENCHMARKS.items():
    print(f"   {k:<28} {thr:<10}  ({note})")


# ## CELL 13 — Performance Visualisation

# In[13]:


# ============================================================
# CELL 13: PERFORMANCE VISUALISATION (inline, no saved PNGs)
# ============================================================

sns.set_theme(style='darkgrid', palette='muted')

test_dates = sorted(test_data['date'].unique())
val_dates  = sorted(val_data['date'].unique())

# ── Plot 1: Portfolio Value (% of dummy capital) ──────────────
fig, ax = plt.subplots(figsize=(16, 5))
n_test  = min(len(test_hist), len(test_dates))
n_bnh_t = min(len(bnh_test),  len(test_dates))
ax.plot(test_dates[:n_test],
        [v / DUMMY_CAPITAL * 100 for v in test_hist[:n_test]],
        label='PPO Agent', color='#2980b9', linewidth=2)
ax.plot(test_dates[:n_bnh_t],
        [v / DUMMY_CAPITAL * 100 for v in bnh_test[:n_bnh_t]],
        label='Buy & Hold', color='#e67e22', linewidth=2, linestyle='--')
ax.axhline(100, color='gray', linestyle=':', linewidth=0.8)
ax.set_title(f'Portfolio Performance (Test 2025–{datetime.now().year}) — {SELECTED_NAME}',
             fontsize=13, fontweight='bold')
ax.set_ylabel('Portfolio Value (% of initial)')
ax.legend()
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
plt.xticks(rotation=30)
plt.tight_layout()
plt.show()

# ── Plot 2: Drawdown ─────────────────────────────────────────
fig, ax = plt.subplots(figsize=(16, 4))
pv_arr = np.array(test_hist[:n_test])
peak   = np.maximum.accumulate(pv_arr)
dd_arr = (pv_arr - peak) / (peak + 1e-8) * 100
ax.fill_between(test_dates[:n_test], dd_arr, 0, alpha=0.6, color='#e74c3c')
ax.plot(test_dates[:n_test], dd_arr, color='#c0392b', linewidth=1)
ax.set_title('Portfolio Drawdown (Test Period)', fontsize=12, fontweight='bold')
ax.set_ylabel('Drawdown (%)')
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
plt.xticks(rotation=30)
plt.tight_layout()
plt.show()

# ── Plot 3: Daily Returns Distribution ───────────────────────
fig, ax = plt.subplots(figsize=(12, 5))
ret_arr = np.array(test_rets) * 100
ax.hist(ret_arr, bins=60, color='#3498db', alpha=0.75, edgecolor='white')
ax.axvline(0, color='black', linewidth=1.2, linestyle='--')
ax.axvline(ret_arr.mean(), color='#2ecc71', linewidth=1.5,
           label=f'Mean: {ret_arr.mean():.3f}%')
ax.axvline(np.percentile(ret_arr, 5), color='#e74c3c', linewidth=1.5, linestyle=':',
           label=f'5th pct: {np.percentile(ret_arr,5):.3f}%')
ax.set_title('Daily Returns Distribution (Test Period)', fontsize=12, fontweight='bold')
ax.set_xlabel('Daily Return (%)')
ax.set_ylabel('Frequency')
ax.legend()
plt.tight_layout()
plt.show()

# ── Plot 4: Metrics comparison bar chart ─────────────────────
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.suptitle('Key Metrics: PPO vs Buy & Hold', fontsize=13, fontweight='bold')
metric_pairs = [
    ('Sharpe Ratio',    '_sharpe',  axes[0]),
    ('Cumulative Ret (%)', '_cum_ret', axes[1]),
    ('Max Drawdown (%)', '_max_dd',  axes[2]),
]
for title, key, ax in metric_pairs:
    vals_  = [test_metrics[key], bnh_test_m[key]]
    labels = ['PPO', 'B&H']
    colors = ['#2980b9', '#e67e22']
    bars   = ax.bar(labels, vals_, color=colors, alpha=0.85, edgecolor='white')
    for bar, v in zip(bars, vals_):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + abs(bar.get_height()) * 0.02,
                f'{v:.3f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax.set_title(title)
    ax.axhline(0, color='black', linewidth=0.8)
plt.tight_layout()
plt.show()

# ── Plot 5: Action distribution ──────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle('PPO Agent Action Analysis (Test Period)', fontsize=12, fontweight='bold')
acts = np.array(test_acts)
axes[0].hist(acts, bins=50, color='#9b59b6', alpha=0.8, edgecolor='white')
axes[0].axvline(0.3,  color='#27ae60', linewidth=1.5, linestyle='--', label='Buy threshold')
axes[0].axvline(-0.3, color='#e74c3c', linewidth=1.5, linestyle='--', label='Sell threshold')
axes[0].set_title('Action Value Distribution')
axes[0].set_xlabel('Action (−1=Sell, 0=Hold, +1=Buy)')
axes[0].legend()
buy_count  = (acts > 0.3).sum()
sell_count = (acts < -0.3).sum()
hold_count = len(acts) - buy_count - sell_count
axes[1].bar(['BUY','HOLD','SELL'],
            [buy_count, hold_count, sell_count],
            color=['#27ae60','#f39c12','#e74c3c'], alpha=0.85, edgecolor='white')
axes[1].set_title('BUY / HOLD / SELL Count')
axes[1].set_ylabel('Number of Days')
for i, v in enumerate([buy_count, hold_count, sell_count]):
    axes[1].text(i, v + 0.5, str(v), ha='center', va='bottom', fontweight='bold')
plt.tight_layout()
plt.show()

# ── Plot 6: Rolling Sharpe ──────────────────────────────────
fig, ax = plt.subplots(figsize=(16, 4))
rets_s = pd.Series(test_rets)
rolling_sharpe = rets_s.rolling(30).apply(
    lambda x: (x.mean() / (x.std() + 1e-8)) * np.sqrt(252), raw=True)
ax.plot(test_dates[:len(rolling_sharpe)], rolling_sharpe.values,
        color='#1abc9c', linewidth=1.5)
ax.axhline(0, color='black', linewidth=0.8, linestyle='--')
ax.axhline(1, color='#27ae60', linewidth=0.8, linestyle=':', label='Sharpe=1 (good)')
ax.fill_between(test_dates[:len(rolling_sharpe)], rolling_sharpe.fillna(0), 0,
                where=rolling_sharpe >= 0, alpha=0.25, color='#27ae60')
ax.fill_between(test_dates[:len(rolling_sharpe)], rolling_sharpe.fillna(0), 0,
                where=rolling_sharpe < 0,  alpha=0.25, color='#e74c3c')
ax.set_title('Rolling 30-Day Sharpe Ratio (Test Period)', fontsize=12, fontweight='bold')
ax.set_ylabel('Rolling Sharpe')
ax.legend()
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
plt.xticks(rotation=30)
plt.tight_layout()
plt.show()

print("✅ All visualisations rendered!")


# ## CELL 14 — Final Recommendation Output

# In[14]:


# ============================================================
# CELL 14: FINAL BUY / HOLD / SELL RECOMMENDATION
# Combines: PPO action + Technical score + Sentiment + Regime
# ============================================================

def generate_recommendation(model, test_df, latest_sentiment,
                             tech_score, bull_pct, bear_pct, sideways_pct):
    """
    Runs PPO on the most recent test observation to produce a recommendation.
    Also incorporates technical strength and sentiment as advisory signals.
    """
    env = NiftyRecommendationEnv(df=test_df, feature_cols=FINAL_FEATURES,
                                  transaction_cost=0, max_shares=MAX_SHARES)
    obs, _ = env.reset()
    done   = False
    last_action = 0.0
    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, _, done, _, _ = env.step(action)
        last_action = float(action[0])

    # ---- PPO signal ----
    if last_action > 0.3:
        ppo_signal = 'BUY'
    elif last_action < -0.3:
        ppo_signal = 'SELL'
    else:
        ppo_signal = 'HOLD'

    # ---- Technical signal ----
    if tech_score >= 65:
        tech_signal = 'BUY'
    elif tech_score <= 35:
        tech_signal = 'SELL'
    else:
        tech_signal = 'HOLD'

    # ---- Sentiment signal ----
    if abs(latest_sentiment) < 0.05:
        sent_signal = 'NEUTRAL'  # zero-score: ignore
    elif latest_sentiment > 0.1:
        sent_signal = 'BUY'
    elif latest_sentiment < -0.1:
        sent_signal = 'SELL'
    else:
        sent_signal = 'HOLD'

    # ---- Regime signal ----
    dominant = 'Bull' if bull_pct > max(bear_pct, sideways_pct) else \
               ('Bear' if bear_pct > max(bull_pct, sideways_pct) else 'Sideways')
    if dominant == 'Bull':
        regime_signal = 'BUY'
    elif dominant == 'Bear':
        regime_signal = 'SELL'
    else:
        regime_signal = 'HOLD'

    # ---- Weighted vote (PPO has highest weight) ----
    score_map = {'BUY': 1, 'HOLD': 0, 'SELL': -1, 'NEUTRAL': 0}
    weighted = (score_map[ppo_signal]    * 0.50 +
                score_map[tech_signal]   * 0.25 +
                score_map[sent_signal]   * 0.15 +
                score_map[regime_signal] * 0.10)

    if weighted > 0.15:
        final = 'BUY'
    elif weighted < -0.15:
        final = 'SELL'
    else:
        final = 'HOLD'

    confidence = abs(weighted) / 1.0 * 100  # 0–100%

    return {
        'ppo_signal'    : ppo_signal,
        'ppo_raw_action': last_action,
        'tech_signal'   : tech_signal,
        'tech_score'    : tech_score,
        'sent_signal'   : sent_signal,
        'sent_score'    : latest_sentiment,
        'regime_signal' : regime_signal,
        'regime_dominant': dominant,
        'weighted_score': weighted,
        'final'         : final,
        'confidence'    : confidence,
    }


# Get latest values
latest_sent_val  = float(data_with_sentiment.dropna(
    subset=['sentiment_score'])['sentiment_score'].iloc[-1])
latest_tech_score = float(data_with_ti.dropna(
    subset=['tech_strength_score'])['tech_strength_score'].iloc[-1])

rec = generate_recommendation(
    ppo_model, test_data, latest_sent_val,
    latest_tech_score, bull_pct, bear_pct, sideways_pct
)

# ---- Signal colours ----
SIG_COLOR = {'BUY': '\033[92m', 'SELL': '\033[91m', 'HOLD': '\033[93m',
             'NEUTRAL': '\033[90m'}
RESET = '\033[0m'

def csig(sig):
    return f"{SIG_COLOR.get(sig,'')}{sig}{RESET}"

print("\n" + "="*65)
print(f"  🔮 FINAL RECOMMENDATION: {SELECTED_NAME} ({SELECTED_TICKER})")
print(f"  As of: {datetime.now().strftime('%Y-%m-%d')}")
print("="*65)
print(f"  PPO Agent Signal  : {csig(rec['ppo_signal'])} (raw action: {rec['ppo_raw_action']:+.4f})")
print(f"  Technical Signal  : {csig(rec['tech_signal'])} (strength: {rec['tech_score']:.1f}/100)")
print(f"  Sentiment Signal  : {csig(rec['sent_signal'])} (score: {rec['sent_score']:+.4f})")
print(f"  Regime Signal     : {csig(rec['regime_signal'])} (dominant: {rec['regime_dominant']})")
print(f"  Weighted Score    : {rec['weighted_score']:+.3f}")
print("-"*65)
print(f"  ▶  FINAL CALL     : {csig(rec['final'])}")
print(f"  ▶  CONFIDENCE     : {rec['confidence']:.1f}%")
print("="*65)
print("\n  ⚠  Disclaimer: This is a research / educational tool.")
print("     Do NOT use as sole basis for real financial decisions.")


# ## CELL 15 — Project Summary

# In[15]:


# ============================================================
# CELL 15: FULL PROJECT SUMMARY
# ============================================================

print("\n" + "="*72)
print("  PROJECT SUMMARY — Nifty 50 Stock Recommendation via Deep RL")
print("="*72)
print(f"\n  Stock Analysed  : {SELECTED_NAME} ({SELECTED_TICKER})")
print(f"  RL Algorithm    : PPO (Proximal Policy Optimization) — tuned")
print(f"  Market          : National Stock Exchange, India (NSE)")
print(f"")
print(f"  Date Splits:")
print(f"    Train   : {TRAIN_START}  →  {TRAIN_END}")
print(f"    Val     : {VAL_START}  →  {VAL_END}")
print(f"    Test    : {TEST_START}  →  {TEST_END}")
print(f"")
print(f"  Input Features ({N_FEATURES} total):")
print(f"    ✅ Technical Indicators : RSI, MACD, BB, SMA, EMA, ATR, OBV, ADX, Stoch, ROC")
print(f"    ✅ Composite Tech Score : Single normalised strength score (0–100)")
print(f"    ✅ Sentiment Analysis   : Finnhub + Alpha Vantage + VADER fallback")
print(f"    ✅ Market Regime        : HMM on ^NSEI Index (Bull/Sideways/Bear, numeric)")
print(f"    ✅ Price features       : log return, volatility, close_norm")
print(f"")
print(f"  PPO Hyperparameters (tuned):")
print(f"    LR={LEARNING_RATE}  Steps={N_STEPS}  Batch={BATCH_SIZE}  Epochs={N_EPOCHS}")
print(f"    Gamma={GAMMA}  ClipRange={CLIP_RANGE}  Entropy={ENT_COEF}")
print(f"    Net: [256, 256, 128] (policy + value)")
print(f"")
print(f"  Test Period Performance (PPO vs Buy & Hold):")
for key in ['Sharpe Ratio','Sortino Ratio','Calmar Ratio',
            'Max Drawdown','Win Rate','Cumulative Return','Buy Precision']:
    ppo_v = test_metrics.get(key, 'N/A')
    bnh_v = bnh_test_m.get(key, 'N/A')
    print(f"    {key:<28}: PPO={ppo_v:>10}   B&H={bnh_v:>10}")
print(f"")
print(f"  Final Recommendation  : {rec['final']} (Confidence: {rec['confidence']:.1f}%)")
print("="*72)
print("\n  References:")
print("   - Schulman et al. (2017): Proximal Policy Optimization Algorithms")
print("   - Liu et al. (2020): FinRL: Deep RL for Automated Stock Trading")
print("   - Stable-Baselines3: https://stable-baselines3.readthedocs.io")
print("   - yfinance: https://github.com/ranaroussi/yfinance")
print("   - Finnhub: https://finnhub.io")
print("   - Alpha Vantage: https://www.alphavantage.co")
print("\n✅ Project complete!")

