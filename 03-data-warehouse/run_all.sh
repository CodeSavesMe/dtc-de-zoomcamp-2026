#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "====================================================="
echo "  Starting Multi-Year Pipeline (2019 & 2020)  "
echo "====================================================="

# List of jobs in "color year" format
JOBS=(
#  "green 2019"
#  "green 2020"
  "yellow 2019"
  "yellow 2020"
)

for JOB in "${JOBS[@]}"; do
  # Extract color and year from the string
  COLOR=$(echo $JOB | awk '{print $1}')
  YEAR=$(echo $JOB | awk '{print $2}')

  echo "--------------------------------------------------------"
  echo ">>> Preparing .env for ${COLOR} Taxi year ${YEAR}..."
  echo "--------------------------------------------------------"

  # Create/overwrite the .env file with the appropriate configuration
  cat <<EOF > .env
# --- Core GCP Settings ---
GCP_PROJECT_ID=dtc-de-2026
BQ_LOCATION=US

# --- Auth ---
GOOGLE_APPLICATION_CREDENTIALS=

# --- GCS Source Configuration ---
GCS_BUCKET_NAME=dw-nytaxi-prod-us-raw
GCS_RAW_PREFIX=
GCS_TLC_URI_PREFIX=

# --- Taxi Data Settings ---
TAXI_COLOR=${COLOR}
TAXI_YEAR=${YEAR}
MONTHS=01,02,03,04,05,06,07,08,09,10,11,12
TAXI_BASE_URL=https://d37ci6vzurychx.cloudfront.net/trip-data

# --- BigQuery Dataset Layers ---
BQ_DATASET_STAGING=dw_nytaxi_staging
BQ_DATASET_FINAL=dw_nytaxi_marts

# --- Table Naming ---
BQ_TABLE_EXT=${COLOR}_tripdata_ext
BQ_TABLE_BASE=${COLOR}_tripdata_base
BQ_TABLE_FINAL=${COLOR}_tripdata

# --- SQL Runner Settings ---
SQL_DIR=sql
SQL_FILE=
SQL_PRINT_RESULTS=true
SQL_PRINT_MAX_ROWS=20
BQ_DRY_RUN=false

# --- Runtime & Performance Tuning ---
LOG_DIR=./logs
MAX_WORKERS=5
MAX_RETRIES=3
HTTP_TIMEOUT_SEC=300
GCS_CHUNK_SIZE=8388608
EOF

  # Optional: Uncomment the lines below if you also need to download data to GCS again
  # echo ">>> 1. Downloading data to GCS (download-to-gcs)..."
  # uv run main.py download-to-gcs

  echo ">>> 2. Running SQL in BigQuery (run-sql)..."
  # MUST use --execute to disable the default --dry-run from the click CLI
  uv run main.py run-sql --execute

  echo ">>> Finished processing ${COLOR} Taxi ${YEAR}!"
  echo ""
done

echo "====================================================="
echo "  All data successfully processed and merged!      "
echo "====================================================="