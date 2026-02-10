# terraform/modules/bigquery/main.tf

resource "google_bigquery_dataset" "this" {
  project    = var.project_id
  dataset_id = var.dataset_id
  location   = var.location
}
