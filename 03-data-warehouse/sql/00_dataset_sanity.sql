-- ------------------------------------------------------------
-- 00_dataset_sanity.sql (NO region-us)
-- Use dataset-level INFORMATION_SCHEMA to avoid region-level permission issues.
-- ------------------------------------------------------------

-- A) List tables + types in staging
SELECT
  table_schema,
  table_name,
  table_type
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}`.INFORMATION_SCHEMA.TABLES
ORDER BY table_name;

-- B) List tables + types in final
SELECT
  table_schema,
  table_name,
  table_type
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}`.INFORMATION_SCHEMA.TABLES
ORDER BY table_name;

-- C) Table options (staging)
SELECT
  table_name,
  option_name,
  option_value
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}`.INFORMATION_SCHEMA.TABLE_OPTIONS
WHERE table_name IN ('{{BQ_TABLE_EXT}}', '{{BQ_TABLE_BASE}}')
ORDER BY table_name, option_name;

-- D) Table options (final)
SELECT
  table_name,
  option_name,
  option_value
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}`.INFORMATION_SCHEMA.TABLE_OPTIONS
WHERE table_name IN ('{{BQ_TABLE_FINAL}}')
ORDER BY table_name, option_name;

-- E) Columns check (staging)
SELECT
  table_name,
  column_name,
  data_type
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}`.INFORMATION_SCHEMA.COLUMNS
WHERE table_name IN ('{{BQ_TABLE_EXT}}', '{{BQ_TABLE_BASE}}')
ORDER BY table_name, ordinal_position;

-- F) Columns check (final)
SELECT
  table_name,
  column_name,
  data_type
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}`.INFORMATION_SCHEMA.COLUMNS
WHERE table_name IN ('{{BQ_TABLE_FINAL}}')
ORDER BY table_name, ordinal_position;

-- G) Quick peek
SELECT * FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_EXT}}` LIMIT 10;
SELECT * FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_BASE}}` LIMIT 10;
SELECT * FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}.{{BQ_TABLE_FINAL}}` LIMIT 10;

-- H) Partition coverage (external hive partitions)
SELECT year, month, COUNT(*) AS c
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_EXT}}`
GROUP BY 1,2
ORDER BY 1,2;

-- I) Final table partitions exist (column-based partitioning)
-- For partitioned tables, BigQuery exposes partitions via INFORMATION_SCHEMA.PARTITIONS.
SELECT
  partition_id,
  total_rows,
  total_logical_bytes
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}`.INFORMATION_SCHEMA.PARTITIONS
WHERE table_name = '{{BQ_TABLE_FINAL}}'
ORDER BY partition_id
LIMIT 30;

-- J) Quick partition-pruning check (should scan much less when filtered)
SELECT COUNT(*) AS c
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}.{{BQ_TABLE_FINAL}}`
WHERE tpep_dropoff_datetime >= '2024-03-01'
  AND tpep_dropoff_datetime <  '2024-03-02';

