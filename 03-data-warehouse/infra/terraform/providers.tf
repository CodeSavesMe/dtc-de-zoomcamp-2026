# infra/terraform/providers.tf

# Terraform + provider configuration:
# - required Terraform version
# - required Google provider version
# - provider settings (project)

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0.0"
    }
  }
}

provider "google" {
  # Default project for all resources in this root module
  project = var.project_id
}
