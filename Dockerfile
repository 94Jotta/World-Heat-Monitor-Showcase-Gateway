# ---------------------------------------------------------
# STAGE 1: BUILD ENVIRONMENT
# ---------------------------------------------------------
FROM python:3.11-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into a separate wheels directory to optimize cache
RUN pip install --no-cache-dir --user -r requirements.txt

# ---------------------------------------------------------
# STAGE 2: PRODUCTION RUNTIME
# ---------------------------------------------------------
FROM python:3.11-slim as runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed libraries from the builder stage
COPY --from=builder /root/.local /root/.local
COPY . .

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# Expose Gateway REST/WebSocket port
EXPOSE 8000

# Strict security: Run application as non-privileged service user
RUN useradd -u 8888 whm_service && chown -R whm_service:whm_service /app
USER whm_service

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
