# ADR 0004: GCS Bucket Module Configuration (Terraform)

## Context
Module 03 uses a GCS bucket as the RAW landing zone for Parquet files. A minimal bucket configuration is sufficient for this module’s current scope, but production-like environments typically require additional controls for:

- **Security** (how access is managed)
- **Cost management** (storage class + retention)
- **Governance** (labels for tracking and ownership)
- **Developer workflow** (safe teardown for sandbox environments)

Terraform module inputs are used so the bucket configuration remains reusable across modules and environments.

---

## Decision

### Implemented in this module (minimal, now)
The Terraform module will provision a GCS bucket with:
- `project_id`, `name`, `location`
- `uniform_bucket_level_access = true` (IAM-only access model)
- optional `force_destroy` (dev/sandbox convenience)

This keeps the module small and easy to maintain while still following a safe security default (UBLA).

### Not implemented yet (production options, later)
The following options are intentionally deferred and may be added later if needed:
- `storage_class`
- `versioning_enabled`
- `labels`
- `lifecycle_rules`

---

## Rationale (why minimal now)
- **Reduce cognitive load:** focus on the Module 03 learning goals (GCS → BigQuery) without overbuilding Terraform.
- **Still safe by default:** UBLA avoids per-object ACL complexity and common misconfigurations.
- **Room to grow:** the module can be extended later without changing the overall structure.

---

## Consequences
- The current module is shorter than a production-grade module.
- Some production concerns (tiering, retention, labeling, version history) are not automated yet and would require manual setup or a later enhancement.

---

## Note: `<<EOT ... EOT` (Heredoc)
Terraform supports heredoc syntax (`<<EOT ... EOT`) for multi-line strings (commonly for long descriptions or embedded examples).
`EOT` is only a delimiter name and can be any matching token (e.g., `EOF`, `TEXT`).
