FROM python:3.13-slim

WORKDIR /app

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    ffmpeg \
    libsndfile1 \
    python3-dev \
    libpq-dev \ 
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
RUN pip cache purge && \
    python -m pip install --upgrade pip && \
    python -m pip install --upgrade setuptools wheel && \
    pip install meson importlib-metadata toml setuptools-metadata

# Install numpy first with legacy resolver to avoid dependency conflicts
RUN pip install numpy --use-deprecated=legacy-resolver

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install the package in development mode
RUN pip install -e .

# Install development dependencies
RUN pip install pytest pytest-asyncio pytest-mock pytest-cov pre-commit

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application with hot reloading
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]