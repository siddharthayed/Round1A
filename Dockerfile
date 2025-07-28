# syntax=docker/dockerfile:1
FROM --platform=linux/amd64 python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    poppler-utils \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY round1A.py main.py requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download SpaCy model (must be included in image!)
RUN python -m spacy download en_core_web_sm

# Set entrypoint
ENTRYPOINT ["python", "main.py"]
