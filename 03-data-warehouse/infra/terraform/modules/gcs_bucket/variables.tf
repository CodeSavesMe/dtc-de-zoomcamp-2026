# terraform/modules/gcs_bucket/variables.tf

variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "name" {
  description = "Globally-unique GCS bucket name."
  type        = string
}

variable "location" {
  description = "Bucket location (e.g. US)."
  type        = string
  default     = "US"
}

variable "force_destroy" {
  description = "If true, deleting the bucket will delete all objects (dev/sandbox only)."
  type        = bool
  default     = false
}

variable "uniform_bucket_level_access" {
  description = "Enable uniform bucket-level access (IAM-only; disables per-object ACLs)."
  type        = bool
  default     = true
}
