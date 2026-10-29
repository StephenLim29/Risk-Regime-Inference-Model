import yfinance as yf
from pathlib import Path
import pandas as pd
import numpy as np

# Tickers used: SPY, TLT, GLD, USO, HYG

TICKERS = ["SPY", "TLT", "GLD", "USO", "HYG"]
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def download_ohlcv(start="2007-05-01"):
    DATA_DIR.mkdir(exist_ok=True)
    df = yf.download(TICKERS, start=start, auto_adjust=True, progress=False)
    df.to_csv(DATA_DIR / "ohlcv.csv")
    df.to_parquet(DATA_DIR / "ohlcv.parquet")
    return True

def download_prices(start="2007-05-01"):
    DATA_DIR.mkdir(exist_ok=True)
    df = yf.download(TICKERS, start=start, auto_adjust=True, progress=False)
    close = df["Close"].dropna(how="all")
    close.to_csv(DATA_DIR / "prices.csv")
    close.to_parquet(DATA_DIR / "prices.parquet")
    return close

def lr_and_rv(data_path):
    # start date is 1 day after first day to track change
    # r = ln(p_t / p_t-1)
    DATA_DIR.mkdir(exist_ok=True)
    prices = pd.read_csv(data_path, index_col="Date", parse_dates=True)
    log_returns = np.log(prices).diff()
    rolling_volatility = np.sqrt((log_returns**2).rolling(30).mean())

    log_returns_long = log_returns.stack().rename("log_ret")
    rv_long = rolling_volatility.stack().rename("rv30")

    combined = (
        pd.concat([log_returns_long, rv_long], axis=1)
        .dropna()
        .rename_axis(index=["date", "ticker"])
        .reset_index()
    )

    combined.to_parquet(DATA_DIR / "lr_rv.parquet", index=False)
    return True

if __name__ == "__main__":
    #print(download_prices().tail())
    print(lr_and_rv(DATA_DIR / "prices.csv"))
    #print(download_ohlcv())
    print("success")