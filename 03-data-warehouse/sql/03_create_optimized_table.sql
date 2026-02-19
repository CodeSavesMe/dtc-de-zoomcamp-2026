-- 03_create_optimized_table.sql
-- ------------------------------------------------------------
-- Promote staging data to the final production table.
-- Appends data idempotently: creates table if missing,
-- clears existing year data to prevent duplicates, then inserts.
-- Maintains partitioning and clustering for optimized queries.
-- ------------------------------------------------------------

-- 1. Create table structure if it doesn't exist (Runs only on the first year)
CREATE TABLE IF NOT EXISTS
  `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}.{{BQ_TABLE_FINAL}}`
PARTITION BY DATE({{TAXI_PICKUP_TS_COL}})
{% if TAXI_CLUSTER_COLS %}
CLUSTER BY {{TAXI_CLUSTER_COLS}}
{% endif %}
AS
SELECT
  *
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_BASE}}`
LIMIT 0; -- Hanya copy skema, tanpa mengambil data

-- 2. Delete existing data for the currently processed year
-- (This ensures the script is idempotent / safe to re-run without duplicating data)
DELETE FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}.{{BQ_TABLE_FINAL}}`
WHERE year = CAST('{{TAXI_YEAR}}' AS INT64);

-- 3. Append the new data from staging to the final table
INSERT INTO `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}.{{BQ_TABLE_FINAL}}`
SELECT
  *
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_BASE}}`;