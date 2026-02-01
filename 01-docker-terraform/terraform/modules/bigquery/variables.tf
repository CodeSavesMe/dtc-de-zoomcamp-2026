# Identifier for the BigQuery dataset
variable "dataset_id" {
  description = "Dataset ID"
  type        = string
}

# Google Cloud Project ID where resources will be created
variable "project_id" {
  description = "Project ID"
  type        = string
}

# Regional location for the dataset (e.g., asia-southeast1)
variable "location" {
  description = "Location"
  type        = string
}