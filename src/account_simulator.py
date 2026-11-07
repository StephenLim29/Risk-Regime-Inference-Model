import duckdb
import pandas as pd
from pathlib import Path
import numpy as np

DATA_DIR = Path("__file__").resolve().parent.parent / "data"
RET_PATH = DATA_DIR / "lr_rv.parquet"
DB_PATH = DATA_DIR / "regime.duckdb"

c = 0.0005

def initialize(con):

    # simple return df
    simple = pd.read_parquet(RET_PATH)
    simple['log_ret'] = np.exp(simple['log_ret']) - 1 # simple returns
    simple = simple.pivot(
        index="date",
        columns="ticker",
        values=["log_ret"]
    ).reset_index()
    simple.rename(columns={"log_ret": "simple_ret"})

    # rebalance dates
    con.execute("""
            CREATE OR REPLACE VIEW rebalance AS
                SELECT
                    MAX(date) AS date
                FROM calendar
                GROUP BY DATE_TRUNC('month', date)
                ORDER BY date
        """)
    # target weight dataframes

    # add strategies
    con.execute("""
        -- 1. Spec table: what each static strategy holds
        CREATE OR REPLACE TABLE strategy_spec AS
        SELECT strategy, ticker, CAST(weight AS DOUBLE) AS weight
        FROM (VALUES
            ('equal_weight', 'SPY', 0.20),
            ('equal_weight', 'TLT', 0.20),
            ('equal_weight', 'GLD', 0.20),
            ('equal_weight', 'USO', 0.20),
            ('equal_weight', 'HYG', 0.20),
            ('60_40',        'SPY', 0.60),
            ('60_40',        'TLT', 0.40),
            ('60_40',        'GLD', 0.00),
            ('60_40',        'USO', 0.00),
            ('60_40',        'HYG', 0.00)
        ) AS t(strategy, ticker, weight);

        -- 2. Target weights table (long format)
        CREATE TABLE IF NOT EXISTS target_weights (
            strategy VARCHAR,
            date     DATE,
            ticker   VARCHAR,
            weight   DOUBLE,
            PRIMARY KEY (strategy, date, ticker)
        );

        -- 3. Rerunnable: clear the static strategies, then rebuild them
        DELETE FROM target_weights
        WHERE strategy IN (SELECT DISTINCT strategy FROM strategy_spec);

        INSERT INTO target_weights
        SELECT s.strategy, m.date, s.ticker, s.weight
        FROM strategy_spec AS s
        CROSS JOIN rebalance AS m
        WHERE m.date >= DATE '2010-12-31';   -- start of out-of-sample period

        -- 4. Validation: both queries should return zero rows
        SELECT strategy, date, COUNT(*) AS n
        FROM target_weights
        GROUP BY strategy, date
        HAVING COUNT(*) <> 5;

        SELECT strategy, date, SUM(weight) AS total
        FROM target_weights
        GROUP BY strategy, date
        HAVING ABS(SUM(weight) - 1) > 1e-9;
    """)
    
def step(target_weights, returns, c):
    gross_return = 0
    turnover = 0
    cost = 0
    net_return = 0
    nav = 0

    out_df = pd.DataFrame({
        "gross_return",
        "turnover",
        "cost",
        "net_return",
        "nav"
    })

    return out_df

if __name__== "__main__":
    con = duckdb.connect(str(DB_PATH))
    initialize(con)
    print(con.sql("""
        SELECT *
        FROM target_weights
        LIMIT 400
    """))
