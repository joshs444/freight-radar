# Freight Radar backend — worker / schedule-init / api share this image.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# install deps first (better layer caching), then the package
COPY pyproject.toml ./
COPY freight_radar ./freight_radar
RUN pip install --upgrade pip && pip install .

# DuckDB + published JSON live on mounted volumes (see docker-compose)
ENV FREIGHT_RADAR_DB=/data/freight_radar.duckdb \
    FREIGHT_RADAR_PUBLISH_DIR=/published \
    TEMPORAL_ADDRESS=temporal:7233

# default command is the worker; compose overrides for schedule-init / api
CMD ["python", "-m", "freight_radar.temporal.worker"]
