-- dedup_fire_events.sql
-- Run in Supabase SQL Editor:
--   https://supabase.com/dashboard/project/fguvvhqvzifnsihhomcv/sql
--
-- Problem: fire_events table has 124,696 rows; should be 62,696 (one row per
-- geo_event_id, matching geo_events_geoevent.csv).
--
-- Strategy: keep the row with the lowest `id` (first inserted) for each
-- geo_event_id; delete everything else.
-- Safe — wrapped in a transaction so you can ROLLBACK if the count looks wrong.

BEGIN;

-- 1. Preview: confirm how many rows will be deleted
SELECT
    COUNT(*)                                            AS total_rows,
    COUNT(DISTINCT geo_event_id)                        AS unique_geo_event_ids,
    COUNT(*) - COUNT(DISTINCT geo_event_id)             AS rows_to_delete
FROM fire_events;

-- 2. Delete duplicates (keep first-inserted row per geo_event_id)
DELETE FROM fire_events
WHERE id NOT IN (
    SELECT MIN(id)
    FROM fire_events
    GROUP BY geo_event_id
);

-- 3. Confirm final count — expect 62,696
SELECT COUNT(*) AS rows_after_dedup FROM fire_events;

-- 4. Commit if the count looks right, otherwise ROLLBACK
COMMIT;
-- ROLLBACK;  -- uncomment to undo if something looks wrong
