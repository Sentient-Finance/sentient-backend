FROM python:3.12-slim

WORKDIR /app

# Create a non-root user first
RUN useradd -m -u 1000 appuser

# Install system dependencies (including curl for health checks)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies as root (to cache in system python) but then switch to appuser
COPY --chown=appuser:appuser pyproject.toml .
RUN pip install --no-cache-dir .

# Copy the rest of the application code
COPY --chown=appuser:appuser . .

USER appuser

# Expose the API port
EXPOSE 8000

# Use exec form for CMD to allow SIGTERM to be handled by uvicorn
CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
