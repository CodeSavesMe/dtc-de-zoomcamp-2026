# The ID of the Google Cloud project where resources will be created

variable "project_id" {
  description = "Your unique Google Cloud Project ID"
  type        = string
}

# The default region for all Google Cloud resources
variable "region" {
  description = "Region for GCP resources (e.g., us-central1)"
  type        = string
  default     = "us-central1"
}

# The globally unique name for the Cloud Storage bucket
variable "gcs_bucket_name" {
  description = "Unique name for the GCS bucket"
  type        = string
}

# The ID for the BigQuery dataset
variable "bq_dataset_name" {
  description = "BigQuery Dataset ID"
  type        = string
  default     = "trips_data_all"
}