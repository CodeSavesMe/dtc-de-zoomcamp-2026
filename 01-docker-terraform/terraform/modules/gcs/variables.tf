# Unique name for the GCS bucket
variable "bucket_name" {
  description = "The name of the GCS bucket"
  type        = string
}

# Regional location for the GCS bucket (e.g., ASIA-SOUTHEAST1)
variable "location" {
  description = "The geographic location of the bucket"
  type        = string
}