# Create GCS Bucket
module "gcs_bucket" {
  source      = "./modules/gcs"
  bucket_name = var.gcs_bucket_name
  location    = var.region
}

# Create BigQuery Dataset
module "bigquery_dataset" {
  source     = "./modules/bigquery"
  dataset_id = var.bq_dataset_name
  project_id = var.project_id
  location   = var.region
}