# Telegram Download Daemon v2.0 Premium Enhanced - Dockerfile
# Single-stage build for better compatibility with user mapping

FROM python:3.10.5-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies globally
RUN pip install --no-cache-dir telethon==1.36.0 cryptg==0.3 pysocks

# Set up application directory
WORKDIR /app

# Copy application files
COPY telegram-download-daemon.py sessionManager.py ./
COPY README.md ./

# Create directories and set permissions
RUN mkdir -p /downloads /session && \
    chmod 777 /downloads /session && \
    chmod 755 /app/*.py

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import telethon; print('OK')"

# Labels for metadata
LABEL maintainer="Telegram Download Daemon v2.0 Premium Enhanced" \
      version="2.0" \
      description="Premium-enhanced Telegram Download Daemon with stats, real-time speed, and interactive commands" \
      telegram-download-daemon="true" \
      features="premium-detection,statistics,real-time-speed,auto-retry,file-filters,pause-resume"

CMD [ "python3", "./telegram-download-daemon.py" ]
