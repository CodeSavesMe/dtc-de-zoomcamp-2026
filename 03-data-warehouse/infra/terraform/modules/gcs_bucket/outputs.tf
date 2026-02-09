# terraform/modules/gcs_bucket/output.tf

output "name" {
  description = "Bucket name."
  value       = google_storage_bucket.this.name
}

output "url" {
  description = "Bucket URL."
  value       = google_storage_bucket.this.url
}

output "location" {
  description = "Bucket location."
  value       = google_storage_bucket.this.location
}
