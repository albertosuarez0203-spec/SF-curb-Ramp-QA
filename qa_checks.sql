-- ============================================================
-- San Francisco Curb Ramp Inventory: data quality audit
--
-- Run against the curb_ramps_sf table built by load_data.py.
-- In pgAdmin, highlight one query block and press F5. Running the
-- whole file at once only displays the last result set.
--
-- Findings are documented in README.md.
-- ============================================================


-- ------------------------------------------------------------
-- 1. Record count, split by whether a ramp exists
--    Expect: crExist=0 -> 14,412   crExist=1 -> 35,682
-- ------------------------------------------------------------
SELECT "crExist", COUNT(*) AS records
FROM curb_ramps_sf
GROUP BY "crExist"
ORDER BY "crExist";


-- ------------------------------------------------------------
-- 2. Coordinate collapse: how many records share a point
--    Expect: 50,094 records across 7,552 distinct points,
--            42,542 of them sharing a coordinate
-- ------------------------------------------------------------
SELECT COUNT(*)                            AS total_records,
       COUNT(DISTINCT geometry)            AS distinct_points,
       COUNT(*) - COUNT(DISTINCT geometry) AS records_sharing_a_point
FROM curb_ramps_sf;


-- ------------------------------------------------------------
-- 3. Does any intersection (CNN) map to more than one point?
--    Expect: 0. This is what proves the collapse in check 2 is
--    deliberate intersection-level geometry rather than GPS noise.
-- ------------------------------------------------------------
SELECT COUNT(*) AS cnns_with_multiple_points
FROM (
    SELECT "CNN"
    FROM curb_ramps_sf
    GROUP BY "CNN"
    HAVING COUNT(DISTINCT geometry) > 1
) t;


-- ------------------------------------------------------------
-- 4. Ramps per intersection
--    7,552 intersections, averaging 6.63 ramps each
-- ------------------------------------------------------------
SELECT ramps_at_intersection, COUNT(*) AS intersections
FROM (
    SELECT "CNN", COUNT(*) AS ramps_at_intersection
    FROM curb_ramps_sf
    GROUP BY "CNN"
) t
GROUP BY ramps_at_intersection
ORDER BY ramps_at_intersection;


-- ------------------------------------------------------------
-- 5. Existing ramps with no detectable surface value
--    Expect: 2,005. detectableSurf is a core ADA attribute, so
--    these are ramps whose compliance cannot be determined.
-- ------------------------------------------------------------
SELECT COUNT(*) AS existing_ramps_missing_detectable_surface
FROM curb_ramps_sf
WHERE "crExist" = 1
  AND "detectableSurf" IS NULL;


-- ------------------------------------------------------------
-- 6. locID duplicates
--    Expect 3: locID reads as a primary key and is not one.
-- ------------------------------------------------------------
SELECT "locID", COUNT(*) AS occurrences
FROM curb_ramps_sf
GROUP BY "locID"
HAVING COUNT(*) > 1
ORDER BY "locID";


-- ------------------------------------------------------------
-- 7. How conditionScore is encoded against crExist
--    Where no ramp exists the score is -1, -2, or 0.
--    Where a ramp exists it is always 1-100.
--
--    crExist=0 -> 8,647 negative | 5,765 zero |      0 scored
--    crExist=1 ->     0 negative |     0 zero | 35,682 scored
-- ------------------------------------------------------------
SELECT "crExist",
       COUNT(*) FILTER (WHERE "conditionScore" < 0) AS negative_sentinel,
       COUNT(*) FILTER (WHERE "conditionScore" = 0) AS zero_sentinel,
       COUNT(*) FILTER (WHERE "conditionScore" > 0) AS scored,
       COUNT(*)                                     AS total
FROM curb_ramps_sf
GROUP BY "crExist"
ORDER BY "crExist";


-- ------------------------------------------------------------
-- 8. What the zero sentinel costs you on an average
--    Dropping only the visibly invalid negatives still understates
--    mean ramp condition by 13.07 points.
--
--    correct 94.00 | negatives dropped 80.93 | no filter 66.65
-- ------------------------------------------------------------
SELECT ROUND(AVG("conditionScore") FILTER (WHERE "crExist" = 1), 2)
           AS correct_mean_existing_ramps_only,
       ROUND(AVG("conditionScore") FILTER (WHERE "conditionScore" >= 0), 2)
           AS mean_after_dropping_negatives_only,
       ROUND(AVG("conditionScore"), 2)
           AS mean_with_no_filter
FROM curb_ramps_sf;
