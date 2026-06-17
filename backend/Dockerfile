# Flight Recorder backend image.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching).
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Application code.
COPY backend/ .

# Seed a clean demo session so the image is self-contained for the sandbox demo.
RUN python -m scripts.seed_db

EXPOSE 8000
CMD ["uvicorn", "flight_recorder.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
