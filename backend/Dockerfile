FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including nodejs for JS static analysis if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    gcc \
    default-jdk \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY benchmarks ./benchmarks

ENV PORT=8000
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
