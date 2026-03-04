-- fix_v_dangerous_delay_candidates.sql
-- Run in Supabase SQL Editor:
--   https://supabase.com/dashboard/project/fguvvhqvzifnsihhomcv/sql
--
-- Problem: v_dangerous_delay_candidates times out on 1.6M row external geoevent table
-- Fix:  add composite indexes to source tables + recreate the view with explicit LIMIT

-- ─── Step 1: Indexes on source tables ────────────────────────────────────────

-- Index on geo_events_externalgeoevent: (geo_event_id, date_created)
-- Speeds up the join + ORDER BY used in the view
CREATE INDEX IF NOT EXISTS idx_ext_geoevent_geo_event_created
    ON geo_events_externalgeoevent (geo_event_id, date_created DESC);

-- Index on geo_events_geoevent: (geo_event_id) for the join
CREATE INDEX IF NOT EXISTS idx_geoevent_geo_event_id
    ON geo_events_geoevent (geo_event_id);

-- Index on notification_type (used in WHERE filter for signal detection)
CREATE INDEX IF NOT EXISTS idx_geoevent_notification_type
    ON geo_events_geoevent (notification_type)
    WHERE notification_type IS NOT NULL;

-- ─── Step 2: Drop and recreate the view with LIMIT baked in ──────────────────
-- This avoids scanning all 1.6M rows when called without an explicit limit

DROP VIEW IF EXISTS v_dangerous_delay_candidates;

CREATE VIEW v_dangerous_delay_candidates AS
SELECT
    g.geo_event_id,
    g.name,
    g.geo_event_type,
    g.notification_type,
    e.external_source,
    e.date_created   AS first_signal_time
FROM geo_events_geoevent g
JOIN (
    -- First external signal per geo_event
    SELECT DISTINCT ON (geo_event_id)
        geo_event_id,
        external_source,
        date_created
    FROM geo_events_externalgeoevent
    ORDER BY geo_event_id, date_created ASC
) e ON e.geo_event_id = g.geo_event_id
-- "dangerous delay candidate" = has external signal but NO evacuation action
WHERE g.geo_event_id NOT IN (
    SELECT DISTINCT geo_event_id
    FROM evac_zone_status_geo_event_map
    WHERE geo_event_id IS NOT NULL
)
-- Newest signals first (most actionable)
ORDER BY e.date_created DESC
LIMIT 2000;

-- ─── Step 3: Verify ──────────────────────────────────────────────────────────
SELECT COUNT(*) AS candidate_count FROM v_dangerous_delay_candidates;

-- Expected: up to 2000 rows (view is now pre-limited)
-- Query time should be < 2s with the indexes above

-- ─── Notes ───────────────────────────────────────────────────────────────────
-- The application code in signal_gap_analysis_page.py already adds .limit(500)
-- on top of this view, so the 2000-row LIMIT here is a safety cap at the DB layer.
--
-- If the evac_zone_status_geo_event_map table is large, also add:
-- CREATE INDEX IF NOT EXISTS idx_evac_map_geo_event_id
--     ON evac_zone_status_geo_event_map (geo_event_id);
