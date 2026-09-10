# Bayyina — one container, two toolchains.
#
# The frontend is built in a Node stage and copied into the Python runtime as
# static files, so the product deploys as a single image with a single process.
# The FE/BE split is a development concern (D-019); this is where it disappears.
#
# Build from the repository root:
#     docker build -t bayyina .
#     docker run -p 8000:8000 bayyina
#
# BAYYINA_ENV is deliberately NOT set here. The image should not assume where it
# runs, and `production` requires an https BAYYINA_BASE_URL (D-045) — so baking
# it in would make a plain `docker run` crash. The platform config sets the two
# together, because they are only meaningful together.

# ---------------------------------------------------------------------------
# Stage 1 — build the interface
# ---------------------------------------------------------------------------
FROM node:22-slim AS frontend

WORKDIR /build

# Dependencies first, so a source-only change does not reinstall them.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ---------------------------------------------------------------------------
# Stage 2 — the runtime
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# PYTHONDONTWRITEBYTECODE: a read-only or ephemeral filesystem should not
# accumulate .pyc files. PYTHONUNBUFFERED: logs must appear in the platform's
# log stream immediately, not when a buffer happens to flush.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RULES_DIR=/app/rules \
    DATA_DIR=/app/data \
    FRONTEND_DIST=/app/static

WORKDIR /app

COPY backend/pyproject.toml backend/constraints.txt ./
COPY backend/src/ ./src/
# The same pinned set CI tested against. Installing unpinned here would ship an
# image built from dependencies nothing had run the suite against.
RUN pip install --no-cache-dir -c constraints.txt .

# THE CORPUS. Copied explicitly and verified below: an image that ships an
# unsigned or tampered rule must fail to build, not fail in front of a caller.
COPY backend/rules/ ./rules/
COPY backend/scripts/ ./scripts/

COPY --from=frontend /build/dist/ ./static/

# THE COMPARABLES. Built by `scripts/ingest_market.py` before the image is, and
# copied as a directory rather than a file so that a build without one still
# succeeds: market data is optional at boot by design (D-074), and the notice
# rule and a caller-supplied figure both work without it. `/healthz` reports its
# absence rather than the image hiding it.
#
# .dockerignore keeps the 359 MB build database and the raw release out. Only
# `comparables.duckdb` comes, at 1.3 MB.
COPY backend/data/ ./data/

# Guardrail G7, moved as early as it can go. The same check runs in CI and again
# at boot; here it means a bad corpus cannot even become an image.
RUN python scripts/verify_corpus.py rules/

# The audit log lives here too. On a platform with an ephemeral filesystem it is
# wiped on redeploy — mount a volume at /app/data for anything but a demo.
# `mkdir -p` leaves any comparables database copied above untouched.
RUN mkdir -p /app/data

# Non-root. The process reads signed rules and appends to an audit log; it has
# no reason to be able to modify its own code.
RUN useradd --create-home --uid 10001 bayyina \
    && chown -R bayyina:bayyina /app/data
USER bayyina

EXPOSE 8000

# --proxy-headers with --forwarded-allow-ips: TLS terminates at the platform
# edge, so the original scheme and client address arrive in X-Forwarded-*.
# Without these the app believes every request is plain HTTP from the proxy —
# which would suppress HSTS and collapse the rate limiter onto one client.
CMD ["uvicorn", "bayyina.api.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
