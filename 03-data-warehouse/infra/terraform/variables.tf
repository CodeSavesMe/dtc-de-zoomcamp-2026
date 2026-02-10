# infra/terraform/variables.tf

variable "project_id" {
  description = "GCP project id."
  type        = string
}

variable "location" {
  description = "GCS + BigQuery location (for this project usually US multi-region)."
  type        = string
  default     = "US"
}

variable "bucket_name" {
  description = "Globally unique GCS bucket name."
  type        = string
}

variable "force_destroy" {
  description = "Delete bucket even if it contains objects (dev only)."
  type        = bool
  default     = false
}

variable "uniform_bucket_level_access" {
  description = "Enable UBLA (IAM-only access, disables per-object ACLs)."
  type        = bool
  default     = true
}

variable "dataset_staging_id" {
  description = "BigQuery staging dataset id."
  type        = string
  default     = "staging"
}

variable "dataset_final_id" {
  description = "BigQuery final dataset id."
  type        = string
  default     = "final"
}
