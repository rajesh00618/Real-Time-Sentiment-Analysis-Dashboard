FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy backend models and services first (needed by worker)
COPY backend/models ./backend/models
COPY backend/services ./backend/services

# Copy worker requirements and code
COPY worker/requirements.txt ./worker/
COPY worker/*.py ./worker/

WORKDIR /app/worker

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install PyTorch CPU version separately with increased timeout
RUN pip install --no-cache-dir --default-timeout=1000 torch==2.1.1 --index-url https://download.pytorch.org/whl/cpu

# Run worker
CMD ["python", "worker.py"]
