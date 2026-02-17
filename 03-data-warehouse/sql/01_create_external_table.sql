-- 01_create_external_table.sql
-- ------------------------------------------------------------
-- Create an external table partitioned via Hive (GCS Parquet).
-- Data source: {{GCS_TRIP_ROOT}}/year=YYYY/month=MM/*.parquet
-- ------------------------------------------------------------

CREATE OR REPLACE EXTERNAL TABLE
  `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_EXT}}`
WITH PARTITION COLUMNS (
  year  INT64,
  month INT64
)
OPTIONS (
  format = 'PARQUET',
  uris = ['{{GCS_TRIP_GLOB}}'],
  hive_partition_uri_prefix = '{{GCS_TRIP_HIVE_PREFIX}}',
  require_hive_partition_filter = FALSE
);
