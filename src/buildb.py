import duckdb
from pathlib import Path
import numpy as np

DATA_DIR = Path("__file__").resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "regime.duckdb"
TICKERS = ["GLD", "HYG", "SPY", "TLT", "USO"]
RV_WINDOW = 30
TOL = 1e-10

def latest(pattern) -> Path:
    files = sorted(DATA_DIR.glob(pattern))
    return files[-1]

def load_prices(con, path) -> None:
    con.execute("""
            CREATE OR REPLACE TABLE prices (
            ticker  VARCHAR NOT NULL,
            date    DATE NOT NULL,
            adj_close DOUBLE NOT NULL,
            PRIMARY KEY(ticker, date)
            )
        """)
    
    ticker_columns = ", ".join(TICKERS)
    con.execute(f"""
        INSERT INTO prices (ticker, date, adj_close)
        SELECT ticker, date::DATE, adj_close
        FROM read_parquet(?)
        UNPIVOT (adj_close FOR ticker IN ({ticker_columns}))
    """, [str(path)])


def create_feature_view(con) -> None:
    con.execute(f"""
        CREATE OR REPLACE VIEW features_sql AS
        WITH r AS (
            SELECT ticker, date,
                ln(adj_close / LAG(adj_close) OVER (PARTITION BY ticker ORDER BY date))
                    AS log_ret

            FROM prices   
            )
        SELECT ticker, date, log_ret,
            sqrt(252 * AVG(log_ret * log_ret) OVER w) AS rv{RV_WINDOW}
        FROM r
        WHERE log_ret IS NOT NULL
        WINDOW w AS (PARTITION BY ticker ORDER BY date
                    ROWS BETWEEN {RV_WINDOW -1} PRECEDING AND CURRENT ROW)
        QUALIFY COUNT(*) OVER w = {RV_WINDOW}
    """)

#ticker, date::DATE AS date, log_ret, rv{RV_WINDOW}
def check_against_pandas(con, path):
    safe = str(path).replace("'", "''")
    con.execute(f"""
        CREATE OR REPLACE VIEW features_pd AS
        SELECT * 
        FROM read_parquet('{safe}')
    """)
    n_sql, n_pd, n_matched, d_ret, d_rv = con.execute(f"""
        SELECT
            (SELECT COUNT(*) FROM features_sql),
            (SELECT COUNT(*) FROM features_pd),
            COUNT(*),
            MAX(ABS(s.log_ret - p.log_ret)),
            MAX(ABS(s.rv{RV_WINDOW} - p.rv{RV_WINDOW}))
        FROM features_sql s
        JOIN features_pd p USING (ticker, date)
    """).fetchone()

    print(f"rows sql={n_sql:,} pandas={n_pd:,} matched={n_matched:,}")
    print(f"max |diff| log_ret={d_ret:.2e} rv{RV_WINDOW}={d_rv:.2e}")
    #assert n_sql == n_pd == n_matched, "row sets differ: check partial window filtering"
    #assert d_ret < TOL and d_rv < TOL, "values differ: check formula / window frame"

def create_model_input_view(con):
    in_list = ", ".join(f"'{t}'" for t in TICKERS)
    con.execute("""
        CREATE OR REPLACE VIEW model_input AS
        PIVOT (SELECT date, ticker, log_ret, rv{RV_WINDOW} FROM features_sql)
        ON ticker IN ({in_list})
        USING first(log_ret) AS ret, first(rv_{RV_WINDOW}) AS rv
        GROUP BY date
    """)

def load_model_input(con):
    rel = con.sql("SELECT * FROM model_input ORDER BY date")
    cols = [c for c in rel.columns if c!= "date"]
    data = rel.fetchnumpy()
    X = np.column_stack([data[c] for c in cols]).astype(np.float32)
    return data["date"], X, cols

if __name__ == "__main__":
    prices_path = latest("prices*.parquet")
    lr_rv_path = latest("lr_rv.parquet")
    con = duckdb.connect(str(DB_PATH))

    load_prices(con, prices_path)
    create_feature_view(con)
    check_against_pandas(con, lr_rv_path)
    create_model_input_view(con)
    dates, X, cols = load_model_input(con)
    assert not np.isnan(X).any(), "NaN in model input"
    print(f"model_input: X {X.shape}, {dates[0]} -> {dates[-1]}")
    print(f"columns: {cols}")

    con.close()
    print(f"saved {DB_PATH}")

    
