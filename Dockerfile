FROM python:3.10-slim

# Prevent Python buffering logs
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (needed for ML libs)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better caching)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Preloading of Models

RUN python -c "from engine.analyze_edit import load_models; load_models()"

# Copy project files
COPY . .

# Default run command
CMD ["python", "-m", "services.scraper.wiki_scrapper"]
