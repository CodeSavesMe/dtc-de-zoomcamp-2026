# ADR 0005: Multi-statement SQL support in BigQuerySqlRunner

- Status: Accepted
- Date: 2026-02-10
- Scope: Module 03 (Data Warehouse)

## Context

Some SQL files in this module contain multiple statements (for example `00_dataset_sanity.sql`, check on sql/*).

The original runner executed one BigQuery job per file and assumed a single statement. When a file contained more than one statement separated by `;`, BigQuery returned syntax errors (for example “Expected end of input”).

Splitting these files manually increases maintenance cost and makes the SQL harder to review.

## Decision

Update `BigQuerySqlRunner` to execute multi-statement SQL files by:

- Rendering templates first (`render_sql_template`)
- Splitting the rendered SQL into statements by `;`, without splitting inside single/double-quoted strings
- Skipping empty or comment-only statements (`-- ...`)
- Executing statements sequentially
- Logging each statement as `path/to/file.sql#NN`
- Keeping `stop_on_error=True` as the default behavior

## Alternatives

1. Require one statement per file  
   Rejected because it forces manual splitting and increases file noise.

2. Use a full SQL parser  
   Rejected because it adds complexity and dependencies beyond this project’s needs.

3. Rewrite SQL as BigQuery scripting blocks  
   Rejected because it changes how SQL files are authored and is not necessary here.

## Consequences

- Multi-statement SQL files can be run directly with the existing CLI.
- Failures are easier to locate due to statement-level logging.
- The splitter is not a complete SQL parser; it is designed for the SQL patterns used in this module.
- If a later statement fails, earlier statements may have already executed. This is mitigated by using idempotent statements like `CREATE OR REPLACE` and failing fast by default.

## Implementation

- File: `src/dw03/pipelines/bq_run_sql.py`
- Added: `split_sql_statements(sql: str) -> list[str]`
- Execution behavior:
  - Dry-run: sum `estimated_bytes` across statements
  - Execute: run each statement and log `job_id`
