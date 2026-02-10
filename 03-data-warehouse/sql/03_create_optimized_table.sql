-- ------------------------------------------------------------
-- 03_create_optimized_table.sql
-- Optimized table (partition + cluster):
-- Partition by DATE(tpep_dropoff_datetime), cluster by VendorID
-- ------------------------------------------------------------

CREATE OR REPLACE TABLE
  `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}.{{BQ_TABLE_FINAL}}`
PARTITION BY DATE(tpep_dropoff_datetime)
CLUSTER BY VendorID AS
SELECT
  *
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_BASE}}`;
