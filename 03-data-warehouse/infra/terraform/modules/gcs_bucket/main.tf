# terraform/modules/gcs_bucket/main.tf

resource "google_storage_bucket" "this" {
  project       = var.project_id
  name          = var.name
  location      = var.location
  force_destroy = var.force_destroy

  uniform_bucket_level_access = var.uniform_bucket_level_access
}
