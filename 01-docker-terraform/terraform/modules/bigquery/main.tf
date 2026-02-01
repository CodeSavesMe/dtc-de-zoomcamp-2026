# Resource definition for the BigQuery Dataset
resource "google_bigquery_dataset" "demo_dataset" {
  dataset_id                 = var.dataset_id
  project                    = var.project_id
  location                   = var.location

  # Allow Terraform to destroy the dataset and all its tables
  delete_contents_on_destroy = true
}