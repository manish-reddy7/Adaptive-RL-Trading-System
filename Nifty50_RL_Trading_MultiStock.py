# %% [markdown]
# # 📈 Nifty 50 Stock Trading Recommendation System (Multi-Stock Optimized)
# ## Deep Reinforcement Learning (PPO) + Technical Analysis + Sentiment Analysis + Market Regime
# 
# **Framework:** Custom PPO (Proximal Policy Optimization) via Stable-Baselines3  
# **Market:** Indian Stock Market (NSE — Yahoo Finance .NS suffix)  
# **Optimization:** Local Caching (Data/Models) + Parallel Execution
# 
# ### Pipeline:
# 1. Download OHLCV data & detect global Market Regime.
# 2. For each stock (Parallelized):
#    - Fetch news/sentiment or load from cache.
#    - Compute technical indicators or load feature-engineered data from cache.
#    - Load pre-trained PPO model from disk OR train/save if missing.
#    - Run backtest and generate recommendation.
# 3. Output consolidated results for all 10 stocks.

# %%
# ============================================================
# CELL 1: INSTALL & IMPORTS
# ============================================================
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from datetime import datetime, timedelta
import os
import requests
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import yfinance as yf
import ta
from ta.trend import MACD, SMAIndicator, EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator, StochasticOscillator, ROCIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from hmmlearn import hmm

import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from sklearn.preprocessing import StandardScaler

print("✅ Imports successful!")

# %%
# ============================================================
# CELL 2: CONFIGURATION
# ============================================================
FINNHUB_API_KEY  = "d7np7rpr01qm36379ongd7np7rpr01qm36379oo0"
NEWSAPI_KEY      = "8d4a630796c94756b96a16efdf92f489"

# ---- PERSISTENCE SETTINGS ----
CACHE_DIR        = "cache"
MODEL_DIR        = "trained_models"
LOG_DIR          = "logs"
FORCE_RETRAIN    = False  # Set to True to ignore saved models
FORCE_REFETCH    = False  # Set to True to ignore cached data/sentiment
CONCURRENCY      = 2      # Number of stocks to process at once (GPU dependent)

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

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

TRAIN_START = "2016-01-01"
TRAIN_END   = "2023-12-31"
VAL_START   = "2024-01-01"
VAL_END     = "2024-12-31"
TEST_START  = "2025-01-01"
TEST_END    = datetime.now().strftime("%Y-%m-%d")
FULL_START  = TRAIN_START
FULL_END    = TEST_END

TRANSACTION_COST = 0.001
MAX_SHARES       = 100
DUMMY_CAPITAL    = 1000000
TOTAL_TIMESTEPS  = 500000
LEARNING_RATE    = 0.0001
N_STEPS          = 1024
BATCH_SIZE       = 128
N_EPOCHS         = 15
GAMMA            = 0.995
GAE_LAMBDA       = 0.95
CLIP_RANGE       = 0.15
ENT_COEF         = 0.005
VF_COEF          = 0.5
MAX_GRAD_NORM    = 0.5

RSI_WINDOW, MACD_FAST, MACD_SLOW, MACD_SIGNAL, BB_WINDOW, SMA_SHORT, SMA_LONG, ATR_WINDOW, ADX_WINDOW, ROC_WINDOW = 14, 12, 26, 9, 20, 10, 50, 14, 14, 10
N_REGIMES, REGIME_LOOKBACK, SEED = 3, 60, 42
np.random.seed(SEED)

FEATURE_COLS = [
    'close_norm', 'daily_return', 'log_return', 'volatility_10',
    'macd', 'macd_signal', 'macd_hist', 'sma_10', 'sma_50', 'ema_20',
    'rsi', 'stoch_k', 'stoch_d', 'roc', 'bb_pct', 'bb_width', 'atr',
    'obv', 'adx', 'sentiment_score', 'regime_score', 'tech_strength_score'
]

# %%
# ============================================================
# CELL 3: DATA ENGINE
# ============================================================
vader = SentimentIntensityAnalyzer()
def score_text(text):
    if not text or not isinstance(text, str): return None
    return vader.polarity_scores(text)['compound']

