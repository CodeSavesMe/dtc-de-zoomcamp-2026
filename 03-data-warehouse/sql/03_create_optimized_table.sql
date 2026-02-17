-- 03_create_optimized_table.sql
-- ------------------------------------------------------------
-- Promote staging data to the final production table.
-- Maintains partitioning and clustering for optimized queries.
-- ------------------------------------------------------------

CREATE OR REPLACE TABLE
  `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}.{{BQ_TABLE_FINAL}}`
PARTITION BY DATE({{TAXI_PICKUP_TS_COL}})
{% if TAXI_CLUSTER_COLS %}
CLUSTER BY {{TAXI_CLUSTER_COLS}}
{% endif %}
AS
SELECT
  *
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_BASE}}`;
