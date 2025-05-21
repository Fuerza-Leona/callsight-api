# CallSight API

A FastAPI application for audio call analysis and transcription.

## Setup

1. Clone the repository
2. Install uv: `brew install uv`
3. Install packages and initialize virtual env: `uv sync`
4. Update environment variables: `./update-env.sh [main, staging, custom...]`

## Start

```bash
uv run app/cli.py [--dev]
```

## Testing

Run tests with:

```bash
pytest
```

Or with coverage:

```bash
pytest --cov=app
```

## API Documentation

When the server is running, API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc