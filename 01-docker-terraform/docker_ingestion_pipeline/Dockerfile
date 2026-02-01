# 1. Base Image: Use a lightweight Python 3.13 image
FROM python:3.13.11-slim

# 2. Tooling: Copy 'uv' binary (faster than installing)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

# 3. Work Directory: Set workspace inside container
WORKDIR /app

# 4. OS Dependencies: Install LibPQ for PostgreSQL connection and Nano
RUN apt-get update && apt-get install -y --no-install-recommends  \
    libpq-dev \
    nano \
    && rm -rf /var/lib/apt/lists/*

# 5. Cache Layer: Copy dependency definition files first
# - uv sync --locked: install all deps according to uv.lock (dev + prod)
#   Used for development or staging builds to leverage Docker cache
COPY pyproject.toml uv.lock ./
RUN uv sync --locked

# 6. Production Dependencies: Sync from lock file in strict mode
# - uv sync --frozen --no-dev --no-install-project: install only production deps
#   Used for final production image, strict version check, smaller image
#RUN uv sync --frozen --no-dev --no-install-project

# 7. Environment: Auto-activate virtual environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 8. Source Code: Copy pipeline module and main script
COPY docker_ingestion_pipeline/ ./docker_ingestion_pipeline/
COPY main.py .

# 9. Execution: Run the app
# - For development/debug: keep container running
# - For production, replace CMD with ENTRYPOINT to run your app
# ENTRYPOINT ["python", "main.py"]
CMD ["tail", "-f", "/dev/null"]