FROM python:3.13-slim

WORKDIR /app

# Copy scripts and requirements
COPY scripts/ /app/scripts/
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Make scripts executable
RUN chmod +x /app/scripts/*.py

# Set environment
ENV PYTHONUNBUFFERED=1
ENV WORK_DIR=/media

# Default command
CMD ["python3", "/app/scripts/organize.py"]
