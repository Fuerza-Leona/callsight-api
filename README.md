# CallSight API

![Tests](https://github.com/Fuerza-Leona/callsight-api/actions/workflows/tests.yml/badge.svg)

A FastAPI application for audio call analysis and transcription.

## Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - MacOS/Linux: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run `./update-env.sh` to update environment variables
6. Run the server: `uvicorn app.main:app --reload`

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
