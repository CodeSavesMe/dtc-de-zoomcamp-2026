Architecture Decision Record.
# ADR 0001: Infrastructure as Code (IaC) via Terraform

## Context
Module 03 uses Google Cloud Storage (GCS) to store raw Parquet files and BigQuery as the data warehouse. Before running any ingestion scripts or SQL steps, we need consistent infrastructure that can be recreated reliably.

## Decision
Use Terraform to provision:
- **1 GCS bucket** as the raw data landing zone
- **2 BigQuery datasets**
  - `staging`: external tables and intermediate/materialized baseline tables
  - `final`: optimized, analytics-ready tables
- **BigQuery location**: `US` (multi-region)

## Rationale
- **Reproducibility:** infrastructure can be recreated from code without manual Console steps
- **Traceability:** infra changes are tracked in Git history
- **Environment consistency:** same configuration across machines/environments
- **Separation of concerns:** Terraform for infra; SQL/Python for data operations

## Consequences
- Requires Terraform and GCP credentials
- Adds a small upfront setup cost (effort), but improves repeatability and portfolio quality
