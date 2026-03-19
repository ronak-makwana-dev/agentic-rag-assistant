FROM python:3.12-slim

# Install system tools needed for building C++ extensions (ChromaDB requirement)
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Upgrade pip and install
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]