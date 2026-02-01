
<div align="center">

# Module 01 — Docker + Terraform  
## NYC TLC Taxi Data → Postgres (Ingestion CLI)

![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Terraform](https://img.shields.io/badge/terraform-623CE4?style=for-the-badge&logo=terraform&logoColor=white)
![ETL](https://img.shields.io/badge/etl_pipeline-4CAF50?style=for-the-badge)

</div>

CLI pipeline to download NYC TLC taxi files (Parquet/CSV/TSV) and load them into Postgres using **staging tables**, **validation**, **advisory locks**, and **atomic swaps**.

**download → staging → validate → (append | atomic swap) → analyze**

Terraform (optional) creates a **GCS bucket** and a **BigQuery dataset** (root module wires `terraform/modules/gcs` and `terraform/modules/bigquery`).

This repo is designed for reproducible local runs using **Docker Compose** (laptop-friendly).

---

## Contents

- [Project structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Quick start](#quick-start)
- [Run commands](#run-commands)
- [Access Postgres](#access-postgres)
- [Services overview](#services-overview)
- [Terraform](#terraform)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Data source](#data-source)

---

## Project structure

```text
01-docker-terraform
├── Makefile
├── README.md
├── .env.example
├── docker-compose.yml
├── main.py                 # CLI entry point
├── pyproject.toml
├── uv.lock
├── docker_ingestion_pipeline/
│   ├── Dockerfile
│   ├── __init__.py
│   ├── config.py           # paths, loader settings, logging
│   ├── core/ingestion_pipeline.py
│   ├── db/                 # loaders, schema, swapper, lock, optimizer, validator
│   ├── ports/              # interfaces (DIP)
│   └── utils/              # downloader, progress, identifiers, datetime fix
├── sql/
└── terraform/
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
````

---

## Prerequisites

* Docker + Docker Compose
* (Optional, local run) `uv` installed
* (Optional) `psql`

Terraform (optional):

* Terraform CLI
* GCP project with billing enabled
* Auth configured, e.g. `gcloud auth application-default login`

---

## Configuration

Create `.env` from the template:

```bash
cp .env.example .env
```

Notes:

* `main.py` loads `.env` from the project root (same folder as `main.py`) with `override=False`.
* Docker Compose also uses `env_file: .env`, and the `app` service sets `DB_HOST=db` and `DB_PORT=5432` internally.

---

## Quick start

### Option A — Run inside Docker (recommended)

```bash
# 1) start the stack (db + app)
make docker.up

# 2) ingest a month (runs inside the running app container)
make docker.exec.ingest TAXI=yellow YEAR=2024 MONTH=01 FILE_FORMAT=parquet IF_EXISTS=replace
```

### Option B — Run locally (outside Docker)

```bash
# 1) install deps
make local.sync

# 2) ingest (make sure db is running)
make local.ingest TAXI=yellow YEAR=2024 MONTH=01 FILE_FORMAT=parquet IF_EXISTS=replace
```

---

## Run commands

### CLI commands

* **Monthly ingest (DTC release naming)**
  `python main.py ingest --taxi yellow --year 2024 --month 01 --file-format parquet`

* **Custom URL ingest**
  `python main.py ingest-url --url "<URL>" --table-name "<NAME>"`

### `--if-exists` behavior

If the final table already exists:

* `skip` / `fail` are decided in `main.py` **before** the pipeline runs
* `replace` uses **staging + atomic swap**
* `append` loads into staging, validates, then **INSERT INTO final**, drops staging

### Makefile cheatsheet

| Goal                                 | Command                                                  |
| ------------------------------------ | -------------------------------------------------------- |
| Start stack                          | `make docker.up`                                         |
| Stop stack                           | `make docker.down`                                       |
| Show status                          | `make docker.ps`                                         |
| Tail logs                            | `make docker.logs`                                       |
| Run ingest inside running container  | `make docker.exec.ingest TAXI=yellow YEAR=2024 MONTH=01` |
| One-off ingest (no docker.up needed) | `make docker.run.ingest TAXI=yellow YEAR=2024 MONTH=01`  |
| Run local ingest                     | `make local.ingest TAXI=yellow YEAR=2024 MONTH=01`       |
| Shell into app                       | `make app.shell`                                         |
| Open psql in db container            | `make db.psql`                                           |

---

## Access Postgres

From your host machine:

```bash
psql -h localhost -p ${DB_PORT:-5432} -U ${DB_USER:-postgres} -d ${DB_NAME:-ny_taxi}
```

Inside Docker network:

* host: `db`
* port: `5432`

---

## Services overview

| Service | Purpose                      | Ports                                          |
| ------- | ---------------------------- | ---------------------------------------------- |
| `db`    | Postgres 16 target warehouse | host `localhost:${DB_PORT}` → container `5432` |
| `app`   | Python ingestion runner      | none                                           |

Compose mounts:

* `./data` → `/app/data` (downloads)
* `./logs` → `/app/logs` (file log: `logs/app.log`)
* Postgres uses a named volume `ny_taxi_postgres_data`

---

## Terraform

Terraform root module creates:

* a **GCS bucket**
* a **BigQuery dataset**

Run:

```bash
cd terraform
terraform init
terraform apply
```

When done testing:

```bash
terraform destroy
```

---

## Verification

Example checks:

```sql
SELECT COUNT(*)::bigint AS rows
FROM public.yellow_tripdata_2024_01;

SELECT tpep_pickup_datetime, passenger_count
FROM public.yellow_tripdata_2024_01
LIMIT 5;
```

---

## Troubleshooting

* **Postgres not ready:** `make docker.ps` and wait for healthcheck to become healthy
* **404 on download:** dataset URL changed; verify DataTalksClub release path (the log will show HTTP status)
* **Table exists:** change `IF_EXISTS` (`replace` / `append` / `skip` / `fail`)
* **Invalid table name:** identifiers must match `^[A-Za-z_][A-Za-z0-9_]*$`
* **Big files / memory pressure:** lower `LOADER_CHUNK_SIZE` and/or `LOADER_BATCH_SIZE`

---

## Data source

NYC TLC datasets (DataTalksClub mirror):
[https://github.com/DataTalksClub/nyc-tlc-data/releases](https://github.com/DataTalksClub/nyc-tlc-data/releases)
