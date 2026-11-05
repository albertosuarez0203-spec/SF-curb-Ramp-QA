# San Francisco Curb Ramp Inventory: Data Quality Audit

A quality audit of San Francisco's public curb ramp dataset, 50,098 records loaded into
a local PostgreSQL/PostGIS database and checked for structural, spatial, and encoding
problems that would affect anyone using the data for accessibility analysis.

The short version: the dataset is usable, but three of its properties will produce wrong
answers if you take the columns at face value. The worst of them survives the null checks
and range checks most people write.

## Data

San Francisco curb ramp inventory, downloaded 2026-10-28. 50,098 rows, 35 columns.
Each record is one curb ramp location, keyed by `locID` and tied to a street intersection
by `CNN`, San Francisco's street centerline network number.

The CSV is not committed to this repository. Download it from SF's open data portal and
put it beside the scripts.

## Stack

Python (pandas, GeoPandas, SQLAlchemy, psycopg2, GeoAlchemy2) for loading,
PostgreSQL 18 with PostGIS 3.6 for the audit.

## Running it

```
pip install pandas geopandas sqlalchemy psycopg2-binary geoalchemy2
createdb gis_projects
psql -d gis_projects -c "CREATE EXTENSION postgis;"

set PGPASSWORD=your_password          # Windows
export PGPASSWORD=your_password       # macOS / Linux

python load_data.py
python qa_checks.py
```

`load_data.py` reads the CSV, builds point geometry from the latitude and longitude
columns, and writes the table to PostGIS. `qa_checks.py` runs the eight checks below
and prints the results.

## Findings

### 1. Four records have no coordinates

Four rows have null latitude and longitude. All four are real ramps (`crExist = 1`) in
good condition (`conditionScore = 100`), so they are not junk rows. They are dropped
during the spatial load because a point cannot be built without coordinates, which means
the PostGIS table holds 50,094 of the 50,098 records and any map built from it silently
undercounts by four real assets.

### 2. Point geometry identifies the intersection, not the ramp

50,094 records resolve to 7,552 distinct coordinate pairs. 42,542 records share their
exact coordinate with at least one other record.

This is the single most consequential property of the dataset and it is not stated in
the column names.

### 3. The collapse is exactly one point per intersection

Not a single `CNN` maps to more than one distinct point. 7,552 distinct CNNs, 7,552
distinct points, averaging 6.63 ramps per intersection.

This rules out the obvious alternative explanation, that the duplication is GPS rounding
or sloppy capture. The geometry is deliberate: every ramp at an intersection is stamped
with that intersection's coordinate. Any per ramp spatial analysis, nearest neighbor,
distance to a transit stop, or clustering, is operating on intersection centroids and
will treat four corners of a crossing as the same place.

### 4. 2,005 existing ramps have no detectable surface value

`detectableSurf` is null on 2,005 records where `crExist = 1`. The truncated dome surface
is a core ADA compliance attribute, so these are ramps whose compliance cannot be
determined from the data. That is 5.6% of all existing ramps.

### 5. Three locIDs appear twice

`locID` reads as a primary key and is not one. `21988000-SE-Left`, `27041000-SE-Center`,
and `22397000-W-Left` each appear on two records. Small in absolute terms, but enough to
break any join or upsert written on the assumption that locID is unique.

### 6. conditionScore uses three different encodings for "no ramp here"

| crExist | negative (-1, -2) | zero | scored 1-100 | total |
|---------|------------------|------|--------------|-------|
| 0 (no ramp) | 8,647 | 5,765 | 0 | 14,412 |
| 1 (ramp exists) | 0 | 0 | 35,682 | 35,682 |

Where no ramp exists, the score is `-1`, `-2`, or `0`. Where a ramp exists, the score is
always between 1 and 100. The encoding is perfectly consistent with `crExist`, which is
what makes it diagnosable, but there is no documentation saying so.

### 7. The zero sentinel defeats the obvious validation

`-1` and `-2` are visibly not scores and anyone will exclude them. `0` is inside the
score's own range. It is not null, it is not negative, it has the right data type, and it
passes every check short of knowing what it means.

### 8. The cost of missing it is about 14%

| filter | n | mean condition |
|--------|---|----------------|
| `crExist = 1` (correct) | 35,682 | 94.00 |
| `conditionScore >= 0` (plausible, wrong) | 41,447 | 80.93 |
| no filter | 50,094 | 66.65 |

Dropping the negative sentinels and keeping everything else, which is the natural thing to
do, understates the average condition of San Francisco's curb ramps by 13.07 points. The
right filter is on `crExist`, not on the score.

## Caveats

The CSV is a point-in-time download from 2026-10-28 and the city updates the inventory,
so the counts above are reproducible against that extract rather than against live data.
The `crExist` interpretation is inferred from the encoding pattern in finding 6 rather than
from a published data dictionary.
