# terraform/modules/bigquery/output.tf

output "dataset_id" {
  description = "BigQuery dataset ID."
  value       = google_bigquery_dataset.this.dataset_id
}

output "location" {
  description = "BigQuery dataset location."
  value       = google_bigquery_dataset.this.location
}