def fetch_finnhub_sentiment(symbol, api_key, days=365):
    end_dt, start_dt = datetime.now(), datetime.now() - timedelta(days=days)
    url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={start_dt.strftime('%Y-%m-%d')}&to={end_dt.strftime('%Y-%m-%d')}&token={api_key}"
    headlines_top = []
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            news = r.json()
            if isinstance(news, list) and len(news) > 0:
                records = []
                for item in news:
                    headline = item.get('headline', '')
                    if headline and len(headlines_top) < 5 and headline not in headlines_top: headlines_top.append(headline)
                    score = score_text(headline)
                    if score is not None:
                        dt = pd.to_datetime(item.get('datetime', 0), unit='s')
                        records.append({'date': dt.date(), 'sentiment_score': score})
                if records:
                    df = pd.DataFrame(records)
                    df['date'] = pd.to_datetime(df['date'])
                    return df.groupby('date')['sentiment_score'].mean().reset_index(), headlines_top
    except: pass
    return pd.DataFrame(), headlines_top

def fetch_newsapi_sentiment(query, api_key, days=29):
    cutoff, headlines_top = datetime.now() - timedelta(days=days), []
    url = f"https://newsapi.org/v2/everything?q={query}&from={cutoff.strftime('%Y-%m-%d')}&sortBy=popularity&language=en&apiKey={api_key}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            articles = data.get('articles', [])
            if articles:
                records = []
                for item in articles:
                    dt_str = item.get('publishedAt', '')[:10]
                    if not dt_str: continue
                    dt = datetime.strptime(dt_str, '%Y-%m-%d')
                    headline = item.get('title', '')
                    if headline and len(headlines_top) < 5 and headline not in headlines_top: headlines_top.append(headline)
                    score = score_text(headline) or score_text(item.get('description', '')) or 0
                    records.append({'date': dt, 'sentiment_score': score})
                if records:
                    df = pd.DataFrame(records)
                    df['date'] = pd.to_datetime(df['date'])
                    return df.groupby('date')['sentiment_score'].mean().reset_index(), headlines_top
    except: pass
    return pd.DataFrame(), headlines_top

def build_sentiment_column(stock_df, ticker, finnhub_key, newsapi_key):
    cache_path = os.path.join(CACHE_DIR, f"sentiment_{ticker}.csv")
    if not FORCE_REFETCH and os.path.exists(cache_path):
        cached = pd.read_csv(cache_path, parse_dates=['date'])
        # Simplified: top headlines aren't cached but were printed once
        return stock_df.merge(cached, on='date', how='left').fillna(0), []
    
    ticker_base = ticker.replace('.NS', '')
    fh_df, fh_head = fetch_finnhub_sentiment("BSE:" + ticker_base, finnhub_key)
    news_df, news_head = fetch_newsapi_sentiment(ticker_base, newsapi_key)
    top_headlines = list(set(fh_head + news_head))[:5]
    
    parts = [p for p in [fh_df, news_df] if not p.empty]
    if parts:
        combined = pd.concat(parts).groupby('date')['sentiment_score'].mean().reset_index()
        combined['date'] = pd.to_datetime(combined['date'])
        combined.to_csv(cache_path, index=False)
        result = stock_df.merge(combined, on='date', how='left')
    else:
        result = stock_df.copy()
        result['sentiment_score'] = 0.0
    
    result['sentiment_score'] = result['sentiment_score'].fillna(0.0)
    return result, top_headlines

