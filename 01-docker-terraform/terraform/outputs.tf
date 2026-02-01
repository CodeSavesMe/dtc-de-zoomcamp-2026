# Display the created Bucket Name in the terminal

output "bucket_name" {
  description = "The name of the created storage bucket"
  value       = module.gcs_bucket.bucket_name
}

# Display the created BigQuery Dataset ID in the terminal
output "dataset_id" {
  description = "The ID of the created BigQuery dataset"
  value       = module.bigquery_dataset.dataset_id
}