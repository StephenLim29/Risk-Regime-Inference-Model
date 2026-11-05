import duckdb
from pathlib import Path

n_min_start = None
n_min_end = None
s = 1
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "regime.duckdb"

con = duckdb.connect(str(DB_PATH))

def calendar(con):
    con.execute("""
        CREATE OR REPLACE VIEW calendar AS
        WITH valid_dates AS (
            SELECT date
            FROM features_sql
            WHERE log_ret IS NOT NULL
                and rv30 IS NOT NULL
            GROUP BY date
            HAVING COUNT(DISTINCT ticker) = 5
        )
        SELECT
            date,
            ROW_NUMBER() OVER (ORDER BY date) - 1 AS day_idx
        FROM valid_dates;

    """)

    con.execute("""
        CREATE OR REPLACE VIEW splitter AS
            WITH valid_dates AS (
                SELECT date
                FROM features_sql
                WHERE log_ret IS NOT NULL
                    and rv30 IS NOT NULL
                GROUP BY date
                HAVING COUNT(DISTINCT ticker) = 5
                ),
            all_dates AS (
                SELECT
                    MIN(date) AS first_valid_date
                FROM valid_dates
            ),
            year_dates AS (
                SELECT
                    YEAR(date) AS year,
                    MIN(date) AS first_date,
                    MAX(date) AS last_date
                FROM valid_dates
                GROUP BY YEAR(date)
            )

            SELECT
                yd.year,
                ad.first_valid_date AS train_start,
                LAG(yd.last_date) OVER (ORDER BY yd.year) AS train_end,
                yd.first_date AS test_start,
                yd.last_date AS test_end
            FROM year_dates AS yd
            CROSS JOIN all_dates as ad
            ORDER BY yd.year;

    """)

    return None

if __name__ == "__main__":
    calendar(con)