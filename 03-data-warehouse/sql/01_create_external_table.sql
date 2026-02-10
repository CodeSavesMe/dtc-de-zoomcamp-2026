-- ------------------------------------------------------------
-- 01_create_external_table.sql
-- Hive-partitioned external table over GCS Parquet:
--   gs://{{GCS_BUCKET_NAME}}/{{GCS_RAW_PREFIX}}/{{TAXI_COLOR}}/year=YYYY/month=MM/*.parquet
-- Uses single wildcard in uris + hive_partition_uri_prefix.
-- ------------------------------------------------------------

CREATE OR REPLACE EXTERNAL TABLE
  `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_EXT}}`
WITH PARTITION COLUMNS (
  year  INT64,
  month INT64
)
OPTIONS (
  format = 'PARQUET',
  uris = ['gs://{{GCS_BUCKET_NAME}}/{{GCS_RAW_PREFIX}}/{{TAXI_COLOR}}/*'],
  hive_partition_uri_prefix = 'gs://{{GCS_BUCKET_NAME}}/{{GCS_RAW_PREFIX}}/{{TAXI_COLOR}}/',
  require_hive_partition_filter = FALSE
);
