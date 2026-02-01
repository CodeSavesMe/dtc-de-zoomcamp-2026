# Terraform configuration block to set specific versions

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

# Google Cloud provider configuration to authenticate and set defaults
provider "google" {
  project = var.project_id
  region  = var.region
}