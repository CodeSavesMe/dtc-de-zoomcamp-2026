# Resource definition for the Storage Bucket

resource "google_storage_bucket" "demo_bucket" {
  name          = var.bucket_name
  location      = var.location

  # Allow Terraform to delete the bucket even if it contains files
  # Recommended for learning/homework environments

  force_destroy = true

  storage_class               = "STANDARD"
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  # Lifecycle rule: Automatically delete objects older than 30 days
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 30
    }
  }
}