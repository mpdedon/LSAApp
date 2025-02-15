# syntax=docker/dockerfile:1

# Comments are provided throughout this file to help you get started.
# If you need more help, visit the Dockerfile reference guide at
# https://docs.docker.com/go/dockerfile-reference/

# Want to help us make this template better? Share your feedback here: https://forms.gle/ybq9Krt8jtBL3iCk7

# Use Python 3.11 slim image
ARG PYTHON_VERSION=3.11.4
FROM python:${PYTHON_VERSION}-slim AS base

# Prevent Python from writing .pyc files and buffer logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-privileged user
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

# Install dependencies
RUN apt-get update && apt-get install -y curl wait-for-it sudo postgresql-client

# Create necessary directories BEFORE switching user
RUN mkdir -p /app/logs /app/core/migrations /app/staticfiles && \
    touch /app/logs/error.log && \
    chown -R appuser:appuser /app/logs /app/core/migrations /app/staticfiles && \
    chmod -R 775 /app/logs && \
    chmod 664 /app/logs/error.log

# Copy the entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to non-root user
USER appuser

# Set environment variables for user-installed packages
ENV PYTHONUSERBASE=/tmp/python

# Install dependencies with cache optimizations
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python -m pip install --user --no-cache-dir -r requirements.txt

# Add Python user install directory to PATH
ENV PATH="${PYTHONUSERBASE}/bin:${PATH}"

# Copy source code
COPY --chown=appuser:appuser . .

# Expose port 8000
EXPOSE 8000

# Set the entrypoint script
ENTRYPOINT ["/entrypoint.sh"]