-- ------------------------------------------------------------
-- 02_create_base_table.sql
-- Materialize external -> native BigQuery table (non-partitioned)
-- Used for HW Q2/Q4/Q6 "non-partitioned/materialized table" comparison.
-- ------------------------------------------------------------

CREATE OR REPLACE TABLE
  `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_BASE}}` AS
SELECT
  *
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_EXT}}`
WHERE year = {{TAXI_YEAR}}
  AND month BETWEEN 1 AND 6;
