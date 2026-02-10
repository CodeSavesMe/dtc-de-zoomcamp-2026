# ADR 0003: Partitioning and Clustering Strategy (BigQuery Final Tables)

## Context

BigQuery is a columnar (OLAP) analytics warehouse where query cost and performance are strongly influenced by the amount of data scanned. In OLAP, the pain often comes from scanning a **Monster Table** (a very large fact table). If a Monster Table is left unoptimized, many queries end up doing unnecessary full scans and become expensive.

For the NYC Yellow Taxi dataset, common analytical queries frequently:
- Filter by a **date/time range** (e.g., `tpep_dropoff_datetime`)
- Aggregate, group, or sort by **VendorID**

To support efficient analytics and reduce scanned bytes, the final serving table should be optimized according to these access patterns.

---

## Decision

Create the **Final (Gold) table** with:

1) **Partitioning** by `DATE(tpep_dropoff_datetime)`
2) **Clustering** by `VendorID`

This optimization is applied only to the `final` layer table(s), while the `staging` base table remains unoptimized to serve as a stable baseline.

---

## Rationale

* **Partitioning reduces scan size:** Date-based partitioning allows BigQuery to prune partitions and scan only relevant date ranges instead of the full dataset.
* **Clustering improves locality:** Clustering by `VendorID` helps BigQuery organize data so queries filtering/grouping by VendorID can scan fewer blocks and run more efficiently.
* **Aligns storage with query patterns:** Partition + clustering choices are driven by expected query behavior, not by schema alone.

---

## Operational Notes

* **Partition filters matter:** Partitioning provides the most benefit when queries include filters on the partition column (e.g., `WHERE DATE(tpep_dropoff_datetime) BETWEEN ...`).
* **Columnar scans:** Selecting fewer columns typically scans fewer bytes; `SELECT *` should be avoided for production workloads.
* **Revisit if query patterns change:** Partition and clustering strategies should be reviewed if the primary filters/grouping dimensions change over time.
