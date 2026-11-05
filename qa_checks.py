"""
Data quality audit of the San Francisco curb ramp inventory.

Runs the integrity checks documented in README.md against the curb_ramps_sf
table in PostGIS and prints the result of each one.

Run load_data.py first to build the table.

Usage:
    set PGPASSWORD=your_password        # Windows
    export PGPASSWORD=your_password     # macOS / Linux
    python qa_checks.py
"""

import os
import sys

import pandas as pd
from sqlalchemy import create_engine

TABLE = "curb_ramps_sf"


def get_engine():
    password = os.environ.get("PGPASSWORD")
    if not password:
        sys.exit(
            "PGPASSWORD is not set. Set it in your shell before running:\n"
            "    set PGPASSWORD=your_password        (Windows)\n"
            "    export PGPASSWORD=your_password     (macOS / Linux)"
        )
    user = os.environ.get("PGUSER", "postgres")
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    database = os.environ.get("PGDATABASE", "gis_projects")
    return create_engine(
        f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    )


CHECKS = [
    (
        "1. Record count, split by whether a ramp exists",
        """
        SELECT "crExist", COUNT(*) AS records
        FROM curb_ramps_sf
        GROUP BY "crExist"
        ORDER BY "crExist";
        """,
    ),
    (
        "2. Coordinate collapse: how many records share a point",
        """
        SELECT COUNT(*)                                  AS total_records,
               COUNT(DISTINCT geometry)                  AS distinct_points,
               COUNT(*) - COUNT(DISTINCT geometry)       AS records_sharing_a_point
        FROM curb_ramps_sf;
        """,
    ),
    (
        "3. Does any intersection (CNN) map to more than one point?",
        """
        SELECT COUNT(*) AS cnns_with_multiple_points
        FROM (
            SELECT "CNN"
            FROM curb_ramps_sf
            GROUP BY "CNN"
            HAVING COUNT(DISTINCT geometry) > 1
        ) t;
        """,
    ),
    (
        "4. Ramps per intersection",
        """
        SELECT ramps_at_intersection, COUNT(*) AS intersections
        FROM (
            SELECT "CNN", COUNT(*) AS ramps_at_intersection
            FROM curb_ramps_sf
            GROUP BY "CNN"
        ) t
        GROUP BY ramps_at_intersection
        ORDER BY ramps_at_intersection;
        """,
    ),
    (
        "5. Existing ramps with no detectable surface value",
        """
        SELECT COUNT(*) AS existing_ramps_missing_detectable_surface
        FROM curb_ramps_sf
        WHERE "crExist" = 1
          AND "detectableSurf" IS NULL;
        """,
    ),
    (
        "6. locID duplicates (locID looks like a key and is not one)",
        """
        SELECT "locID", COUNT(*) AS occurrences
        FROM curb_ramps_sf
        GROUP BY "locID"
        HAVING COUNT(*) > 1
        ORDER BY "locID";
        """,
    ),
    (
        "7. How conditionScore is encoded against crExist",
        """
        SELECT "crExist",
               COUNT(*) FILTER (WHERE "conditionScore" < 0) AS negative_sentinel,
               COUNT(*) FILTER (WHERE "conditionScore" = 0) AS zero_sentinel,
               COUNT(*) FILTER (WHERE "conditionScore" > 0) AS scored,
               COUNT(*)                                     AS total
        FROM curb_ramps_sf
        GROUP BY "crExist"
        ORDER BY "crExist";
        """,
    ),
    (
        "8. What the zero sentinel costs you on an average",
        """
        SELECT ROUND(AVG("conditionScore") FILTER (WHERE "crExist" = 1), 2)
                   AS correct_mean_existing_ramps_only,
               ROUND(AVG("conditionScore") FILTER (WHERE "conditionScore" >= 0), 2)
                   AS mean_after_dropping_negatives_only,
               ROUND(AVG("conditionScore"), 2)
                   AS mean_with_no_filter
        FROM curb_ramps_sf;
        """,
    ),
]


def main():
    engine = get_engine()
    pd.set_option("display.max_rows", 50)
    pd.set_option("display.width", 100)

    for title, sql in CHECKS:
        print()
        print(title)
        print("-" * len(title))
        result = pd.read_sql(sql, engine)
        if result.empty:
            print("(no rows)")
        else:
            print(result.to_string(index=False))

    print()


if __name__ == "__main__":
    main()
