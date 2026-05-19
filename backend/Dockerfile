# ── Stage 1: Builder ──────────────────────────────────────────────────────
# Install dependencies in a separate stage so the final image only contains
# what's needed to run — not the pip cache, build tools, or compiler output.
FROM python:3.11-slim AS builder

WORKDIR /app

# System dependencies needed only during build
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies in a separate layer: if requirements.txt doesn't change,
# Docker cache reuses this layer and skips the pip install on rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────────────────────────
# Minimal image: copy only the installed packages and application code.
# No pip, no build tools, no source cache — smaller attack surface.
FROM python:3.11-slim AS runtime

WORKDIR /app

# curl is needed at runtime for the HEALTHCHECK command
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages \
                    /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin \
                    /usr/local/bin

# Copy only the application modules the API needs.
# Build context is ./backend so all paths are relative to that folder.
COPY agents/     ./agents/
COPY pipeline/   ./pipeline/
COPY security/   ./security/
COPY models/     ./models/
COPY config/     ./config/
COPY utils/      ./utils/
COPY api.py      .
COPY requirements.txt .

# Logs directory — mounted as a volume in docker-compose for persistence
RUN mkdir -p logs

# Rule: never run as root in production containers
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check used by docker-compose depends_on condition: service_healthy.
# 40s start period gives the pipeline time to initialise before first check.
HEALTHCHECK --interval=30s \
            --timeout=10s \
            --start-period=40s \
            --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1"]
