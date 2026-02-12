FROM python:3.13-slim

WORKDIR /app

# Copy project files
COPY . /app/

# Create non-root user
RUN groupadd -r mediaorg && \
    useradd -r -g mediaorg -u 1000 mediaorg && \
    chown -R mediaorg:mediaorg /app

# Install package and dependencies
RUN pip install --no-cache-dir -e .

# Make scripts executable
RUN chmod +x /app/scripts/*.py

# Set environment
ENV PYTHONUNBUFFERED=1
ENV WORK_DIR=/media

# Switch to non-root user
USER mediaorg

# Default command (backward compatible)
CMD ["python3", "/app/scripts/organize.py"]
