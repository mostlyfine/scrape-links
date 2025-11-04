# syntax=docker/dockerfile:1
# Minimal image to run the web scraper as documented in README.md
# Uses a non-root user and installs system libs required for lxml/readability.

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build deps for lxml (readability-lxml) then clean.
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential \
  libxml2-dev \
  libxslt1-dev \
  zlib1g-dev \
  && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better layer caching
COPY requirements.txt ./
RUN pip install --upgrade pip \
  && pip install -r requirements.txt

# Copy application code
COPY scrape_links.py ./

# Create non-root user
RUN addgroup --system app && adduser --system --ingroup app app
USER app

# Default entrypoint runs the script; users can append URL and options.
ENTRYPOINT ["python", "scrape_links.py"]
# By default show help if no args are passed.
CMD ["-h"]

# Example usage:
#   docker build -t scraper .
#   docker run --rm scraper https://example.com/docs/
#   docker run --rm -v "$PWD/output":/app/output scraper -d 1 -o https://example.com/docs/
