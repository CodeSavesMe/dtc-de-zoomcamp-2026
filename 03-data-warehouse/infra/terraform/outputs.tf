# infra/terraform/outputs.tf
#
# Root module outputs:
# Useful values after `terraform apply` for scripts/README/debugging.

output "project_id" {
  description = "GCP project id used by this stack."
  value       = var.project_id
}

output "location" {
  description = "Location used for resources (bucket + BigQuery datasets)."
  value       = var.location
}

output "bucket_name" {
  description = "Created GCS bucket name."
  value       = module.raw_bucket.name
}

output "bucket_url" {
  description = "Created GCS bucket URL."
  value       = module.raw_bucket.url
}

output "bq_dataset_staging_id" {
  description = "BigQuery staging dataset ID."
  value       = module.bq_dataset_staging.dataset_id
}

output "bq_dataset_final_id" {
  description = "BigQuery final dataset ID."
  value       = module.bq_dataset_final.dataset_id
}
