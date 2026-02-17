-- 02_create_base_table.sql
-- ------------------------------------------------------------
-- Create a native BigQuery table from an external source.
-- Features: Partitioning, clustering, and schema drift handling.
-- Filtered by: {{TAXI_YEAR}}
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE
  `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_BASE}}`
PARTITION BY DATE({{TAXI_PICKUP_TS_COL}})
{% if TAXI_CLUSTER_COLS %}
CLUSTER BY {{TAXI_CLUSTER_COLS}}
{% endif %}
AS
SELECT
{% if TAXI_EXCEPT_COLS %}
  * EXCEPT({{TAXI_EXCEPT_COLS}})
{% else %}
  *
{% endif %}
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_EXT}}`
WHERE year = CAST('{{TAXI_YEAR}}' AS INT64);
