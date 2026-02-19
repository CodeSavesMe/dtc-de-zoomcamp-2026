# terraform/modules/bigquery/variables.tf

variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "dataset_id" {
  description = "BigQuery dataset ID (e.g. staging, final)."
  type        = string
}

variable "location" {
  description = "BigQuery dataset location (e.g. US)."
  type        = string
  default     = "US"
}
