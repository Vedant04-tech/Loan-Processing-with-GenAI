# Production Dockerfile for TRACE Underwriting Decision Platform
FROM python:3.11-slim

# Set runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install security updates and base utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cache Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy codebase
COPY . .

# Ensure output directories exist
RUN mkdir -p \
    "step4_Document comparison/output" \
    "step5_calculation/output" \
    "step6_risk_anomaly/output"

# Container Entrypoint: defaults to running all benchmark cases, supports passing single applicant IDs
ENTRYPOINT ["python", "main.py"]
CMD ["--all"]
