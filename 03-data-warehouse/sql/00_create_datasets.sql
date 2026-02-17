-- sql/00_create_datasets.sql
-- ------------------------------------------------------------
-- Initialize BigQuery datasets for staging and final layers.
-- Configures the dataset location based on {{BQ_LOCATION}}.
-- ------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS `{{GCP_PROJECT_ID}}.{{BQ_DATASET_STAGING}}`
OPTIONS (location = "{{BQ_LOCATION}}");

CREATE SCHEMA IF NOT EXISTS `{{GCP_PROJECT_ID}}.{{BQ_DATASET_FINAL}}`
OPTIONS (location = "{{BQ_LOCATION}}");
