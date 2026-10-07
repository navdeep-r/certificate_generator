FROM python:3.11-slim

WORKDIR /app

# System dependencies for asyncpg / psycopg2 / reportlab
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Storage directory must exist inside the image; bind-mount will overlay it
RUN mkdir -p storage

# Default: run the API server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