def add_technical_indicators(df):
    df = df.copy().sort_values('date')
    close, high, low, volume = df['close'], df['high'], df['low'], df['volume']
    df['rsi'] = RSIIndicator(close=close, window=RSI_WINDOW).rsi()
    macd_ind = MACD(close=close, window_fast=MACD_FAST, window_slow=MACD_SLOW, window_sign=MACD_SIGNAL)
    df['macd'], df['macd_signal'], df['macd_hist'] = macd_ind.macd(), macd_ind.macd_signal(), macd_ind.macd_diff()
    bb = BollingerBands(close=close, window=BB_WINDOW)
    df['bb_pct'], df['bb_width'] = bb.bollinger_pband(), bb.bollinger_wband()
    df['sma_10'], df['sma_50'] = SMAIndicator(close=close, window=SMA_SHORT).sma_indicator(), SMAIndicator(close=close, window=SMA_LONG).sma_indicator()
    df['ema_20'], df['atr'] = EMAIndicator(close=close, window=20).ema_indicator(), AverageTrueRange(high=high, low=low, close=close, window=ATR_WINDOW).average_true_range()
    df['obv'], df['adx'] = OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume(), ADXIndicator(high=high, low=low, close=close, window=ADX_WINDOW).adx()
    stoch = StochasticOscillator(high=high, low=low, close=close)
    df['stoch_k'], df['stoch_d'], df['roc'] = stoch.stoch(), stoch.stoch_signal(), ROCIndicator(close=close, window=ROC_WINDOW).roc()
    df['daily_return'], df['log_return'] = close.pct_change(), np.log(close / close.shift(1))
    df['volatility_10'], df['close_norm'] = df['daily_return'].rolling(10).std(), (close - close.rolling(50).mean()) / (close.rolling(50).std() + 1e-8)
    return df

def compute_technical_strength_score(df):
    df = df.copy()
    signals = pd.DataFrame(index=df.index)
    signals['rsi_sig'] = df['rsi'].clip(0, 100) / 100
    macd_h = df['macd_hist']
    signals['macd_sig'] = ((macd_h - macd_h.min()) / (macd_h.max() - macd_h.min() + 1e-8)).clip(0, 1)
    signals['bb_sig'] = df['bb_pct'].clip(0, 1)
    signals['sma_cross_sig'] = (df['close'] > df['sma_50']).astype(float)
    signals['ema_sig'] = (df['close'] > df['ema_20']).astype(float)
    signals['adx_sig'] = ((df['adx'] - 10) / 40).clip(0, 1)
    signals['stoch_sig'] = df['stoch_k'].clip(0, 100) / 100
    roc = df['roc']
    signals['roc_sig'] = ((roc - roc.min()) / (roc.max() - roc.min() + 1e-8)).clip(0, 1)
    obv_ma = df['obv'].rolling(20).mean()
    signals['obv_sig'] = (df['obv'] > obv_ma).astype(float)
    atr_norm = (df['atr'] / (df['close'] + 1e-8))
    signals['atr_sig'] = (1 - atr_norm.clip(0, 0.1) / 0.1).clip(0, 1)
    df['tech_strength_score'] = signals.mean(axis=1) * 100
    return df

# %%
# ============================================================
# CELL 4: RL ENVIRONMENT
# ============================================================
class NiftyRecommendationEnv(gym.Env):
    def __init__(self, df, feature_cols):
        super().__init__()
        self.df, self.feature_cols = df.reset_index(drop=True), feature_cols
        self.dates = sorted(df['date'].unique())
        self.n_days = len(self.dates)
        self.action_space = spaces.Box(low=-1, high=1, shape=(1,), dtype=np.float32)
        self.observation_space = spaces.Box(low=-10, high=10, shape=(1 + len(feature_cols) + 1,), dtype=np.float32)
        self.reset()
    def _obs(self):
        if self.current_step >= len(self.df): return np.zeros(self.observation_space.shape, dtype=np.float32)
        row = self.df.iloc[self.current_step]
        return np.nan_to_num(np.concatenate([[self.position], row[self.feature_cols].values, [row['close_norm']]]), nan=0.0).astype(np.float32)
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.balance = float(DUMMY_CAPITAL)
        self.shares_held = 0
        self.position = 0.0
        self.portfolio_hist = [DUMMY_CAPITAL]
        self.returns_hist = []
        self.actions_hist = []  # Track raw scalar actions
        return self._obs(), {}
    def step(self, action):
        row, action_scalar = self.df.iloc[self.current_step], float(action[0])
        self.actions_hist.append(action_scalar)
        price = float(row['close'])
        if action_scalar > 0.3:
            n = min(int((self.balance * 0.3) / (price * (1+TRANSACTION_COST))), MAX_SHARES)
            if n > 0: self.balance -= n*price*(1+TRANSACTION_COST); self.shares_held += n; self.position = min(1.0, self.position+0.3)
        elif action_scalar < -0.3:
            n = min(self.shares_held, max(1, int(self.shares_held * 0.5)))
            if n > 0: self.balance += n*price*(1-TRANSACTION_COST); self.shares_held -= n; self.position = max(-1.0, self.position-0.3)
        self.current_step += 1
        done = self.current_step >= self.n_days - 1
        val = self.balance + self.shares_held * (float(self.df.iloc[self.current_step]['close']) if not done else price)
        ret = (val - self.portfolio_hist[-1]) / (self.portfolio_hist[-1] + 1e-8)
        self.portfolio_hist.append(val); self.returns_hist.append(ret)
        reward = ret * 100
        if len(self.returns_hist) >= 20:
            ra = np.array(self.returns_hist[-20:])
            reward = (ra.mean() / (ra.std() + 1e-8) - max(0, (max(self.portfolio_hist) - val) / max(self.portfolio_hist)) * 0.5) * 10
        return self._obs(), float(reward), done, False, {}

