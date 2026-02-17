-- 04_dataset_sanity.sql
-- Focus: Metadata validation and cost-efficient data checks.
-- ------------------------------------------------------------

-- A & B) List tables and types in Staging and Final datasets (Metadata-only)
SELECT table_schema, table_name, table_type
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}`.INFORMATION_SCHEMA.TABLES
ORDER BY table_name;

SELECT table_schema, table_name, table_type
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}`.INFORMATION_SCHEMA.TABLES
ORDER BY table_name;

-- C & D) Verify table configurations and options (Metadata-only)
SELECT table_name, option_name, option_value
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}`.INFORMATION_SCHEMA.TABLE_OPTIONS
WHERE table_name IN ('{{BQ_TABLE_EXT}}', '{{BQ_TABLE_BASE}}')
ORDER BY table_name, option_name;

SELECT table_name, option_name, option_value
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}`.INFORMATION_SCHEMA.TABLE_OPTIONS
WHERE table_name = '{{BQ_TABLE_FINAL}}'
ORDER BY table_name, option_name;

-- E & F) Audit column names and data types (Metadata-only)
SELECT table_name, column_name, data_type
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}`.INFORMATION_SCHEMA.COLUMNS
WHERE table_name IN ('{{BQ_TABLE_EXT}}', '{{BQ_TABLE_BASE}}')
ORDER BY table_name, ordinal_position;

SELECT table_name, column_name, data_type
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}`.INFORMATION_SCHEMA.COLUMNS
WHERE table_name = '{{BQ_TABLE_FINAL}}'
ORDER BY table_name, ordinal_position;

-- G) Quick data samples (Minimal scan via partition filtering)
-- G1) Sample EXT: Filtered to a single Hive partition
SELECT
{{TAXI_PICKUP_TS_COL}} AS pickup_ts,
year,
month
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_EXT}}`
WHERE year = CAST('{{TAXI_YEAR}}' AS INT64)
AND month = 1
LIMIT 10;

-- G2) Sample BASE: Scans exactly one day
SELECT
{{TAXI_PICKUP_TS_COL}} AS pickup_ts
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_BASE}}`
WHERE DATE({{TAXI_PICKUP_TS_COL}}) = DATE('{{TAXI_YEAR}}-01-01')
LIMIT 10;

-- G3) Sample FINAL: Scans exactly one day
SELECT
{{TAXI_PICKUP_TS_COL}} AS pickup_ts
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}.{{BQ_TABLE_FINAL}}`
WHERE DATE({{TAXI_PICKUP_TS_COL}}) = DATE('{{TAXI_YEAR}}-01-01')
LIMIT 10;

-- H) Check Hive partition coverage (Distinct year/month)
SELECT DISTINCT year, month
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_EXT}}`
WHERE year = CAST('{{TAXI_YEAR}}' AS INT64)
ORDER BY 1,2;

-- I) Inspect physical partition metadata (Row counts and storage)
SELECT partition_id, total_rows, total_logical_bytes
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}`.INFORMATION_SCHEMA.PARTITIONS
WHERE table_name = '{{BQ_TABLE_FINAL}}'
ORDER BY partition_id
LIMIT 30;

-- J) Test Partition Pruning (Ensures 1-day scan efficiency)
SELECT COUNT(1) AS c
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}.{{BQ_TABLE_FINAL}}`
WHERE {{TAXI_PICKUP_TS_COL}} >= TIMESTAMP('{{TAXI_YEAR}}-03-01')
AND {{TAXI_PICKUP_TS_COL}} <  TIMESTAMP('{{TAXI_YEAR}}-03-02');

-- K) Rowcount Reconciliation: Cross-check EXT vs BASE vs FINAL
-- Validates data consistency for a specific month across all layers.
WITH params AS (
SELECT
CAST('{{TAXI_YEAR}}' AS INT64) AS y,
1 AS m
),

range_filter AS (
SELECT
DATE(y, m, 1) AS start_date,
DATE(y, m, 1) + INTERVAL 1 MONTH AS end_date,
TIMESTAMP(DATE(y, m, 1)) AS start_ts,
TIMESTAMP(DATE(y, m, 1) + INTERVAL 1 MONTH) AS end_ts
FROM params
),

cnt_ext AS (
SELECT COUNT(1) AS row_count
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_EXT}}`
WHERE year = (SELECT y FROM params)
AND month = (SELECT m FROM params)
),

cnt_base AS (
SELECT COUNT(1) AS row_count
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}.{{BQ_TABLE_BASE}}`
-- Guaranteed pruning via DATE(col) filter
WHERE DATE({{TAXI_PICKUP_TS_COL}}) >= (SELECT start_date FROM range_filter)
AND DATE({{TAXI_PICKUP_TS_COL}}) <  (SELECT end_date   FROM range_filter)
),

cnt_final AS (
SELECT COUNT(1) AS row_count
FROM `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}.{{BQ_TABLE_FINAL}}`
WHERE DATE({{TAXI_PICKUP_TS_COL}}) >= (SELECT start_date FROM range_filter)
AND DATE({{TAXI_PICKUP_TS_COL}}) <  (SELECT end_date   FROM range_filter)
)

SELECT
FORMAT('%d-%02d', (SELECT y FROM params), (SELECT m FROM params)) AS period_check,
(SELECT row_count FROM cnt_ext)   AS rows_ext_hive,
(SELECT row_count FROM cnt_base)  AS rows_base_native,
(SELECT row_count FROM cnt_final) AS rows_final_native,

(SELECT row_count FROM cnt_base) - (SELECT row_count FROM cnt_final) AS diff_base_final,
(SELECT row_count FROM cnt_ext)  - (SELECT row_count FROM cnt_base)  AS diff_ext_base,

(SELECT row_count FROM cnt_base) = (SELECT row_count FROM cnt_final) AS is_base_final_match,
(SELECT row_count FROM cnt_ext)  = (SELECT row_count FROM cnt_base)  AS is_ext_base_match
;