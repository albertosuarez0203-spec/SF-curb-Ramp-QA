"""
Load the San Francisco curb ramp inventory CSV into PostGIS.

Reads the CSV, reports records that cannot be given a geometry, builds point
geometry from the latitude and longitude columns, and writes the table.

Usage:
    set PGPASSWORD=your_password        # Windows
    export PGPASSWORD=your_password     # macOS / Linux
    python load_data.py
"""

import os
import sys

import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine

CSV = os.environ.get("CURB_RAMP_CSV", "Curb_Ramps_20261028.csv")
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


def main():
    if not os.path.exists(CSV):
        sys.exit(
            f"Cannot find {CSV}. Put the CSV beside this script, or set "
            f"CURB_RAMP_CSV to its path."
        )

    df = pd.read_csv(CSV, low_memory=False)
    print(f"Read {len(df)} rows from {CSV}")

    # Records with no coordinates cannot be given a geometry, so they are
    # dropped here. They are not junk: report them so the loss is visible
    # rather than silent.
    missing = df[df["Latitude"].isna() | df["Longitude"].isna()]
    print(f"Records with no coordinates: {len(missing)}")
    if not missing.empty:
        print(missing[["locID", "CNN", "crExist", "conditionScore"]].to_string(index=False))

    located = df.dropna(subset=["Latitude", "Longitude"]).copy()

    gdf = gpd.GeoDataFrame(
        located,
        geometry=gpd.points_from_xy(located.Longitude, located.Latitude),
        crs="EPSG:4326",
    )

    engine = get_engine()
    gdf.to_postgis(TABLE, engine, if_exists="replace", index=False)
    print(f"Wrote {len(gdf)} records to {TABLE}")


if __name__ == "__main__":
    main()