# %%
# ============================================================
# CELL 5: CORE PIPELINE RUNNER
# ============================================================
def process_stock(ticker, name, regime_df, bull_pct, bear_pct, sideways_pct):
    try:
        print(f"🚀 Processing {name} ({ticker})...")
        cache_feat = os.path.join(CACHE_DIR, f"features_{ticker}.csv")
        
        if not FORCE_REFETCH and os.path.exists(cache_feat):
            df = pd.read_csv(cache_feat, parse_dates=['date'])
            tops = []
        else:
            df = yf.download(ticker, start=FULL_START, end=FULL_END, progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.reset_index()
            df.columns = [str(c).lower().strip() for c in df.columns]
            if 'date' not in df.columns and 'index' in df.columns:
                df.rename(columns={'index':'date'}, inplace=True)
            df['date'] = pd.to_datetime(df['date'])
            df = add_technical_indicators(df)
            df = compute_technical_strength_score(df)
            df = df.merge(regime_df, on='date', how='left').fillna(method='ffill').fillna(1)
            df, tops = build_sentiment_column(df, ticker, FINNHUB_API_KEY, NEWSAPI_KEY)
            df.replace([np.inf, -np.inf], np.nan, inplace=True)
            df[FEATURE_COLS] = df[FEATURE_COLS].ffill().bfill().fillna(0)
            df.to_csv(cache_feat, index=False)

        # Scale for RL
        df_rl = df.copy()
        scaler = StandardScaler()
        df_rl[FEATURE_COLS] = scaler.fit_transform(df_rl[FEATURE_COLS])
        train_data = df_rl[(df_rl['date'] >= TRAIN_START) & (df_rl['date'] <= TRAIN_END)].copy()
        test_data = df_rl[(df_rl['date'] >= TEST_START) & (df_rl['date'] <= TEST_END)].copy()

        env = DummyVecEnv([lambda: Monitor(NiftyRecommendationEnv(train_data, FEATURE_COLS))])
        mod_path = os.path.join(MODEL_DIR, f"PPO_{ticker}")
        
        # Robust loading for .zip or no-extension legacy files
        if not FORCE_RETRAIN and (os.path.exists(mod_path + ".zip") or os.path.exists(mod_path)):
            load_path = mod_path + ".zip" if os.path.exists(mod_path + ".zip") else mod_path
            print(f"📂 Loading existing trained model for {ticker} from {load_path}...")
            ppo = PPO.load(load_path, env=env, device='cuda')
        else:
            ppo = PPO("MlpPolicy", env, learning_rate=LEARNING_RATE, n_steps=N_STEPS, batch_size=BATCH_SIZE, n_epochs=N_EPOCHS, gamma=GAMMA, gae_lambda=GAE_LAMBDA, clip_range=CLIP_RANGE, ent_coef=ENT_COEF, vf_coef=VF_COEF, max_grad_norm=MAX_GRAD_NORM, verbose=0, seed=SEED, device='cuda')
            print(f"🤖 Training PPO for {ticker}...")
            ppo.learn(total_timesteps=TOTAL_TIMESTEPS); ppo.save(mod_path)
            print(f"✅ Saved model to {mod_path}.zip")

        # Eval
        tenv = NiftyRecommendationEnv(test_data, FEATURE_COLS)
        obs, _ = tenv.reset(); done = False; last_a = 0
        while not done:
            a, _ = ppo.predict(obs, deterministic=True); obs, _, done, _, _ = tenv.step(a); last_a = float(a[0])
        
        v = np.array(tenv.portfolio_hist); r = np.array(tenv.returns_hist); acts = np.array(tenv.actions_hist)
        cum_ret = (v[-1]/v[0]-1)
        # Annualized Return
        days = len(r)
        ann_ret = (1 + cum_ret)**(252/days) - 1 if days > 0 else 0
        # Sharpe
        sharpe = (r.mean()/(r.std()+1e-8))*np.sqrt(252) if len(r)>0 else 0
        # Sortino
        neg_r = r[r < 0]
        sortino = (r.mean()/(neg_r.std()+1e-8))*np.sqrt(252) if len(neg_r)>0 else 0
        # Max Drawdown
        peaks = np.maximum.accumulate(v)
        drawdowns = (peaks - v) / peaks
        max_dd = np.max(drawdowns)
        # Calmar
        calmar = ann_ret / max_dd if max_dd > 0 else 0
        # Win Rate
        win_rate = np.sum(r > 0) / len(r) if len(r) > 0 else 0
        # Buy/Sell Precision
        buys = acts > 0.3
        sells = acts < -0.3
        # Direct alignment: r[i] is the return resulting from acts[i]
        buy_prec = np.sum(r[buys] > 0) / np.sum(buys) if np.sum(buys) > 0 else 0
        sell_prec = np.sum(r[sells] < 0) / np.sum(sells) if np.sum(sells) > 0 else 0
        
        s_m = {'BUY':1,'HOLD':0,'SELL':-1,'NEUTRAL':0}
        p_s = 'BUY' if last_a > 0.3 else 'SELL' if last_a < -0.3 else 'HOLD'
        t_s = 'BUY' if df['tech_strength_score'].iloc[-1] >= 65 else 'SELL' if df['tech_strength_score'].iloc[-1] <= 35 else 'HOLD'
        sent_v = df['sentiment_score'].iloc[-1]
        sn_s = 'BUY' if sent_v > 0.1 else 'SELL' if sent_v < -0.1 else 'NEUTRAL' if abs(sent_v) < 0.05 else 'HOLD'
        dom = 'Bull' if bull_pct > max(bear_pct, sideways_pct) else 'Bear' if bear_pct > max(bull_pct, sideways_pct) else 'Sideways'
        rg_s = 'BUY' if dom == 'Bull' else 'SELL' if dom == 'Bear' else 'HOLD'
        w = s_m[p_s]*0.5 + s_m[t_s]*0.25 + s_m[sn_s]*0.15 + s_m[rg_s]*0.10
        f_s = 'BUY' if w > 0.15 else 'SELL' if w < -0.15 else 'HOLD'
        
        return {
            'Ticker': ticker, 'Name': name, 'FINAL SIGNAL': f_s, 
            'Sharpe Ratio': f"{sharpe:.2f}",
            'Sortino Ratio': f"{sortino:.2f}",
            'Calmar Ratio': f"{calmar:.2f}",
            'Max Drawdown': f"{max_dd*100:.2f}%",
            'Win Rate': f"{win_rate*100:.1f}%",
            'Buy Precision': f"{buy_prec*100:.1f}%",
            'Sell Precision': f"{sell_prec*100:.1f}%",
            'Cumulative Return': f"{cum_ret*100:.2f}%",
            'Annualised Return': f"{ann_ret*100:.2f}%",
            'Headlines': tops
        }
    except Exception as e:
        print(f"❌ Error in {ticker}: {e}"); return None

# %%
# ============================================================
# CELL 6: COMPUTE REGIME (EXPORTABLE FOR API)
# ============================================================
def compute_regime():
    """
    Compute market regime for all stocks
    Returns: (nifty_data, regime_df, bull_pct, bear_pct, sideways_pct)
    """
    n_idx = yf.download("^NSEI", start=FULL_START, end=FULL_END, progress=False, auto_adjust=True)
    if isinstance(n_idx.columns, pd.MultiIndex):
        n_idx.columns = n_idx.columns.get_level_values(0)
    n_idx = n_idx.reset_index()
    n_idx.columns = [str(c).lower().strip() for c in n_idx.columns]
    
    # Standardize column names
    if 'date' not in n_idx.columns and 'index' in n_idx.columns:
        n_idx.rename(columns={'index':'date'}, inplace=True)
    
    n_idx['date'] = pd.to_datetime(n_idx['date'])
    
    # Global Regime (NSE Index)
    ret = np.log(n_idx['close'] / n_idx['close'].shift(1)).dropna()
    vol = ret.rolling(60).std().fillna(0)
    h_m = hmm.GaussianHMM(n_components=3, covariance_type='full', n_iter=500, random_state=SEED).fit(np.column_stack([ret.values[59:], vol.values[59:]]))
    st = h_m.predict(np.column_stack([ret.values[59:], vol.values[59:]]))
    m_r = {s: ret.values[59:][st == s].mean() for s in range(3)}; s_s = sorted(m_r, key=m_r.get)
    r_map = {s_s[0]:0, s_s[1]:1, s_s[2]:2}
    reg_df = pd.DataFrame({'date': n_idx['date'].values[60:], 'regime_score': [r_map[s] for s in st]})
    counts = reg_df['regime_score'].value_counts(normalize=True)*100
    b_p, br_p, s_p = counts.get(2,0), counts.get(0,0), counts.get(1,0)
    
    # Return data for external use
    nifty_data = n_idx.iloc[60:].copy()
    nifty_data = nifty_data.merge(reg_df, on='date', how='left')
    
    return nifty_data, reg_df, b_p, br_p, s_p

# %%
# ============================================================
# CELL 7: EXECUTION
# ============================================================
if __name__ == "__main__":
    n_idx = yf.download("^NSEI", start=FULL_START, end=FULL_END, progress=False, auto_adjust=True)
    if isinstance(n_idx.columns, pd.MultiIndex):
        n_idx.columns = n_idx.columns.get_level_values(0)
    n_idx = n_idx.reset_index()
    n_idx.columns = [str(c).lower().strip() for c in n_idx.columns]
    
    # Standardize column names
    if 'date' not in n_idx.columns and 'index' in n_idx.columns:
        n_idx.rename(columns={'index':'date'}, inplace=True)
    
    n_idx['date'] = pd.to_datetime(n_idx['date'])
    
    # Global Regime (NSE Index)
    ret = np.log(n_idx['close'] / n_idx['close'].shift(1)).dropna()
    vol = ret.rolling(60).std().fillna(0)
    h_m = hmm.GaussianHMM(n_components=3, covariance_type='full', n_iter=500, random_state=SEED).fit(np.column_stack([ret.values[59:], vol.values[59:]]))
    st = h_m.predict(np.column_stack([ret.values[59:], vol.values[59:]]))
    m_r = {s: ret.values[59:][st == s].mean() for s in range(3)}; s_s = sorted(m_r, key=m_r.get)
    r_map = {s_s[0]:0, s_s[1]:1, s_s[2]:2}
    reg_df = pd.DataFrame({'date': n_idx['date'].values[60:], 'regime_score': [r_map[s] for s in st]})
    counts = reg_df['regime_score'].value_counts(normalize=True)*100
    b_p, br_p, s_p = counts.get(2,0), counts.get(0,0), counts.get(1,0)

    print(f"🌍 Overall Market Regime: Bull {b_p:.1f}% | Bear {br_p:.1f}% | Sideways {s_p:.1f}%")
    
    results = []
    # Using ProcessPoolExecutor for true parallelism
    with ProcessPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(process_stock, tick, name, reg_df, b_p, br_p, s_p) for stock_id, (tick, name) in STOCK_OPTIONS.items()]
        for f in as_completed(futures):
            res = f.result()
            if res: results.append(res)
    
    res_df = pd.DataFrame(results).drop(columns=['Headlines'])
    import IPython.display as display
    display.display(res_df)
    
    print("\n📰 TOP HEADLINES PER STOCK:")
    for r in results:
        if r['Headlines']:
            print(f"\n{r['Ticker']}:")
            for h in r['Headlines']: print(f"  - {h}")
