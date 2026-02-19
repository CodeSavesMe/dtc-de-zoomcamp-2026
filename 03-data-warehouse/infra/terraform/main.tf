# infra/terraform/main.tf

# Root module: wires reusable modules to provision:
# - 1 GCS bucket for RAW files
# - 2 BigQuery datasets: staging and final

module "raw_bucket" {
  # Local reusable module for GCS bucket
  source = "./modules/gcs_bucket"

  # Where to create the bucket
  project_id = var.project_id

  # Globally unique bucket name (must be unique across all GCS)
  name = var.bucket_name

  # Bucket location (multi-region recommended for this project, e.g. US)
  location = var.location

  # Dev/sandbox convenience:
  # - true  -> terraform destroy can delete non-empty buckets (dangerous for prod)
  # - false -> destroy will fail if bucket still has objects
  force_destroy = var.force_destroy

  # Security model:
  # - true  -> IAM-only at bucket level, disables per-object ACLs (recommended default)
  # - false -> legacy ACL model (avoid)
  uniform_bucket_level_access = var.uniform_bucket_level_access
}

module "bq_dataset_staging" {
  # Local reusable module for BigQuery dataset
  source = "./modules/bigquery"

  # Where to create the dataset
  project_id = var.project_id

  # Dataset ID (layer): staging
  dataset_id = var.dataset_staging_id

  # Dataset location should match the chosen multi-region (e.g. US)
  location = var.location
}

module "bq_dataset_final" {
  # Local reusable module for BigQuery dataset
  source = "./modules/bigquery"

  project_id = var.project_id
  dataset_id = var.dataset_final_id
  location   = var.location
}
