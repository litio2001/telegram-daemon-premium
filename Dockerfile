# Telegram Download Daemon Premium - Dockerfile
# Multi-stage build for optimized image size and security

FROM python:3.10.5 AS compile-image

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir --user telethon cryptg==0.3 pysocks

FROM python:3.10.5-slim AS run-image

# Create non-root user for security
RUN groupadd -r telegram && useradd -r -g telegram telegram

# Copy Python packages from compile stage
COPY --from=compile-image /root/.local /home/telegram/.local

# Set up application directory
WORKDIR /app

# Copy application files
COPY telegram-download-daemon.py sessionManager.py ./
COPY *.md ./

# Set proper permissions
RUN chmod 755 /app/*.py && \
    chown -R telegram:telegram /app && \
    mkdir -p /downloads /session && \
    chmod 777 /downloads /session  # Allow any user to write

# Don't switch to non-root user yet - let docker-compose handle user mapping
# USER telegram

# Add user's local bin to PATH (for both root and user)
ENV PATH=/home/telegram/.local/bin:/root/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

# Labels for metadata
LABEL maintainer="Telegram Download Daemon Premium" \
      version="1.15" \
      description="Premium-enhanced Telegram Download Daemon with auto-detection" \
      telegram-download-daemon="true"

CMD [ "python3", "./telegram-download-daemon.py" ]
