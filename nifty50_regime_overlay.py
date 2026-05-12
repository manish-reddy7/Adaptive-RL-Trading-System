import warnings
warnings.filterwarnings("ignore")

from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import yfinance as yf
from hmmlearn import hmm
from sklearn.preprocessing import StandardScaler
from typing import cast


START_DATE = "2015-01-01"
END_DATE = (datetime.now().date() + timedelta(days=1)).isoformat()
TICKER = "^NSEI"
OUTPUT_FILE = "nifty50_price_regime_overlay.png"
SEED = 42


sns.set_theme(style="whitegrid", context="talk")
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#222222",
    "axes.labelcolor": "#222222",
    "xtick.color": "#222222",
    "ytick.color": "#222222",
    "text.color": "#222222",
    "font.family": "DejaVu Sans",
})


REGIME_STYLES = {
    0: {"label": "Bear", "color": "#e74c3c", "alpha": 0.16},
    1: {"label": "Sideways", "color": "#f39c12", "alpha": 0.16},
    2: {"label": "Bull", "color": "#2ecc71", "alpha": 0.14},
}


def download_nifty_index() -> pd.DataFrame:
    raw = yf.download(TICKER, start=START_DATE, end=END_DATE, progress=False, auto_adjust=True)
    if raw is None:
        raise RuntimeError("No data returned for ^NSEI.")

    df = cast(pd.DataFrame, raw)
    if df.empty:
        raise RuntimeError("No data downloaded for ^NSEI.")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    df = df.reset_index()
    df.columns = [str(c).lower().strip() for c in df.columns]

    if "date" not in df.columns:
        raise RuntimeError("Downloaded data does not contain a date column.")
    if "close" not in df.columns:
        raise RuntimeError("Downloaded data does not contain a close column.")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").dropna(subset=["close"]).reset_index(drop=True)
    return df


def detect_regimes(df: pd.DataFrame, n_regimes: int = 3, lookback: int = 21) -> pd.DataFrame:
    work = df.copy()
    work["log_return"] = np.log(work["close"] / work["close"].shift(1))
    work["volatility"] = work["log_return"].rolling(lookback).std()
    work = work.dropna(subset=["log_return", "volatility"]).reset_index(drop=True)

    features = work[["log_return", "volatility"]].values
    features = StandardScaler().fit_transform(features)

    model = hmm.GaussianHMM(
        n_components=n_regimes,
        covariance_type="full",
        n_iter=500,
        random_state=SEED,
        tol=1e-5,
    )
    model.fit(features)
    raw_states = model.predict(features)
    work["regime_raw"] = raw_states

    mean_ret_by_state: dict[int, float] = {
        state: float(work.loc[work["regime_raw"] == state, "log_return"].mean())
        for state in range(n_regimes)
    }
    ordered_states = sorted(mean_ret_by_state.keys(), key=lambda state: mean_ret_by_state[state])
    regime_map = {
        ordered_states[0]: 0,
        ordered_states[1]: 1,
        ordered_states[2]: 2,
    }
    work["regime_score"] = work["regime_raw"].map(regime_map).astype(int)
    return work[["date", "close", "regime_score"]].copy()


def build_segments(regime_df: pd.DataFrame):
    segments = []
    if regime_df.empty:
        return segments

    start_idx = 0
    current_regime = int(regime_df.iloc[0]["regime_score"])
    for idx in range(1, len(regime_df)):
        regime = int(regime_df.iloc[idx]["regime_score"])
        if regime != current_regime:
            segments.append((
                regime_df.iloc[start_idx]["date"],
                regime_df.iloc[idx - 1]["date"],
                current_regime,
            ))
            start_idx = idx
            current_regime = regime

    segments.append((
        regime_df.iloc[start_idx]["date"],
        regime_df.iloc[-1]["date"],
        current_regime,
    ))
    return segments


def plot_nifty_regime_overlay(price_df: pd.DataFrame, regime_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(16, 8))

    segments = build_segments(regime_df)
    for start, end, regime in segments:
        style = REGIME_STYLES[regime]
        ax.axvspan(start, end, color=style["color"], alpha=style["alpha"], lw=0)

    ax.plot(
        price_df["date"],
        price_df["close"],
        color="#111111",
        linewidth=1.8,
        label="Nifty 50 Close",
        zorder=3,
    )

    ax.set_title("Nifty 50 Price with Regime Overlay", fontsize=18, fontweight="bold", pad=16)
    ax.set_xlabel("Time (Years)", fontsize=12)
    ax.set_ylabel("Price Level", fontsize=12)

    ax.xaxis.set_major_locator(mdates.YearLocator(base=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.grid(True, which="major", axis="both", alpha=0.14)
    ax.grid(True, which="minor", axis="x", alpha=0.06)

    legend_handles = [
        Line2D([0], [0], color="#111111", lw=2, label="Nifty 50 Close"),
        mpatches.Patch(color=REGIME_STYLES[2]["color"], alpha=REGIME_STYLES[2]["alpha"], label="Bull"),
        mpatches.Patch(color=REGIME_STYLES[0]["color"], alpha=REGIME_STYLES[0]["alpha"], label="Bear"),
        mpatches.Patch(color=REGIME_STYLES[1]["color"], alpha=REGIME_STYLES[1]["alpha"], label="Sideways"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", frameon=True, framealpha=0.95, facecolor="white")

    ax.margins(x=0)
    fig.tight_layout()
    fig.savefig(OUTPUT_FILE, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    price_df = download_nifty_index()
    regime_df = detect_regimes(price_df)
    plot_nifty_regime_overlay(price_df, regime_df)
    print(f"Saved {OUTPUT_FILE}")
