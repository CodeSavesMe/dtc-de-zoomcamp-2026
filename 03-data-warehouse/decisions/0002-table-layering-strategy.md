# ADR 0002: Table Layering Strategy (External vs. Materialized)

## Context

Raw NYC taxi data is stored as Parquet files in Google Cloud Storage (GCS). BigQuery provides two primary methods to interact with this data:

* **External Table:** A direct reference to files in GCS (no data movement).
* **Materialized Table:** Native internal storage within BigQuery.

A structured table lifecycle is required to ensure data validation, repeatability, and high-performance analytics.

### Medallion Architecture Mapping

To keep the layering easy to reason about, this design aligns with **Medallion Architecture** principles:

* **Bronze:** Raw Parquet files in GCS (Source of Truth).
* **Silver:** BigQuery materialized baseline tables (Curated baseline & persistent).
* **Gold:** BigQuery final optimized tables (Analytics & BI ready).

---

## Decision

Adopt a **3-step table lifecycle** to transform data from raw storage to an optimized state:

### 1. External Table (Staging - Landing)

* **Mechanism:** References Parquet files directly in GCS.
* **Characteristics:** Stores only metadata (schema + file URIs) in BigQuery. Data is scanned on-demand.
* **Purpose:** Provides a fast, transparent landing layer for initial exploration and schema validation.

### 2. Materialized Base Table (Staging - Silver)

* **Mechanism:** Created from the External Table using `CTAS` (*Create Table As Select*).
* **Characteristics:** Data is physically stored in BigQuery native storage. Serves as a stable baseline without partitioning or clustering.
* **Purpose:** Ensures data persistence and query stability even if the source GCS objects are modified, moved, or deleted.

### 3. Final Table (Optimized - Gold)

* **Mechanism:** Derived from the Materialized Base Table.
* **Characteristics:** Implements **Partitioning** and **Clustering** optimized for analytical workloads.
* **Purpose:** Provides a high-performance, cost-effective layer for end-user consumption and BI dashboards.

---

## Rationale

* **Efficiency:** External tables enable a rapid landing zone without immediate data duplication.
* **Resilience:** Materialized tables provide a BigQuery-native baseline, reducing dependency on GCS object paths/availability for downstream queries.
* **Governance:** Clear separation between `staging` and `final` layers isolates responsibilities and minimizes risk during backfills or schema changes.

## Operational Notes

* **Query Costs:** Querying external tables still incurs BigQuery processing costs since data must be read and processed.
* **Data Integrity:** If referenced GCS objects are deleted or moved, external table queries fail. Materialized tables remain functional because the data is stored in BigQuery.
* **Performance:** The Gold layer (Final Table) should be used for production dashboards to minimize latency and scanned bytes.
