# =============================================================================
# Dockerfile — ECOAIMS Frontend (Dash)
# =============================================================================
# Base image: Python 3.12 slim (small footprint)
FROM python:3.12-slim

# Prevent Python from writing .pyc files & enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory inside the container
WORKDIR /app

# ── 1. Copy requirements and install dependencies ──────────────────────
COPY ecoaims_frontend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ── 2. Copy the entire frontend codebase ───────────────────────────────
COPY ecoaims_frontend/ ./ecoaims_frontend/

# ── 3. Expose the Dash default port ────────────────────────────────────
EXPOSE 8050

# ── 4. Set PYTHONPATH so `ecoaims_frontend` package is resolvable ──────
ENV PYTHONPATH="/app:${PYTHONPATH}"

# ── 5. Default command ─────────────────────────────────────────────────
# The app reads ECOAIMS_API_BASE_URL from the environment at runtime.
# Override via: -e ECOAIMS_API_BASE_URL="http://host.docker.internal:8008"
CMD ["python", "ecoaims_frontend/app.py"]
