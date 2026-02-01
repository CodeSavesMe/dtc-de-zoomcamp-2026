output "dataset_id" {
  description = "The unique ID of the created BigQuery dataset"
  value       = google_bigquery_dataset.demo_dataset.dataset_id
}